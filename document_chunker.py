import json
from config import CHUNK_SIZE

class DocumentChunker:

    def give_chunks(self,content, document_id):
        chunks = []
        # Împărțim textul în cuvinte individuale pentru a nu le tăia la jumătate
        words = content.split()
        
        # Parcurgem cuvintele în pași de mărimea CHUNK_SIZE
        for i in range(0, len(words), CHUNK_SIZE):
            chunk_words = words[i:i + CHUNK_SIZE]
            # Reconstruim textul punând spații între cuvinte
            chunk_text = " ".join(chunk_words)
            
            chunk_index = i // CHUNK_SIZE
            
            dictionar = {
                "document_id": document_id,
                "chunk_index": chunk_index,
                "content": chunk_text
            }
            print("Dictionar--- document_chunker", dictionar)
            chunks.append(dictionar)
        
        return chunks

    def read_documents(self,path):
        chunks = []
        # Încărcăm registrul de documente
        try:
            with open(f"knowledge/{path}/registry.json", "r", encoding="utf-8") as f:
                results = json.load(f)
        except FileNotFoundError:
            print(f"Atenție: Registrul pentru '{path}' nu a fost găsit.")
            return chunks
        
        for document in results:
            # Încărcăm doar documentele care NU au "always_load" setat pe True (sau conform logicii tale)
            if not document.get("always_load", False):
                file_path = f"knowledge/{path}/{document['id']}.md"
                try:
                    with open(file_path, "r", encoding="utf-8") as f:    
                        result = f.read()
                        chunks.extend(self.give_chunks(result, document['id']))
                except FileNotFoundError:
                    print(f"Fișierul {file_path} nu a fost găsit.")

        return chunks

    def load_documents(self):

        documents = [] 
        documents.extend(self.read_documents("facts"))       
        documents.extend(self.read_documents("procedures"))
        print(f"S-au încărcat în total {len(documents)} chunk-uri.")
        return documents
       
       