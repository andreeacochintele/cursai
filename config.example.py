"""
Application configuration.

This module contains all configurable settings used by the AI agent.

Future exercises may extend this file with:
- Model configuration
- API credentials
- Prompt templates
- Embedding settings
- Logging configuration
"""
AZURE_ENDPOINT = "link"
API_KEY = "key"
MODEL_NAME = "model"
CHUNK_SIZE = 150
EMBEDDINGS_MODEL = "bge-m3:latest"

EMBEDDINGS_ENDPOINT = "http://localhost:11434/api/embed"
MIN_SIMILARITY = 0.55
MAX_HISTORY_MESSAGES = 13
MAX_CONTEXT_TOKENS = 4000
KEEP_RECENT_MESSAGES = 6
MAX_RESPONSE_TOKENS = 2000

INPUT_TOKEN_PRICE_PER_MILLION = 2.0
OUTPUT_TOKEN_PRICE_PER_MILLION = 10.0

MODEL_ENDPOINT = (
    "http://localhost:11434/api/chat"
)



