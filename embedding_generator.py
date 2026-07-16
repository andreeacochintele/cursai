import json
import os

from document_chunker import DocumentChunker
from embeddings_client import EmbeddingsClient


class EmbeddingGenerator:

    def generate_embeddings(self):

        if os.path.exists("embeddings.json"):
            return

        chunker = DocumentChunker()
        chunks = chunker.load_documents()
        print("Chunks",chunks)
        client = EmbeddingsClient()

        embeddings_data = []

        for chunk in chunks:

            embedding = client.get_embedding(
                chunk["content"]
            )

            
            print("Embedding generated")
            print(len(embedding))


            embeddings_data.append(
                {
                    "document_id": chunk["document_id"],
                    "chunk_index": chunk["chunk_index"],
                    "content": chunk["content"],
                    "embedding": embedding
                }
            )
        print(len(embeddings_data))
        
        with open(
            "embeddings.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                embeddings_data,
                f,
                ensure_ascii=False,
                indent=4
            )
        