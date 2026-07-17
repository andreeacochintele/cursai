import tiktoken
from config import EMBEDDINGS_MODEL


# Initialize the encoder once at module startup to optimize performance
try:
    # Attempt to load the encoder specific to the configured LLM/Embedding model
    _encoder = tiktoken.encoding_for_model(EMBEDDINGS_MODEL)
except KeyError:
    # Fallback to cl100k_base (standard for GPT-4 and Ada/3 embeddings) if model is not recognized
    _encoder = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    """
    Safely counts the number of tokens in a given text using tiktoken.
    Prevents runtime crashes by handling None values and non-string inputs.
    """
    # If the value is none, return 0
    if text is None:
        return 0
    # Convert non-string inputs (e.g., dictionaries, lists) to string format 
    if not isinstance(text,str):
        try:
            text=str(text)
        except Exception:
            return 0
    # Handle empty or whitespace-only strings
    if not text.strip():
        return 0
    return len(_encoder.encode(text))