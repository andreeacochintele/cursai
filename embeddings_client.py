import requests
import json

from config import EMBEDDINGS_MODEL, EMBEDDINGS_ENDPOINT, MIN_SIMILARITY



class EmbeddingsClient:
    def get_embedding(self, text: str) -> list[float]:
        response = requests.post(
            EMBEDDINGS_ENDPOINT,
            json={
                "model": EMBEDDINGS_MODEL,
                "input": text
            }
        )

        if not response.ok:
            print("STATUS:", response.status_code)
            print("BODY:", response.text)

        response.raise_for_status()
        return response.json()["embeddings"][0]

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Computes the cosine similarity between two embedding vectors.

        Returns a float in the range [-1, 1]:
        1.0 - vectors are semantically identical
        0.0 - vectors are unrelated
        -1.0 - vectors are semantically opposite

        General interpretation:
        > 0.9      very similar
        0.7 - 0.9  similar
        0.5 - 0.7  somewhat related
        < 0.5      likely unrelated

        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a ** 2 for a in vec1) ** 0.5
        magnitude2 = sum(b ** 2 for b in vec2) ** 0.5
        return dot_product / (magnitude1 * magnitude2)
    

    def semantic_search(self, user_question: str):
        try:
            with open("embeddings.json", "r", encoding="utf-8") as f:
                embeddings_data = json.load(f)  # Acum avem o listă de dicționare Python
        except FileNotFoundError:
            print("Eroare: Fișierul 'embeddings.json' nu există. Rulează mai întâi generatorul!")
            return []

        # Generăm embedding-ul pentru întrebarea utilizatorului
        question_embedding = self.get_embedding(user_question)
        results = []
        
        # Calculăm similaritatea cu fiecare chunk salvat
        for chunk in embeddings_data:
            similarity = self.cosine_similarity(
                question_embedding,
                chunk["embedding"]
            )

            results.append({
                "document_id": chunk["document_id"],
                "chunk_index": chunk["chunk_index"],
                "similarity": similarity,
                "content": chunk["content"]
            })
            
        # Sortăm descrescător (reverse=True), ca cele mai mari similarități să fie primele!
        sorted_results = sorted(results, key=lambda x: x["similarity"], reverse=True) 

        # Filtrăm rezultatele care nu depășesc pragul minim de similaritate
        approved_results = []
        for chunk in sorted_results:
            if chunk["similarity"] >= MIN_SIMILARITY:
                approved_results.append(chunk)

        return approved_results
