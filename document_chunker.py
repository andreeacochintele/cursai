import json
import logging

from config import CHUNK_SIZE, CHUNK_OVERLAP
from utils import count_tokens

logger = logging.getLogger(__name__)


class DocumentChunker:
    """
    Handles reading raw Markdown files and dividing them into semantic chunks
    based on word count, keeping track of token counts for each chunk.
    """
    def give_chunks(self, content, document_id):
        """
        Splits text into CHUNK_SIZE-word chunks, stepping by
        (CHUNK_SIZE - CHUNK_OVERLAP) so consecutive chunks overlap —
        keeps sentences that fall on a chunk boundary from getting cut
        in half and losing retrieval relevance.
        """
        chunks = []
        words = content.split()
        if not words:
            return chunks

        # guard against CHUNK_OVERLAP >= CHUNK_SIZE (step would be <= 0)
        step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)

        for i in range(0, len(words), step):
            chunk_words = words[i:i + CHUNK_SIZE]
            if not chunk_words:
                break

            chunk_text = " ".join(chunk_words)
            chunk_index = i // step
            token_count = count_tokens(chunk_text)

            chunks.append({
                "document_id": document_id,
                "chunk_index": chunk_index,
                "content": chunk_text,
                "token_count": token_count
            })

            # stop once we hit the end, otherwise overlap adds a redundant last chunk
            if i + CHUNK_SIZE >= len(words):
                break

        return chunks

    def read_documents(self, path):
        """
        Load the document registry for a specific category and processes eligible
        Markdown documents into chunks
        """
        chunks = []
        try:
            with open(f"knowledge/{path}/registry.json", "r", encoding="utf-8") as f:
                results = json.load(f)
        except FileNotFoundError:
            logger.warning("Registry '%s' was not found.", path)
            return chunks

        for document in results:
            # Load the document that have "always_load" as false
            if not document.get("always_load", False):
                file_path = f"knowledge/{path}/{document['id']}.md"
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        result = f.read()
                        chunks.extend(self.give_chunks(result, document['id']))
                except FileNotFoundError:
                    logger.warning("Document file '%s' was not found.", file_path)

        return chunks

    def load_documents(self):
        """
        Concatenate document chunks from both facts and procedures
        """
        documents = []
        documents.extend(self.read_documents("facts"))
        documents.extend(self.read_documents("procedures"))
        logger.info("Total chunks loaded: %d", len(documents))
        return documents