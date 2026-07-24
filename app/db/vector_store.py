from typing import List, Dict, Any

class BioVectorStore:
    def __init__(self, persist_directory="./chroma_db"):
        self.persist_directory = persist_directory
        
    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        """Adds scientific texts (disabled)."""
        pass
            
    def query(self, query_text: str, n_results=5):
        """Retrieves top context (disabled)."""
        return []

# Singleton instance
vector_store = BioVectorStore()
