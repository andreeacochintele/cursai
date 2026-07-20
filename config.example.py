"""
Application configuration.

This module contains all configurable settings used by the AI agent.
Copy this file to config.py and fill in real values — config.py is your
local secrets file and should never be committed.

HOW TO SWITCH PROVIDERS
========================
Change the PROVIDER value below to "azure" or "ollama" and fill in the
matching profile. Everything else in the app (llm_client.py,
embeddings_client.py, cost tracking in conversation_context.py) adapts
automatically — no other file needs to change.

  - "azure"  -> for people who have an Azure AI Foundry subscription/API key.
  - "ollama" -> free, fully local, no API key needed. Install Ollama and
                pull a couple of models first (see README.md, section
                "Using Ollama instead of Azure").

This works because Ollama exposes an OpenAI-compatible API at
http://localhost:11434/v1, and both llm_client.py and embeddings_client.py
already talk to whichever endpoint is configured here via the standard
`openai` SDK.
"""

# ============================================================
# 1. PICK YOUR PROVIDER — this is the only line most people need to touch
# ============================================================
PROVIDER = "ollama"   # <-- change to "ollama" if you don't have an Azure API key

# ============================================================
# 2. Fill in the profile you're using (the other one can stay as a template)
# ============================================================
_PROFILES = {

    "azure": {
        # Requires an Azure AI Foundry resource + API key.
        "endpoint": "https://<your-resource>.services.ai.azure.com/openai/v1",
        "api_key": "<your-azure-api-key>",
        "model_name": "<your-chat-deployment-name>",             # e.g. "gpt-4o-mini"
        "embeddings_model": "<your-embeddings-deployment-name>",  # e.g. "text-embedding-3-large"
                                                                   # ^ must be a SEPARATE deployment from the chat model
        "token_limit_param": "max_completion_tokens",  # Azure/OpenAI's newer models expect this exact key name
        "input_price_per_million": 2.0,   # $ per 1M input tokens — check your actual pricing tier and adjust
        "output_price_per_million": 10.0,  # $ per 1M output tokens
    },

    "ollama": {
        # Free, runs fully on your own machine — no API key, no cost.
        # One-time setup:
        #   curl -fsSL https://ollama.com/install.sh | sh
        #   ollama pull llama3.1          # any tool-calling-capable chat model
        #   ollama pull nomic-embed-text  # an embeddings model
        #   ollama serve                  # keep this running in a terminal
        "endpoint": "http://localhost:11434/v1",
        "api_key": "ollama",         # ignored by Ollama, but the OpenAI SDK requires some non-empty string
        "model_name": "llama3.1",
        "embeddings_model": "nomic-embed-text",
        "token_limit_param": "max_tokens",  # Ollama's OpenAI-compatible layer expects the OLDER param name
        "input_price_per_million": 0.0,   # local = free
        "output_price_per_million": 0.0,
    },

}

if PROVIDER not in _PROFILES:
    raise ValueError(
        f"config.py: PROVIDER is set to '{PROVIDER}', but only "
        f"{list(_PROFILES.keys())} are defined below it. Fix the PROVIDER line above."
    )

_active = _PROFILES[PROVIDER]

# ============================================================
# 3. These exact variable names are what llm_client.py, embeddings_client.py
#    and conversation_context.py import — don't rename them, whichever
#    PROVIDER is active just fills them in differently.
#    (AZURE_ENDPOINT/API_KEY keep their original names for backward
#    compatibility with the rest of the codebase, even though they now
#    also carry the Ollama values when PROVIDER = "ollama".)
# ============================================================
AZURE_ENDPOINT = _active["endpoint"]
API_KEY = _active["api_key"]
MODEL_NAME = _active["model_name"]
EMBEDDINGS_MODEL = _active["embeddings_model"]
TOKEN_LIMIT_PARAM = _active["token_limit_param"]
INPUT_TOKEN_PRICE_PER_MILLION = _active["input_price_per_million"]
OUTPUT_TOKEN_PRICE_PER_MILLION = _active["output_price_per_million"]

# ============================================================
# Shared settings — apply to both profiles, tune freely regardless of provider
# ============================================================
CHUNK_SIZE = 150
MIN_SIMILARITY = 0.55
MAX_HISTORY_MESSAGES = 13
MAX_CONTEXT_TOKENS = 4000
KEEP_RECENT_MESSAGES = 6
MAX_RESPONSE_TOKENS = 2000