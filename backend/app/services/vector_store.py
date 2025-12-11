import chromadb
from chromadb.utils import embedding_functions
from app.services.ollama_service import ollama_service
from pathlib import Path
import uuid

class VectorStoreService:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.persist_directory = self.base_dir / "data" / "chroma_db"
        self.client = chromadb.PersistentClient(path=str(self.persist_directory))
        
        # We need a custom embedding function wrapper for ChromaDB to use LangChain's OllamaEmbeddings
        self.embedding_function = self._get_embedding_function()
        
        self.collection = self.client.get_or_create_collection(
            name="data_dictionary",
            embedding_function=self.embedding_function
        )

    def _get_embedding_function(self):
        # Wrapper to make LangChain embeddings compatible with ChromaDB
        class OllamaEmbeddingFunction(chromadb.EmbeddingFunction):
            def __call__(self, input: list[str]) -> list[list[float]]:
                return ollama_service.embeddings.embed_documents(input)
        return OllamaEmbeddingFunction()

    def add_documents(self, documents: list[str], metadatas: list[dict] = None):
        ids = [str(uuid.uuid4()) for _ in documents]
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def query(self, query_text: str, n_results: int = 5):
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )

vector_store = VectorStoreService()
