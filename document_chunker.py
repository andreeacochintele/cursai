import json
from config import CHUNK_SIZE
from utils import count_tokens

class DocumentChunker:
    """
    Handles reading raw Markdown files and dividing them into semantic chunks
    based on word count, keeping track of token counts for each chunk.
    """
    def give_chunks(self,content, document_id):

        """
        Splits a text document into chunks of CHUNK_SIZE words.
        Attached metadata like document_id, index, and calculated token count.
        
        """
        chunks = []
        # We split the document in words
        words = content.split()
        
        # Iterate through words in steps of CHUNK_SIZE
        for i in range(0, len(words), CHUNK_SIZE):
            chunk_words = words[i:i + CHUNK_SIZE]
            # Reconstruct the text by putting one white space between words
            chunk_text = " ".join(chunk_words)
    
            chunk_index = i // CHUNK_SIZE
            #Measure the actual token size of this chunk
            token_count = count_tokens(chunk_text)


            dictionary = {
                "document_id": document_id,
                "chunk_index": chunk_index,
                "content": chunk_text,
                "token_count":token_count
            }
            #print("Dictionar--- document_chunker", dictionary)
            chunks.append(dictionary)
        
        return chunks

    def read_documents(self,path):
        """
        Load the document registry for a specific category and processes eligible
        Markdown documents into chunks
        """


        chunks = []
        # Read the registry of documents
        try:
            with open(f"knowledge/{path}/registry.json", "r", encoding="utf-8") as f:
                results = json.load(f)
        except FileNotFoundError:
            print(f"Warning: The registry '{path}' was not found.")
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
                    print(f"Warning: {file_path} was not found.")

        return chunks

    def load_documents(self):
        """
        Concatenate document chunks from both facts and procedures
        """
        documents = [] 
        documents.extend(self.read_documents("facts"))       
        documents.extend(self.read_documents("procedures"))
        print(f"Total chunks loades: {len(documents)}")
        return documents
       
       