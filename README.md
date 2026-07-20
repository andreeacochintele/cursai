# Wizzard of OS

A RAG-powered Linux sysadmin chatbot, built on Azure AI Foundry, with tool-calling and a minimal web chat UI.

## Features

- **Chat over HTTP** (FastAPI) or **CLI** — same agent, two front ends.
- **RAG**: internal knowledge base (company facts, support procedures) is chunked, embedded, and retrieved by semantic search on every message.
- **Tool calling**: the model can call read-only diagnostic tools (see below) instead of guessing.
- **Session persistence**: conversations are saved to disk as JSON and can be resumed, listed, and exported to Markdown.
- **Web UI**: single-file chat page (`static/index.html`) with quick-action chips, session browser, and live token/cost stats.

## Project structure

```
.
├── app.py                     # FastAPI app (web API + serves the chat page)
├── main.py                    # CLI entry point
├── agent.py                   # Orchestrates RAG + tool calls + LLM turns
├── llm_client.py               # Talks to the chat model (Azure AI Foundry via OpenAI SDK)
├── embeddings_client.py       # Talks to the embeddings deployment + cosine similarity search
├── embedding_generator.py     # Builds embeddings.json from the knowledge base (once)
├── document_chunker.py        # Splits knowledge base docs into chunks for embedding
├── conversation_context.py    # Message history, system prompt assembly, context compression
├── session_manager.py         # One Agent per session_id, for the web API
├── utils.py                   # Token counting (tiktoken)
├── config.py                  # Your local config — NOT committed, see Setup
├── config_example.py          # Template for config.py
├── requirements.txt
├── static/
│   └── index.html             # The web chat UI
├── tools/
│   ├── tool.py                 # Base Tool class
│   ├── tools.py                 # Registry — add new tools here
│   ├── lucky_number_tool.py
│   ├── service_status_tool.py   # Windows service status (PowerShell)
│   ├── service_logs_tool.py     # Windows Event Log lookup (PowerShell)
│   └── disk_usage_tool.py       # Disk space usage (PowerShell)
├── knowledge/
│   ├── prompts/identity.md      # The system prompt (persona, scope, rules)
│   ├── facts/                   # always_load:true docs (always in the system prompt)
│   └── procedures/              # always_load:false docs (retrieved via RAG)
├── embeddings.json            # Generated vector DB (gitignore this — regenerated on first run)
└── sessions/                  # Saved conversations, one JSON file per session_id (auto-created)
```

## Setup

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS/WSL
# .venv\Scripts\activate           # Windows cmd/PowerShell
```

> **WSL users:** create the venv on the native Linux filesystem (e.g. `~/projects/...`), not under `/mnt/c/...`. Venvs on the Windows-mounted filesystem are unreliable — pip installs can silently land outside the venv ("Defaulting to user installation because normal site-packages is not writeable").

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> If you hit `error: externally-managed-environment` (PEP 668) even inside an active venv, check `.venv/pyvenv.cfg` for `include-system-site-packages`. As a last resort inside a venv (never on system Python): `pip install --break-system-packages -r requirements.txt`.

### 3. Configure

```bash
cp config_example.py config.py
```

Edit `config.py`:

| Setting | Description |
|---|---|
| `AZURE_ENDPOINT` | Your Azure AI Foundry endpoint, e.g. `https://<resource>.services.ai.azure.com/openai/v1` |
| `API_KEY` | Your Azure AI Foundry API key |
| `MODEL_NAME` | Chat deployment name |
| `EMBEDDINGS_MODEL` | Embeddings deployment name (must be a separate deployment from the chat model) |
| `MIN_SIMILARITY` | Cosine similarity threshold for RAG matches (0–1) |
| `MAX_CONTEXT_TOKENS` / `KEEP_RECENT_MESSAGES` | Context window management |
| `INPUT_TOKEN_PRICE_PER_MILLION` / `OUTPUT_TOKEN_PRICE_PER_MILLION` | For the cost estimate shown in stats |

`config.py` is your local secrets file — don't commit it.

### 4. Corporate proxy (if applicable)

If your organization routes all HTTP traffic through a proxy (`HTTP_PROXY`/`HTTPS_PROXY`), make sure `localhost`/`127.0.0.1` are excluded, or any local service calls will be blocked or misrouted:

```bash
export NO_PROXY="localhost,127.0.0.1"
export no_proxy="localhost,127.0.0.1"
```

## Running

**Web (recommended):**
```bash
uvicorn app:app --reload
```
Open `http://127.0.0.1:8000/` for the chat UI, or `http://127.0.0.1:8000/docs` for the API reference.

**CLI:**
```bash
python main.py
```

On first run, both entry points build `embeddings.json` from the `knowledge/` folder (skipped on later runs if the file already exists — delete it to force a rebuild after editing knowledge docs).

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Chat UI |
| `POST` | `/chat` | `{session_id, message}` → `{session_id, reply}` |
| `GET` | `/sessions` | Lists saved (disk) and active (in-memory) sessions |
| `GET` | `/sessions/{id}/history` | User/assistant messages for a session |
| `GET` | `/sessions/{id}/stats` | Token usage + estimated cost |
| `GET` | `/sessions/{id}/export` | Downloads the session as Markdown |
| `GET` | `/health` | Liveness check |

## Tools

All tools are **read-only** — they inspect the system but never restart, stop, or modify anything. They currently run **PowerShell commands on the Windows machine hosting the bot** (there's no Linux host in this setup); if you later get SSH access to a real Linux server, `service_status`/`service_logs`/`disk_usage` are the ones to adapt (swap `subprocess` for an SSH-based call).

| Tool | What it does |
|---|---|
| `lucky_number` | Deterministic novelty number from today's date + a birth date. Not a sysadmin tool — kept as a scope/permission test case. |
| `service_status` | `Get-Service` — is a Windows service running, stopped, what's its startup type. |
| `service_logs` | `Get-WinEvent` — recent System/Application log entries mentioning a service. |
| `disk_usage` | `Get-PSDrive` — used/free space per drive. |

To add a new tool: create `tools/your_tool.py` following the pattern in `tools/lucky_number_tool.py` (a `Tool(name, description, parameters, callback)` instance), then import and register it in `tools/tools.py`.

## Knowledge base / RAG

- `knowledge/prompts/identity.md` — the system prompt: persona, scope rules (what the bot will/won't answer), style, safety rules. Always sent in full.
- `knowledge/facts/*.md` + `registry.json` — docs with `always_load: true` are always injected into the system prompt (no retrieval needed).
- `knowledge/procedures/*.md` + `registry.json` — docs with `always_load: false` are chunked, embedded, and retrieved via semantic search per message.

To add a knowledge doc: drop a `.md` file in the right folder and add an entry to that folder's `registry.json` with a matching `id`. Delete `embeddings.json` afterwards so it gets rebuilt with the new content.


