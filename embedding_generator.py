"""
Local Vector Database Generator.

This module loads the chunked documents, requests their vector embeddings 
via the Embeddings Client, and saves the serialized results to a local 
JSON database for semantic search retrieval.
"""

import json
import os
import logging

from document_chunker import DocumentChunker
from embeddings_client import EmbeddingsClient

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Manages the lifecycle of the local embeddings database.
    Prevents redundant API calls by verifying existing databases, 
    and serializes vector data with full document metadata.
    """

    async def generate_embeddings(self):
        """
        Processes all knowledge base files, generates their embeddings,
        and saves them locally to 'embeddings.json'.
        """
        # Skip generation if the local vector database already exists
        if os.path.exists("embeddings.json"):
            logger.info("embeddings.json already exists — skipping regeneration.")
            return

        # Load and chunk all dynamic documents
        chunker = DocumentChunker()
        chunks = chunker.load_documents()

        if not chunks:
            logger.warning("No document chunks found. Database generation aborted.")
            return

        logger.info("Found %d chunks. Generating embeddings...", len(chunks))
        client = EmbeddingsClient()
        embeddings_data = []

        # Process each chunk automatically
        for id, chunk in enumerate(chunks, 1):
            try:
                # Generate embedding vector for the current chunk's content
                embedding = await client.get_embedding(
                    chunk["content"]
                )
                # Append structured chunk metadata, content, token counts
                embeddings_data.append(
                    {
                        "document_id": chunk["document_id"],
                        "chunk_index": chunk["chunk_index"],
                        "content": chunk["content"],
                        "token_count": chunk.get("token_count", 0),  # Save the token count from chunker
                        "embedding": embedding
                    }
                )
                logger.info("Processed chunk %d/%d (ID: %s)", id, len(chunks), chunk['document_id'])
            except Exception as e:
                logger.error("Failed to generate embedding for chunk %d/%d: %s", id, len(chunks), e)

        logger.info("Saving %d vectors to 'embeddings.json'...", len(embeddings_data))
        try:
            with open("embeddings.json", "w", encoding="utf-8") as f:
                json.dump(
                    embeddings_data,
                    f,
                    ensure_ascii=False,
                    indent=4
                )
        except FileNotFoundError:
            logger.error("'embeddings.json' path is missing/invalid.")
            return []
        logger.info("Vector database initialized and saved successfully.")