"""
Vector Store Service
Enhanced semantic search for NL2SQL with rich column/table context.
"""
import chromadb
from chromadb.utils import embedding_functions
from app.services.ollama_service import ollama_service
from pathlib import Path
import uuid
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing vector embeddings of database schema."""
    
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.persist_directory = self.base_dir / "data" / "chroma_db"
        self.client = chromadb.PersistentClient(path=str(self.persist_directory))
        
        # Custom embedding function wrapper for ChromaDB
        self.embedding_function = self._get_embedding_function()
        
        self.collection = self.client.get_or_create_collection(
            name="data_dictionary",
            embedding_function=self.embedding_function
        )

    def _get_embedding_function(self):
        """Wrapper to make LangChain embeddings compatible with ChromaDB."""
        class OllamaEmbeddingFunction(chromadb.EmbeddingFunction):
            def __call__(self, input: list[str]) -> list[list[float]]:
                return ollama_service.embeddings.embed_documents(input)
        return OllamaEmbeddingFunction()

    def add_documents(
        self, 
        documents: List[str], 
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ):
        """Add documents to the vector store."""
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.debug(f"Added {len(documents)} documents to vector store")

    def query(
        self, 
        query_text: str, 
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict:
        """Query the vector store for relevant documents."""
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where
        )

    def clear_table_documents(self, table_name: str):
        """Remove all documents for a specific table."""
        try:
            # Get all document IDs for this table
            results = self.collection.get(
                where={"table": table_name}
            )
            
            if results and results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"Cleared {len(results['ids'])} documents for table {table_name}")
                return len(results['ids'])
            return 0
        except Exception as e:
            logger.warning(f"Error clearing documents for table {table_name}: {e}")
            return 0

    def clear_all_documents(self):
        """Remove all documents from the vector store."""
        try:
            # Get all documents
            results = self.collection.get()
            if results and results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"Cleared all {len(results['ids'])} documents from vector store")
                return len(results['ids'])
            return 0
        except Exception as e:
            logger.warning(f"Error clearing all documents: {e}")
            return 0

    def get_table_context(self, table_name: str) -> str:
        """Get all vectorized context for a specific table."""
        try:
            results = self.collection.get(
                where={"table": table_name}
            )
            
            if results and results['documents']:
                return "\n".join(results['documents'])
            return ""
        except Exception as e:
            logger.warning(f"Error getting context for table {table_name}: {e}")
            return ""

    def get_relevant_context(
        self, 
        query: str, 
        n_results: int = 5
    ) -> str:
        """
        Get relevant context for a natural language query.
        Returns formatted string ready to inject into prompts.
        """
        results = self.query(query, n_results=n_results)
        
        if not results or not results.get('documents') or not results['documents'][0]:
            return ""
        
        documents = results['documents'][0]
        metadatas = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0]
        
        # Format context with relevance scores
        context_parts = []
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
            # Similarity score (lower distance = more similar)
            similarity = max(0, 1 - dist) if dist else 1.0
            
            doc_type = meta.get('type', 'unknown') if meta else 'unknown'
            table = meta.get('table', '') if meta else ''
            
            context_parts.append(f"[{doc_type}] {doc}")
        
        return "\n".join(context_parts)

    def get_stats(self) -> Dict:
        """Get statistics about the vector store."""
        try:
            results = self.collection.get()
            
            # Count by type
            type_counts = {}
            table_counts = {}
            
            if results and results['metadatas']:
                for meta in results['metadatas']:
                    if meta:
                        doc_type = meta.get('type', 'unknown')
                        table = meta.get('table', 'unknown')
                        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
                        table_counts[table] = table_counts.get(table, 0) + 1
            
            return {
                "total_documents": len(results['ids']) if results else 0,
                "by_type": type_counts,
                "by_table": table_counts
            }
        except Exception as e:
            logger.warning(f"Error getting stats: {e}")
            return {"total_documents": 0, "by_type": {}, "by_table": {}}

    # ==================== SEMANTIC TOOLS ====================
    
    def semantic_column_search(
        self, 
        concept: str, 
        table_filter: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Find columns semantically matching a concept.
        Uses BGE-M3 embeddings to find relevant columns by meaning.
        
        Args:
            concept: The concept to search for (e.g., "montant facture", "code tâche", "année")
            table_filter: Optional table name to filter results
            n_results: Number of results to return
            
        Returns:
            List of dicts with {table, column, data_type, similarity, description}
        """
        try:
            where_filter = {"type": "column_description"}
            if table_filter:
                where_filter = {"$and": [
                    {"type": "column_description"},
                    {"table": table_filter}
                ]}
            
            results = self.collection.query(
                query_texts=[concept],
                n_results=n_results,
                where=where_filter
            )
            
            if not results or not results.get('metadatas') or not results['metadatas'][0]:
                return []
            
            columns = []
            for meta, doc, dist in zip(
                results['metadatas'][0], 
                results['documents'][0],
                results['distances'][0]
            ):
                similarity = max(0, 1 - dist) if dist else 1.0
                columns.append({
                    "table": meta.get('table', ''),
                    "column": meta.get('column', ''),
                    "data_type": meta.get('data_type', ''),
                    "similarity": round(similarity, 3),
                    "description": doc
                })
            
            return columns
        except Exception as e:
            logger.warning(f"Semantic column search failed: {e}")
            return []

    def find_table_for_concept(self, concept: str, n_results: int = 3) -> List[Dict]:
        """
        Find the most relevant table(s) for a given concept.
        
        Args:
            concept: The concept to search for (e.g., "factures fournisseur", "commandes")
            
        Returns:
            List of dicts with {table, similarity, description}
        """
        try:
            results = self.collection.query(
                query_texts=[concept],
                n_results=n_results,
                where={"type": "table_description"}
            )
            
            if not results or not results.get('metadatas') or not results['metadatas'][0]:
                return []
            
            tables = []
            for meta, doc, dist in zip(
                results['metadatas'][0],
                results['documents'][0],
                results['distances'][0]
            ):
                similarity = max(0, 1 - dist) if dist else 1.0
                tables.append({
                    "table": meta.get('table', ''),
                    "similarity": round(similarity, 3),
                    "description": doc
                })
            
            return tables
        except Exception as e:
            logger.warning(f"Find table for concept failed: {e}")
            return []

    def validate_column_exists(self, column_name: str, table_name: Optional[str] = None) -> Dict:
        """
        Check if a column exists and suggest corrections if not.
        
        Args:
            column_name: The column name to validate
            table_name: Optional table to search in
            
        Returns:
            Dict with {exists, exact_match, suggestions}
        """
        try:
            # First, try exact match
            where_filter = {"column": column_name}
            if table_name:
                where_filter = {"$and": [
                    {"column": column_name},
                    {"table": table_name}
                ]}
            
            exact_results = self.collection.get(where=where_filter)
            
            if exact_results and exact_results['ids']:
                meta = exact_results['metadatas'][0] if exact_results['metadatas'] else {}
                return {
                    "exists": True,
                    "exact_match": True,
                    "table": meta.get('table', ''),
                    "column": column_name,
                    "data_type": meta.get('data_type', ''),
                    "suggestions": []
                }
            
            # No exact match - search semantically for suggestions
            suggestions = self.semantic_column_search(column_name, table_name, n_results=3)
            
            return {
                "exists": False,
                "exact_match": False,
                "table": table_name or '',
                "column": column_name,
                "suggestions": suggestions
            }
        except Exception as e:
            logger.warning(f"Validate column failed: {e}")
            return {"exists": False, "exact_match": False, "suggestions": []}

    def get_column_mapping(self, user_terms: List[str]) -> Dict[str, Dict]:
        """
        Map user-friendly terms to actual column names.
        
        Args:
            user_terms: List of terms the user used (e.g., ["montant", "année", "fournisseur"])
            
        Returns:
            Dict mapping each term to best matching column info
        """
        mapping = {}
        for term in user_terms:
            results = self.semantic_column_search(term, n_results=1)
            if results:
                best = results[0]
                mapping[term] = {
                    "table": best['table'],
                    "column": best['column'],
                    "data_type": best['data_type'],
                    "confidence": best['similarity']
                }
            else:
                mapping[term] = None
        return mapping


# Singleton instance
vector_store = VectorStoreService()
