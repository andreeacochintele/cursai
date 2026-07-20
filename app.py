"""
FastAPI web interface for the Wizzard of OS agent.

Run with:
    uvicorn app:app --reload

Docs available at:
    http://127.0.0.1:8000/docs   (Swagger UI, auto-generated)
    http://127.0.0.1:8000/redoc
"""
from contextlib import asynccontextmanager
import logging

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from llm_client import LLMClient
from embeddings_client import EmbeddingsClient
from embedding_generator import EmbeddingGenerator
from session_manager import SessionManager
from conversation_context import ConversationContext


# --- App state (created once at startup, shared by every request) ---
# Pydantic models below define exactly what a request body must look like.
# FastAPI validates incoming JSON against these automatically and returns
# a 422 error with a clear message if a field is missing or the wrong type
# — no manual "if not data.get('message')" checks needed, unlike Flask.

class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="Client-chosen identifier for the conversation")
    message: str = Field(..., min_length=1, description="The user's message to the agent")


class ChatResponse(BaseModel):
    session_id: str
    reply: str


class SessionStats(BaseModel):
    total_input: int
    total_output: int
    grand_total: int
    total_cost: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown hook. This is where we create the ONE shared httpx
    connection pool and the ONE shared LLM client, instead of a new
    connection per request (what the CLI + a naive "create client every
    call" version would do). Also runs the embeddings.json generation
    step, same as main.py did before entering the REPL loop.
    """
    async with httpx.AsyncClient() as shared_http_client:
        llm_client = LLMClient()
        embeddings_client = EmbeddingsClient(http_client=shared_http_client)

        # One-time knowledge base indexing (skipped if embeddings.json
        # already exists), same as EmbeddingGenerator did in main.py.
        # NOTE: EmbeddingGenerator.generate_embeddings() is still the
        # sync version from the original project (file I/O + calls the
        # embeddings client). Fine to run once, synchronously, before we
        # start serving traffic.
        await EmbeddingGenerator().generate_embeddings()

        app.state.session_manager = SessionManager(llm_client, embeddings_client)

        yield  # <-- app serves requests during this point

        await llm_client.aclose()


app = FastAPI(
    title="Wizzard of OS API",
    description="RAG-powered Linux sysadmin assistant",
    version="1.0.0",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serves the minimal chat page."""
    return FileResponse("static/index.html")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to a session's agent and get its reply.
    If session_id has never been seen before, a new session is created
    (or resumed from disk if a saved session with that id already exists).
    """
    session_manager: SessionManager = app.state.session_manager
    try:
        reply = await session_manager.send_message(request.session_id, request.message)
    except Exception as e:
        # Anything unexpected becomes a clean 500 instead of a stack trace
        # leaking to the client — logger.exception() automatically attaches
        # the full traceback to the log line, so it's still fully visible
        # server-side for debugging, without a manual traceback dump.
        logger.exception("/chat failed for session '%s'", request.session_id)
        raise HTTPException(status_code=500, detail=f"Agent failed to respond: {e}")

    return ChatResponse(session_id=request.session_id, reply=reply)


@app.get("/sessions")
async def list_sessions():
    """
    Lists sessions saved to disk (sessions/*.json) AND sessions currently
    active in memory for this running process.
    """
    return {
        "saved_on_disk": ConversationContext.list_sessions(),
        "active_in_memory": app.state.session_manager.list_active_sessions()
    }


@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """
    Returns the user/assistant message history for a session — whether it's
    already active in memory, or only saved on disk (sessions/*.json).
    """
    history = app.state.session_manager.get_history(session_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")
    # Filter to user/assistant turns only, mirroring the CLI's /history command
    return [m for m in history if m.get("role") in ("user", "assistant")]


@app.get("/sessions/{session_id}/stats", response_model=SessionStats)
async def get_session_stats(session_id: str):
    """Returns token usage and cost stats for a session (in-memory or on disk)."""
    stats = app.state.session_manager.get_stats(session_id)
    if stats is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")
    return stats


@app.get("/sessions/{session_id}/export")
async def export_session(session_id: str):
    """Downloads the session's user/assistant turns as a Markdown file."""
    markdown = app.state.session_manager.export_markdown(session_id)
    if markdown is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")
    return PlainTextResponse(
        markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{session_id}.md"'}
    )


@app.get("/health")
async def health():
    """Simple liveness check — useful for load balancers / uptime monitors."""
    return {"status": "ok"}