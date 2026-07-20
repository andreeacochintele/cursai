"""Core agent orchestration.
The agent coordinates communication between
the conversation context and the language model."""
import copy
import json
import logging

from embeddings_client import EmbeddingsClient
from utils import count_tokens
from config import RAG_TOP_K

logger = logging.getLogger(__name__)

# Safety cap on chained tool calls (model calls a tool, sees the result,
# decides to call another, etc.) — prevents an infinite loop if the model
# gets stuck repeatedly requesting tools instead of answering.
MAX_TOOL_ITERATIONS = 5


class Agent:

    """
    Main Agent controller, using the RAG retrieval pipeline
    executing  LLM completions, managing tools, and logging sessions cost
    
    """
    def __init__(self, llm_client, context, tools=None, embeddings_client: EmbeddingsClient | None = None):
        self.llm_client = llm_client
        self.context = context
        # Convert the tools list into a lookup dictionary mapped by tool name
        self.tools = {tool.name: tool for tool in tools} if tools else {}
        # Reused across calls (instead of "new EmbeddingsClient() per message"
        # like the CLI version did) so the underlying httpx connection pool
        # is shared. Passed in explicitly so session_manager.py can give
        # every session the same shared pool.
        self.embeddings_client = embeddings_client or EmbeddingsClient()

    def _handle_tool_calls(self, tool_calls) -> list[dict]:
        """
        Iterate through requested tool calls, executes the matching local callbacks,
        and formats the results for LLM consumption.
        """
        results = []
        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            arguments_str = tc["function"]["arguments"]
            tool_id = tc["id"]

            try:
                arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                if not isinstance(arguments, dict):
                    arguments = {}
            except Exception as e:
                logger.warning("Failed to parse arguments for tool '%s': %s", tool_name, e)
                arguments = {}

            tool = self.tools.get(tool_name)
            if not tool:
                result = f"Tool '{tool_name}' not found"
            else:
                # A tool callback raising an uncaught exception used to crash
                # the whole /chat request (500). Now it's contained: the LLM
                # sees a clear failure message for THIS tool and can still
                # finish answering with whatever else it knows.
                try:
                    result = tool.callback(**arguments)
                except Exception as e:
                    logger.exception("Tool '%s' raised an exception during execution", tool_name)
                    result = f"Tool '{tool_name}' failed to run: {e}"

            # Format the output matching the OpenAi tool message schema
            results.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": str(result)
            })
        return results

    async def _get_retrieved_context(self, user_message: str) -> str:
        """
        Queries the vector database and aggregate matching documents
        If no relevant chunks are found, returns a safe fallback instruction.
        """
        try:
            # Reuses the shared EmbeddingsClient (shared httpx connection
            # pool) instead of constructing a new one per call.
            results = await self.embeddings_client.semantic_search(user_message, top_k=RAG_TOP_K)
        except Exception as e:
            # The data base is not accesible
            logger.warning("Semantic search failed: %s", e)
            return (
                "# Retrieved Context\n"
                "Warning: Internal knowledge base is currently offline.\n"
                "Fallback to you general system administration knowledge.\n"
            )
        # The search was fine but no entries over MIN_SIMILARITY
        if not results:
            return (
                "# Retrieved Context\n"
                "No specific internal documentation matches this query.\n"
                "Fallback to you general system administration knowledge\n"
            )
        # We found relevant data
        retrieved_context = "# Retrieved Context \n"
        for result in results:
            retrieved_context += result["content"] + "\n\n"
        return retrieved_context

    def _track_llm_usage(self, response) -> tuple[int, int]:
        """
        Extracts prompt and completion tokens safely from LLM response
        """
        prompt = 0
        completion = 0

        if isinstance(response, dict) and "usage" in response and response["usage"]:
            prompt = response["usage"].get("prompt_tokens", 0)
            completion = response["usage"].get("completion_tokens", 0)

        return prompt, completion

    async def _execute_tool_workflow(self, initial_message) -> tuple[dict, int, int, bool]:
        """
        Executes requested tool calls, appends results to history, and prompts the LLM again.
        Returns (message, prompt_tokens, completion_tokens, was_truncated).

        The follow-up LLM call is given the tool list again (tools=...), not
        just the previous version's plain history — this is what allows the
        model to chain a second tool call off the first one's result
        (e.g. "check status" -> sees it's failed -> "check logs"), instead of
        being forced to produce a final text answer no matter what.
        """
        total_prompt = 0
        total_completion = 0

        # Create a deep copy of the initial message to prevent mutating the original data structure
        saved_message = copy.deepcopy(initial_message)

        # Ensure that function arguments are serialized back to a JSON string 
        # to satisfy the strict schema validation of the OpenAI API
        for tc in saved_message.get("tool_calls", []):
            if not isinstance(tc["function"]["arguments"], str):
                tc["function"]["arguments"] = json.dumps(tc["function"]["arguments"])

        # We add the agent's initial intent to run the tools in context
        await self.context.add_message(saved_message)

        # Execute tools and append their response to history
        tool_results = self._handle_tool_calls(initial_message["tool_calls"])
        for result in tool_results:
            await self.context.add_message(result)

        # Second run of the LLM with the tools information — tools=... is
        # passed again so the model CAN request another tool call if the
        # result of this one calls for it (see docstring above).
        try:
            second_response = await self.llm_client.generate_response(
                self.context.get_history(),
                tools=list(self.tools.values())
            )
        except Exception as e:
            logger.error("LLM call after tool execution failed: %s", e)
            fallback_message = {
                "role": "assistant",
                "content": (
                    "I ran the requested tool(s), but I couldn't reach the language model "
                    "to finish formulating a response. Please check your connection/API "
                    "configuration and try again."
                )
            }
            return fallback_message, 0, 0, False

        # Capture the usage for this LLM turn
        p, c = self._track_llm_usage(second_response)
        total_prompt += p
        total_completion += c

        return second_response["message"], total_prompt, total_completion, second_response.get("truncated", False)

    async def process_message(self, user_message: str) -> str:
        """
        The entry point for processing incoming user prompts.
        Coordinates RAG injection, usage tracking, tool routing, and final output
        """
        # Log user's prompt
        await self.context.add_message({"role": "user", "content": user_message})

        # Retrieve semantic context (RAG)
        context_text = await self._get_retrieved_context(user_message)

        # Compute token counts for monitoring
        total_input_tokens = count_tokens(user_message) + count_tokens(context_text)

        # Create a temporary message list for API calls only.
        # We intentionally do NOT persist the RAG context into self.context:
        # this keeps the permanent conversation history lean (cost optimization),
        # while still giving the LLM the retrieved context for this single turn.
        api_messages = self.context.get_history().copy()
        api_messages.append({"role": "system", "content": context_text})

        # Request initial LLM completion (uses api_messages, WITH RAG context)
        try:
            response = await self.llm_client.generate_response(
                api_messages,
                tools=list(self.tools.values())
            )
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            fallback_text = (
                "I'm unable to reach the language model right now (network or API error). "
                "Please check your connection and API configuration, then try again."
            )
            await self.context.add_message(
                {"role": "assistant", "content": fallback_text},
                input_tokens=total_input_tokens,
                output_tokens=count_tokens(fallback_text)
            )
            return fallback_text

        # Track usage of the first LLM generation
        p_tokens, c_tokens = self._track_llm_usage(response)
        total_prompt = p_tokens
        total_completion = c_tokens

        message = response["message"]
        was_truncated = response.get("truncated", False)

        # Tool-call loop: keep executing tools and re-prompting the model as
        # long as it keeps requesting them, up to MAX_TOOL_ITERATIONS. Before,
        # this only ran ONCE — a model wanting to chain a second tool call
        # off the first one's result would have that request silently
        # dropped, and whatever it said in that turn (often empty) was
        # returned as the final answer.
        iterations = 0
        while message.get("tool_calls") and iterations < MAX_TOOL_ITERATIONS:
            iterations += 1
            message, tool_p, tool_c, was_truncated = await self._execute_tool_workflow(message)
            total_prompt += tool_p
            total_completion += tool_c

        if iterations >= MAX_TOOL_ITERATIONS and message.get("tool_calls"):
            logger.warning(
                "Hit MAX_TOOL_ITERATIONS (%d) with more tool calls still pending — "
                "stopping to avoid an infinite loop.", MAX_TOOL_ITERATIONS
            )

        # Emergency local calculation fallback if the API did not return usage statistics
        if total_prompt == 0:
            total_prompt = total_input_tokens
            total_completion = count_tokens(message.get("content", ""))

        # Save the final assistant answer
        await self.context.add_message(
            message,
            input_tokens=total_prompt,
            output_tokens=total_completion
        )

        # Fetch statistics from the conversation context
        session_stats = self.context.get_total_tokens_consumed()

        # Log session usage metrics
        logger.info(
            "Current message: %d input | %d output tokens", total_prompt, total_completion
        )
        logger.info(
            "Session total — input: %d, output: %d, total: %d, cost: %s",
            session_stats["total_input"], session_stats["total_output"],
            session_stats["grand_total"], session_stats["total_cost"]
        )

        # Fallback: the LLM call succeeded but produced no usable text
        # (e.g. content came back null/empty with no tool_calls either).
        if message.get("content"):
            final_content = message["content"]
        elif was_truncated:
            final_content = (
                "My response got cut off before I could finish (token limit reached). "
                "Try asking a more specific/shorter question, or raise MAX_RESPONSE_TOKENS "
                "in config.py."
            )
        else:
            final_content = (
                "I wasn't able to come up with a useful answer for that. "
                "Could you rephrase the question or give a bit more detail?"
            )

        return final_content