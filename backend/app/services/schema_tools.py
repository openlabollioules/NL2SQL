"""
Schema Tools Service
Provides validation, correction, and semantic understanding of database schema.
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ColumnMapping:
    """Represents a mapping from user term to actual column."""
    user_term: str
    table: str
    column: str
    data_type: str
    confidence: float
    needs_cast: bool = False
    cast_expression: str = ""


@dataclass
class SQLValidationResult:
    """Result of SQL validation."""
    is_valid: bool
    errors: List[str]
    suggestions: List[str]
    corrected_sql: Optional[str] = None


class SchemaToolsService:
    """Service for schema validation, correction and semantic understanding."""
    
    def __init__(self):
        # Lazy imports to avoid circular dependencies
        self._duckdb = None
        self._vector_store = None
        self._relationship_service = None
    
    @property
    def duckdb(self):
        if self._duckdb is None:
            from app.services.duckdb_service import get_duckdb_service
            self._duckdb = get_duckdb_service()
        return self._duckdb
    
    @property
    def vector_store(self):
        if self._vector_store is None:
            from app.services.vector_store import vector_store
            self._vector_store = vector_store
        return self._vector_store
    
    @property
    def relationships(self):
        if self._relationship_service is None:
            from app.services.relationship_service import relationship_service
            self._relationship_service = relationship_service
        return self._relationship_service
    
    # ==================== SCHEMA INTROSPECTION ====================
    
    def get_all_tables(self) -> List[str]:
        """Get list of all table names."""
        tables = self.duckdb.get_tables()
        return [t[0] for t in tables]
    
    def get_table_columns(self, table_name: str) -> Dict[str, str]:
        """Get columns and types for a table."""
        try:
            schema = self.duckdb.get_schema(table_name)
            return {col[0]: col[1] for col in schema}
        except Exception as e:
            logger.warning(f"Could not get schema for {table_name}: {e}")
            return {}
    
    def get_full_schema(self) -> Dict[str, Dict[str, str]]:
        """Get complete schema: {table: {column: type}}"""
        schema = {}
        for table in self.get_all_tables():
            schema[table] = self.get_table_columns(table)
        return schema
    
    # ==================== SEMANTIC COLUMN RESOLUTION ====================
    
    def resolve_user_concepts(self, user_query: str) -> List[ColumnMapping]:
        """
        Extract concepts from user query and map them to actual columns.
        
        Args:
            user_query: Natural language query
            
        Returns:
            List of ColumnMapping objects
        """
        # Common concepts to extract
        concept_patterns = [
            # Financial
            (r"chiffre\s*d'?\s*affaire|ca\b|montant|total|somme", "amount"),
            (r"facture|invoice", "invoice"),
            (r"commande|order", "order"),
            (r"règlement|paiement|payment", "payment"),
            (r"dépense|expense", "expense"),
            # Entities
            (r"fournisseur|vendor|supplier", "supplier"),
            (r"client|customer", "customer"),
            (r"projet|project", "project"),
            (r"tâche|tache|task", "task"),
            (r"opération|operation", "operation"),
            # Time
            (r"année|an\b|year", "year"),
            (r"mois|month", "month"),
            (r"date", "date"),
            # Identifiers
            (r"numéro|numero|number|code", "identifier"),
        ]
        
        query_lower = user_query.lower()
        found_concepts = []
        
        for pattern, concept_type in concept_patterns:
            if re.search(pattern, query_lower):
                found_concepts.append(concept_type)
        
        # Now map concepts to actual columns using semantic search
        mappings = []
        for concept in found_concepts:
            mapping = self._map_concept_to_column(concept, user_query)
            if mapping:
                mappings.append(mapping)
        
        return mappings
    
    def _map_concept_to_column(self, concept_type: str, original_query: str) -> Optional[ColumnMapping]:
        """Map a concept type to the best matching column, considering query context."""
        
        query_lower = original_query.lower()
        
        # Determine context-based table filter
        table_filter = None
        if concept_type == "amount":
            # Amount context detection
            if "facture" in query_lower or "invoice" in query_lower:
                table_filter = "IA_Factures"
            elif "commande" in query_lower or "order" in query_lower:
                table_filter = "IA_Commandes"
            elif "dépense" in query_lower or "depense" in query_lower:
                table_filter = "IA_Depenses"
            elif "règlement" in query_lower or "reglement" in query_lower:
                table_filter = "IA_Reglements"
        elif concept_type == "year":
            # Year context detection
            if "facture" in query_lower:
                table_filter = "IA_Factures"
            elif "commande" in query_lower:
                table_filter = "IA_Commandes"
        elif concept_type == "supplier":
            # Supplier is typically in IA_Commandes
            table_filter = "IA_Commandes"
        
        # Define search queries for each concept type
        search_queries = {
            "amount": "montant valeur prix total EUR ligne",
            "invoice": "facture numéro",
            "order": "commande numéro",
            "payment": "règlement paiement montant",
            "expense": "dépense montant coût",
            "supplier": "fournisseur nom vendor",
            "customer": "client nom customer",
            "project": "projet identifiant code ID",
            "task": "tâche code identifiant ID",
            "operation": "opération code identifiant",
            "year": "date année",
            "month": "date mois",
            "date": "date création",
            "identifier": "numéro code identifiant",
        }
        
        query = search_queries.get(concept_type, concept_type)
        
        # Use semantic search with optional table filter
        results = self.vector_store.semantic_column_search(query, table_filter=table_filter, n_results=5)
        
        if not results:
            # Fallback without filter
            results = self.vector_store.semantic_column_search(query, n_results=3)
        
        if not results:
            return None
        
        # For amounts, prefer columns with MONTANT_LIGNE (avoid EUR which may be corrupted)
        best = results[0]
        if concept_type == "amount":
            for r in results:
                col_lower = r['column'].lower()
                # Prefer MONTANT_LIGNE but NOT MONTANT_LIGNE_EUR (often corrupted in CSV)
                if 'montant_ligne' in col_lower and 'eur' not in col_lower:
                    best = r
                    break
                # Fallback to MONTANT without EUR
                elif 'montant' in col_lower and 'eur' not in col_lower:
                    best = r
        
        # Determine if casting is needed
        needs_cast = False
        cast_expr = ""
        data_type = best.get('data_type', '').upper()
        column = best['column']
        
        # Amount columns always need CAST for French locale
        if concept_type == "amount":
            needs_cast = True
            cast_expr = f"CAST(REPLACE({column}, ',', '.') AS DOUBLE)"
        elif concept_type == "year":
            if 'DATE' in data_type or 'TIMESTAMP' in data_type:
                needs_cast = True
                cast_expr = f"YEAR({column})"
            else:
                cast_expr = column
        
        return ColumnMapping(
            user_term=concept_type,
            table=best['table'],
            column=column,
            data_type=data_type,
            confidence=best['similarity'],
            needs_cast=needs_cast,
            cast_expression=cast_expr if needs_cast else best['column']
        )
    
    # ==================== SQL VALIDATION ====================
    
    def validate_sql(self, sql: str) -> SQLValidationResult:
        """
        Validate SQL against the actual schema.
        
        Returns validation result with errors and suggestions.
        """
        errors = []
        suggestions = []
        
        schema = self.get_full_schema()
        all_tables = list(schema.keys())
        all_columns = {}
        for table, cols in schema.items():
            for col in cols:
                if col not in all_columns:
                    all_columns[col] = []
                all_columns[col].append(table)
        
        # Extract tables referenced in SQL
        table_pattern = r'\bFROM\s+(["\w]+)|\bJOIN\s+(["\w]+)'
        referenced_tables = re.findall(table_pattern, sql, re.IGNORECASE)
        referenced_tables = [t[0] or t[1] for t in referenced_tables]
        referenced_tables = [t.strip('"') for t in referenced_tables]
        
        # Validate tables
        for table in referenced_tables:
            if table not in all_tables:
                # Find similar table
                similar = self._find_similar_name(table, all_tables)
                errors.append(f"Table '{table}' does not exist")
                if similar:
                    suggestions.append(f"Did you mean '{similar}'?")
        
        # Extract columns referenced in SQL (simplified)
        # This is a basic extraction - could be improved with proper SQL parsing
        col_pattern = r'(?:SELECT|WHERE|GROUP BY|ORDER BY|ON)\s+([^FROM]+)'
        
        # Check for syntax using DuckDB EXPLAIN
        try:
            self.duckdb.conn.sql(f"EXPLAIN {sql}")
            is_valid = True
        except Exception as e:
            is_valid = False
            error_msg = str(e)
            errors.append(f"Syntax error: {error_msg}")
            
            # Try to extract column name from error
            col_match = re.search(r'column "(\w+)" not found|"(\w+)" not found', error_msg, re.IGNORECASE)
            if col_match:
                bad_col = col_match.group(1) or col_match.group(2)
                # Find similar column using semantic search
                similar_cols = self.vector_store.semantic_column_search(bad_col, n_results=1)
                if similar_cols:
                    best = similar_cols[0]
                    suggestions.append(f"Column '{bad_col}' not found. Did you mean '{best['column']}' from table '{best['table']}'?")
        
        return SQLValidationResult(
            is_valid=is_valid and len(errors) == 0,
            errors=errors,
            suggestions=suggestions
        )
    
    def _find_similar_name(self, name: str, candidates: List[str]) -> Optional[str]:
        """Find the most similar name from candidates."""
        name_lower = name.lower()
        
        # Exact match (case insensitive)
        for c in candidates:
            if c.lower() == name_lower:
                return c
        
        # Partial match
        for c in candidates:
            if name_lower in c.lower() or c.lower() in name_lower:
                return c
        
        return None
    
    # ==================== SQL CORRECTION ====================
    
    def correct_sql(self, sql: str, error_message: str) -> Tuple[str, List[str]]:
        """
        Attempt to correct SQL based on error message.
        
        Returns:
            Tuple of (corrected_sql, list of changes made)
        """
        changes = []
        corrected = sql
        
        schema = self.get_full_schema()
        all_tables = list(schema.keys())
        
        # 1. Fix table names
        table_error = re.search(r'Table.*"(\w+)".*not found|Table with name (\w+) does not exist', error_message, re.IGNORECASE)
        if table_error:
            bad_table = table_error.group(1) or table_error.group(2)
            correct_table = self._find_similar_name(bad_table, all_tables)
            if correct_table:
                corrected = re.sub(rf'\b{bad_table}\b', correct_table, corrected, flags=re.IGNORECASE)
                changes.append(f"Replaced table '{bad_table}' with '{correct_table}'")
        
        # 2. Fix column names
        col_error = re.search(r'column "(\w+)" not found|Referenced column "(\w+)" not found', error_message, re.IGNORECASE)
        if col_error:
            bad_col = col_error.group(1) or col_error.group(2)
            
            # Find which table this column should be from
            # First, try semantic search
            results = self.vector_store.semantic_column_search(bad_col, n_results=1)
            if results:
                best = results[0]
                corrected = re.sub(rf'\b{bad_col}\b', best['column'], corrected, flags=re.IGNORECASE)
                changes.append(f"Replaced column '{bad_col}' with '{best['column']}' from {best['table']}")
        
        return corrected, changes
    
    # ==================== JOIN PATH FINDING ====================
    
    def get_required_joins(self, tables: List[str]) -> List[str]:
        """
        Find the minimal JOIN path between tables.
        
        Args:
            tables: List of table names that need to be joined
            
        Returns:
            List of JOIN clauses
        """
        if len(tables) <= 1:
            return []
        
        rels = self.relationships.get_relationships()
        joins = []
        joined_tables = {tables[0]}
        
        # Build direct relationships map
        rel_map = {}
        for rel in rels:
            key1 = (rel['table_source'], rel['table_target'])
            key2 = (rel['table_target'], rel['table_source'])
            rel_map[key1] = rel
            rel_map[key2] = {
                'table_source': rel['table_target'],
                'column_source': rel['column_target'],
                'table_target': rel['table_source'],
                'column_target': rel['column_source']
            }
        
        # Greedily add tables via available relationships
        for target_table in tables[1:]:
            if target_table in joined_tables:
                continue
            
            # Find a relationship from any joined table to target
            for joined in joined_tables:
                key = (joined, target_table)
                if key in rel_map:
                    rel = rel_map[key]
                    join_clause = f"JOIN {target_table} ON {rel['table_source']}.{rel['column_source']} = {rel['table_target']}.{rel['column_target']}"
                    joins.append(join_clause)
                    joined_tables.add(target_table)
                    break
        
        return joins

    # ==================== QUERY BUILDING HELPERS ====================
    
    def build_select_clause(self, mappings: List[ColumnMapping], aggregations: Dict[str, str] = None) -> str:
        """
        Build SELECT clause from column mappings.
        
        Args:
            mappings: List of ColumnMapping
            aggregations: Dict mapping column to aggregation function (e.g., {"amount": "SUM"})
        """
        parts = []
        aggregations = aggregations or {}
        
        for m in mappings:
            col_expr = m.cast_expression
            
            if m.user_term in aggregations:
                agg = aggregations[m.user_term]
                col_expr = f"{agg}({col_expr})"
            
            alias = m.user_term.replace(" ", "_")
            parts.append(f"{col_expr} AS {alias}")
        
        return ", ".join(parts)
    
    def get_join_path(self, table1: str, table2: str) -> Optional[str]:
        """
        Get JOIN clause between two tables based on defined relationships.
        """
        rels = self.relationships.get_relationships()
        
        for rel in rels:
            if rel['table_source'] == table1 and rel['table_target'] == table2:
                return f"JOIN {table2} ON {table1}.{rel['column_source']} = {table2}.{rel['column_target']}"
            elif rel['table_source'] == table2 and rel['table_target'] == table1:
                return f"JOIN {table2} ON {table2}.{rel['column_source']} = {table1}.{rel['column_target']}"
        
        return None
    
    def suggest_query_structure(self, user_query: str) -> Dict:
        """
        Analyze user query and suggest SQL structure.
        
        Returns dict with suggested tables, columns, aggregations, grouping, joins.
        """
        mappings = self.resolve_user_concepts(user_query)
        
        if not mappings:
            return {"error": "Could not understand query concepts"}
        
        # Get all unique tables involved
        all_tables = list(set(m.table for m in mappings))
        
        # Determine primary table based on context
        query_lower = user_query.lower()
        primary_table = None
        
        # Context-based primary table selection
        if "facture" in query_lower:
            for t in all_tables:
                if "facture" in t.lower():
                    primary_table = t
                    break
        elif "commande" in query_lower:
            for t in all_tables:
                if "commande" in t.lower():
                    primary_table = t
                    break
        
        # Fallback: table with most mapped columns
        if not primary_table:
            table_counts = {}
            for m in mappings:
                table_counts[m.table] = table_counts.get(m.table, 0) + 1
            primary_table = max(table_counts, key=table_counts.get) if table_counts else None
        
        # Get required JOINs
        required_joins = []
        if len(all_tables) > 1 and primary_table:
            # Reorder tables with primary first
            ordered_tables = [primary_table] + [t for t in all_tables if t != primary_table]
            required_joins = self.get_required_joins(ordered_tables)
        
        # Determine aggregations
        aggregations = {}
        
        if any(word in query_lower for word in ['total', 'somme', 'sum', 'chiffre']):
            for m in mappings:
                if m.user_term == 'amount':
                    aggregations['amount'] = 'SUM'
        
        if any(word in query_lower for word in ['nombre', 'count', 'combien']):
            aggregations['count'] = 'COUNT'
        
        # Determine grouping
        group_by = []
        for m in mappings:
            if m.user_term not in aggregations and m.user_term != 'amount':
                group_by.append(m)
        
        return {
            "primary_table": primary_table,
            "mappings": mappings,
            "aggregations": aggregations,
            "group_by": group_by,
            "suggested_tables": all_tables,
            "required_joins": required_joins
        }


# Singleton instance
schema_tools = SchemaToolsService()
