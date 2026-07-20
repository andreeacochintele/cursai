"""
Session management for the multi-user API.

The CLI version had exactly one ConversationContext living for the whole
process. A web API serves many users concurrently, each identified by a
session_id, so we need one (Agent, ConversationContext) pair per session,
kept in memory and reused across requests from the same session_id.

Two concurrency concerns this module addresses:

1. Two different sessions must never block each other. Solved by simply
   keeping separate objects per session_id — nothing shared, nothing to
   lock, across sessions.
2. Two *concurrent* requests for the *same* session_id (e.g. a double
   click, or a buggy client retry) must not interleave and corrupt that
   session's message history. Solved with one asyncio.Lock per session:
   requests for the same session_id queue up and run one at a time;
   requests for different sessions run fully in parallel.
"""
import asyncio

from agent import Agent
from conversation_context import ConversationContext
from embeddings_client import EmbeddingsClient
from tools.tools import tools


class SessionManager:
    def __init__(self, llm_client, embeddings_client: EmbeddingsClient):
        self.llm_client = llm_client
        self.embeddings_client = embeddings_client
        self._agents: dict[str, Agent] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        # Guards creation of new per-session entries in the dicts above,
        # so two simultaneous first-requests for a brand-new session_id
        # can't each create their own separate Agent.
        self._creation_lock = asyncio.Lock()

    async def _get_or_create(self, session_id: str) -> tuple[Agent, asyncio.Lock]:
        if session_id in self._agents:
            return self._agents[session_id], self._locks[session_id]

        async with self._creation_lock:
            # Re-check: another request may have created it while we waited.
            if session_id not in self._agents:
                context = ConversationContext(llm_client=self.llm_client)
                # If a save file already exists for this session_id, resume it
                # instead of starting fresh (mirrors the CLI's resume flow).
                context.load_session(session_id)

                agent = Agent(
                    self.llm_client,
                    context,
                    tools=tools,
                    embeddings_client=self.embeddings_client
                )
                self._agents[session_id] = agent
                self._locks[session_id] = asyncio.Lock()

        return self._agents[session_id], self._locks[session_id]

    async def send_message(self, session_id: str, message: str) -> str:
        """
        Routes a user message to the right session's Agent, creating that
        session on first use. Autosaves after every turn, same as the CLI.
        """
        agent, lock = await self._get_or_create(session_id)
        async with lock:
            reply = await agent.process_message(message)
            agent.context.save_session(session_id)
            return reply

    def _get_context(self, session_id: str) -> ConversationContext | None:
        """
        Returns the ConversationContext for a session: the live in-memory
        one if the session has already exchanged a message in this process,
        otherwise a fresh one loaded straight from its saved JSON file on
        disk. Returns None if the session doesn't exist anywhere.

        This lets the web UI browse/export a session's history *before*
        the user has sent it a first live message in the current process
        — without this fallback, a session that only exists on disk would
        404 until send_message() had been called for it at least once.
        """
        if session_id in self._agents:
            return self._agents[session_id].context

        temp_context = ConversationContext(llm_client=self.llm_client)
        if temp_context.load_session(session_id):
            return temp_context
        return None

    def get_history(self, session_id: str):
        context = self._get_context(session_id)
        if context is None:
            return None
        return context.get_history()

    def get_stats(self, session_id: str):
        context = self._get_context(session_id)
        if context is None:
            return None
        return context.get_total_tokens_consumed()

    def export_markdown(self, session_id: str) -> str | None:
        """
        Builds a Markdown transcript (user/assistant turns only) for a
        session, in-memory — no temp file needed, unlike
        ConversationContext.export_history() which writes to disk.
        """
        context = self._get_context(session_id)
        if context is None:
            return None

        lines = [f"# Conversation export ({len(context.get_history())} messages)\n"]
        for msg in context.get_history():
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content") or ""
            speaker = "**You**" if role == "user" else "**AI**"
            lines.append(f"{speaker}: {content}\n")
        return "\n".join(lines)

    def list_active_sessions(self) -> list[str]:
        return list(self._agents.keys())