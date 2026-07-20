"""
Conversation memory management.

This module is responsible for storing and retrieving
messages exchanged between the user and the AI assistant.
"""
from config import (
    INPUT_TOKEN_PRICE_PER_MILLION,
    OUTPUT_TOKEN_PRICE_PER_MILLION,
    MAX_CONTEXT_TOKENS,
    KEEP_RECENT_MESSAGES,
)
import json
import os
import logging
from utils import count_tokens

logger = logging.getLogger(__name__)


class ConversationContext:
    """
    Manages the conversation history, dynamically builds the system
    and keeps track of cumulative token consumption across the session.
    """


    def __init__(self, llm_client=None):
        # Reference to the LLM client, used to generate summaries when the
        # context needs to be compressed. Optional: if not provided, context
        # recycling falls back to plain truncation (old behavior).
        self.llm_client = llm_client

        # Global token counters
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Construct the inistial dynamic system prompt - Identity + Always-loaded procedures and facts
        system_message = self.assemble_system_prompt()

        # Store the token size on the message for reference/debugging only.
        # We do NOT add it to total_input_tokens here: no API call has
        # happened yet, and the system prompt is resent in full with every
        # real request afterwards — it's already counted inside each
        # turn's actual usage.prompt_tokens. Adding it here too would
        # double-count it in the session total.
        sys_input = count_tokens(system_message["content"])
        system_message["input_tokens"] = sys_input
        system_message["output_tokens"] = 0

        self.messages = [system_message]


    # Knowledge categories that get scanned for always-loaded documents.
    # Adding a new category (e.g. "policies") means: create the folder +
    # registry.json, then add its name here. No other code changes needed.
    ALWAYS_LOAD_CATEGORIES = ("facts", "procedures")

    def _load_always_load_content(self, category: str) -> str:
        """
        Loads and concatenates every document in the given knowledge
        category (e.g. 'facts', 'procedures') that is marked
        'always_load: true' in that category's registry.json.
        Returns an empty string (and logs a warning) if the registry
        or a referenced document is missing/corrupted.
        """
        content = ""
        registry_path = f"knowledge/{category}/registry.json"

        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except FileNotFoundError:
            logger.warning("'%s' not found. Skipping '%s'.", registry_path, category)
            return content
        except json.JSONDecodeError:
            logger.error("'%s' is corrupted. Please check its JSON syntax.", registry_path)
            return content

        for document in registry:
            if not document.get("always_load", False):
                continue
            doc_path = f"knowledge/{category}/{document['id']}.md"
            try:
                with open(doc_path, "r", encoding="utf-8") as f:
                    content += f"\n\n#{document['name']}\n\n" + f.read()
            except FileNotFoundError:
                logger.warning("'%s' not found. Skipping this document.", doc_path)

        return content

    def assemble_system_prompt(self):
        """
        Loads the core identity file and appends any documents from
        the registry that have always_load
        """

        # Load the primary identity file
        try:
            with open(
                "knowledge/prompts/identity.md", "r", encoding="utf-8"
            ) as f:
                prompt_content = f.read()
        except FileNotFoundError:
            logger.error("'identity.md' is missing. Falling back to a minimal generic identity.")
            prompt_content = (
                "You are a helpful Linux system administration assistant. "
                "Your custom identity file could not be loaded, so you are "
                "operating with a minimal default persona."
            )

        # Dynamically append always-loaded content from every knowledge category
        for category in self.ALWAYS_LOAD_CATEGORIES:
            prompt_content += self._load_always_load_content(category)

        return {
            "role": "system",
            "content": prompt_content
        }
    

    def _current_context_tokens(self) -> int:
        """
        Computes the real token size of everything currently held in
        self.messages (the actual context window we'd send to the LLM),
        as opposed to the cumulative session totals tracked elsewhere.
        Recomputed from content directly so it stays accurate regardless
        of whether a given message was stored with token metadata.
        """
        total = 0
        for msg in self.messages:
            total += count_tokens(str(msg.get("content", "")))
        return total

    async def _summarize_old_messages(self, messages_to_summarize: list) -> str | None:
        """
        Asks the LLM to compress a batch of older messages into a short,
        factual summary, so we can shrink the context without losing the
        gist of what was already discussed. Returns None if summarization
        isn't possible (no llm_client, no content, or the call fails) so
        the caller can fall back to plain truncation.
        """
        if not self.llm_client or not messages_to_summarize:
            return None

        transcript_lines = []
        for msg in messages_to_summarize:
            role = msg.get("role", "unknown")
            content = msg.get("content") or ""
            if content:
                transcript_lines.append(f"{role}: {content}")
        transcript = "\n".join(transcript_lines)

        if not transcript.strip():
            return None

        summarization_request = [
            {
                "role": "system",
                "content": (
                    "You compress an earlier portion of a Linux sysadmin support "
                    "conversation into a short factual summary (max 5-6 sentences). "
                    "Capture: what the user asked about, what solutions or commands "
                    "were already given, and any issue that stayed unresolved. "
                    "Do not invent information that isn't in the transcript."
                )
            },
            {"role": "user", "content": transcript}
        ]

        try:
            result = await self.llm_client.generate_response(summarization_request)
            summary_text = (result.get("message", {}) or {}).get("content", "")
            return summary_text.strip() or None
        except Exception as e:
            logger.warning("Context summarization failed: %s", e)
            return None

    async def add_message(self, message:dict, input_tokens:int = 0,output_tokens:int=0):
        """
        Adds a new message to the history. If the real token size of the
        context exceeds MAX_CONTEXT_TOKENS, older messages are compressed
        into a single LLM-generated summary instead of being discarded,
        while the system identity and the most recent turns are preserved.
        """
        # Default fallback to ensure msg_to_store is defined
        msg_to_store = message.copy()

        if input_tokens or output_tokens:
            
            # Assign token values
            msg_to_store["input_tokens"] = msg_to_store.get("input_tokens",input_tokens)
            msg_to_store["output_tokens"] = msg_to_store.get("output_tokens",output_tokens)

            # Increment overall session counters
            self.total_input_tokens += msg_to_store["input_tokens"]
            self.total_output_tokens += msg_to_store["output_tokens"]
        
        # append the message with token metadata ti you message list
        self.messages.append(msg_to_store)

        # Prevent LLM context window overflow error during long chat.
        # Trigger is the ACTUAL token size of the context, not message count.
        current_tokens = self._current_context_tokens()
        has_enough_messages = len(self.messages) > KEEP_RECENT_MESSAGES + 1
        if current_tokens > MAX_CONTEXT_TOKENS and has_enough_messages:
            logger.info(
                "Context reached %d tokens (limit: %d). Compressing older turns...",
                current_tokens, MAX_CONTEXT_TOKENS
            )

            # Safeguard index 0: Ensure the System Identity Prompt is never purged
            system_prompt = self.messages[0]

            # Always keep the most recent turns untouched, for coherence
            recent_messages = self.messages[-KEEP_RECENT_MESSAGES:] if KEEP_RECENT_MESSAGES else []
            older_messages = self.messages[1:len(self.messages) - len(recent_messages)]

            summary_text = await self._summarize_old_messages(older_messages)

            if summary_text:
                summary_message = {
                    "role": "system",
                    "content": f"# Summary of earlier conversation\n{summary_text}"
                }
                self.messages = [system_prompt, summary_message] + recent_messages
                logger.info("Older turns summarized and compressed.")
            else:
                # Fallback: summarization unavailable or failed -> plain truncation
                self.messages = [system_prompt] + recent_messages
                logger.info("Summarization unavailable, fell back to plain truncation.")

    # Directory where session JSON files are stored (one file per session_id)
    SESSIONS_DIR = "sessions"

    def save_session(self, session_id: str) -> str:
        """
        Persists the current conversation (message history + token counters)
        to disk as JSON, so it can be resumed later via load_session().
        Returns the path the session was saved to.
        """
        os.makedirs(self.SESSIONS_DIR, exist_ok=True)
        path = os.path.join(self.SESSIONS_DIR, f"{session_id}.json")

        data = {
            "session_id": session_id,
            "messages": self.messages,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error("Could not save session '%s': %s", session_id, e)

        return path

    def load_session(self, session_id: str) -> bool:
        """
        Restores a previously saved conversation from disk, replacing the
        current in-memory history and token counters. Returns True if the
        session was found and loaded successfully, False otherwise (current
        state is left untouched on failure).
        """
        path = os.path.join(self.SESSIONS_DIR, f"{session_id}.json")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.warning("Session '%s' not found.", session_id)
            return False
        except json.JSONDecodeError as e:
            logger.error("Session file '%s' is corrupted: %s", path, e)
            return False

        self.messages = data.get("messages", self.messages)
        self.total_input_tokens = data.get("total_input_tokens", self.total_input_tokens)
        self.total_output_tokens = data.get("total_output_tokens", self.total_output_tokens)
        return True

    @classmethod
    def list_sessions(cls) -> list[str]:
        """
        Returns the list of saved session IDs, most recently modified first.
        Empty list if the sessions directory doesn't exist yet.
        """
        if not os.path.isdir(cls.SESSIONS_DIR):
            return []

        files = [f for f in os.listdir(cls.SESSIONS_DIR) if f.endswith(".json")]
        files.sort(
            key=lambda f: os.path.getmtime(os.path.join(cls.SESSIONS_DIR, f)),
            reverse=True
        )
        return [os.path.splitext(f)[0] for f in files]

    def export_history(self, filepath: str) -> str:
        """
        Writes a human-readable Markdown transcript of the conversation
        (user/assistant turns only — system/tool messages are omitted)
        to filepath. Returns the path written to.
        """
        lines = [f"# Conversation export ({len(self.messages)} messages)\n"]

        for msg in self.messages:
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content") or ""
            speaker = "**You**" if role == "user" else "**AI**"
            lines.append(f"{speaker}: {content}\n")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except OSError as e:
            logger.error("Could not export conversation to '%s': %s", filepath, e)

        return filepath

    def get_history(self):
        """
        Return the chronological list of messages.
        """
        return self.messages
    
    def get_total_tokens_consumed(self):
        """
        Return the total token stats
        """

        price_per_token_in = INPUT_TOKEN_PRICE_PER_MILLION/1_000_000
        price_per_token_out = OUTPUT_TOKEN_PRICE_PER_MILLION/1_000_000

        cost = (self.total_input_tokens*price_per_token_in) + (self.total_output_tokens*price_per_token_out)
        return {
            "total_input": self.total_input_tokens,
            "total_output": self.total_output_tokens,
            "grand_total": self.total_input_tokens + self.total_output_tokens,
            "total_cost": f"${cost:.6f}" # 6 decimals
        }