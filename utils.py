import tiktoken
from config import EMBEDDINGS_MODEL

try:
    # Încercăm să luăm encoder-ul potrivit pentru modelul configurat de tine
    _encoder = tiktoken.encoding_for_model(EMBEDDINGS_MODEL)
except KeyError:
    # Dacă modelul nu este listat direct în tiktoken, folosim cl100k_base (standard pentru GPT-4/Embeddings)
    _encoder = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    """
    Numără tokenii dintr-un text folosind biblioteca tiktoken.
    Poate fi importată și folosită oriunde în proiect.
    """
    #daca valoarea seste none, returnam 0
    if text is None:
        return 0
    # daca am primit dictionar sau lista in loc de text returnam 0
    if not isinstance(text,str):
        try:
            text=str(text)
        except Exception:
            return 0
    #daca string-ul este gol dupa curatare, returnam 0
    if not text.strip():
        return 0
    return len(_encoder.encode(text))