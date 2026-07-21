"""
Session management for the multi-user API.

One (Agent, ConversationContext) pair per session_id, kept in memory.
Each session gets its own asyncio.Lock so concurrent requests for the
same session_id don't interleave and corrupt its history; different
sessions run fully in parallel.
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
        # guards against two simultaneous first-requests creating duplicate agents
        self._creation_lock = asyncio.Lock()

    async def _get_or_create(self, session_id: str) -> tuple[Agent, asyncio.Lock]:
        if session_id in self._agents:
            return self._agents[session_id], self._locks[session_id]

        async with self._creation_lock:
            # re-check in case another request created it while we waited
            if session_id not in self._agents:
                context = ConversationContext(llm_client=self.llm_client)
                # resumes from disk if a save file already exists
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
        Returns the live context if the session's already active in memory,
        otherwise loads it fresh from disk. None if it doesn't exist at all.
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
        """Builds a Markdown transcript (user/assistant turns only), in-memory."""
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