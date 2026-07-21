"""
LLM integration layer.
 
This module is responsible for all communication
with the language model via OpenAI/Azure endpoint,
including formatting tools, executing completions, 
and capturing token usage.
"""
import copy
import json
import logging
from openai import AsyncOpenAI, OpenAIError
from config import (
    MODEL_NAME,
    AZURE_ENDPOINT,
    API_KEY,
    MAX_RESPONSE_TOKENS,
    TOKEN_LIMIT_PARAM,
)
from tools.tool import Tool

logger = logging.getLogger(__name__)
 
class LLMClient:
    """
    Client wrapper for OpenAi/Azure API calls.
    Handles formatting of system tools, conversational completions and
    usage tracking.
    
    """
    def __init__(self):
        # Initializa the OpenAI client pointing to the Azure or custom endpoint.
        # A timeout is set so a hanging/unresponsive endpoint doesn't block forever.
        self.client = AsyncOpenAI(
            base_url=AZURE_ENDPOINT,
            api_key=API_KEY,
            timeout=60.0
        )
 
    def _tool_to_dict(self, tool: Tool):
        """
        Converts a custom Tool class instance into the schema format 
        expected by the OpenAI tools API.
        """
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        }
 
    async def generate_response(self, messages, tools: list = None):
        """
        Sends the conversation history to the LLM and returns the structure 
        including generated message, tool calls and API token usage.
        """

        # token limit kwarg name differs by provider (see TOKEN_LIMIT_PARAM in config.py)
        kwargs = {
            "model": MODEL_NAME,
            "messages": messages,
            TOKEN_LIMIT_PARAM: MAX_RESPONSE_TOKENS
        }

        # Inject formatted tools if any are active
        if tools:
            kwargs["tools"] = [
                self._tool_to_dict(tool)
                for tool in tools
            ]
        
        
        try:
            # Execute API request
            response = await self.client.chat.completions.create(
                **kwargs
            )
        except OpenAIError as e:
            # Handle specific OpenAi exceptions
            logger.exception("LLM API call failed (model=%s, base_url=%s)", MODEL_NAME, AZURE_ENDPOINT)
            raise e
        except Exception as e:
            logger.exception("Unexpected connection error calling the LLM")
            raise e
 
        # Extract the primary generated assistant message
        choice = response.choices[0]
        message = choice.message

        # A response cut off mid-generation (finish_reason == "length") is
        # the main reason content can come back empty/incomplete — flag it
        # loudly instead of leaving the caller to guess from token counts.
        was_truncated = getattr(choice, "finish_reason", None) == "length"
        if was_truncated:
            logger.warning(
                "LLM response was truncated at MAX_RESPONSE_TOKENS (%d). "
                "Consider raising this value in config.py.", MAX_RESPONSE_TOKENS
            )

        # Build the standardized response dictionary
        result = {
            "message": {
                "role": "assistant",
                "content": message.content
            }, 
            "truncated": was_truncated,
            # Extract and pass the API usage back to the agent
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if getattr(response, "usage", None) else None
        }

        # Process tool calls if the model requested any actions
        if getattr(message, "tool_calls", None):
            result["message"]["tool_calls"] = []
 
            for tc in message.tool_calls:
                # Safely parse JSON arguments if they come as string
                try:
                    args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments,str) else tc.function.arguments
                except json.JSONDecodeError:
                    args = tc.function.arguments

                result["message"]["tool_calls"].append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": args
                    }
                })
 
        return result
    
    async def aclose(self):
        """Cleanly closes the underlying async HTTP connections on shutdown."""
        await self.client.close()