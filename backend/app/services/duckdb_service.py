"""
DuckDB Service
Handles all database operations using DuckDB with schema caching.
"""
import logging
import os
import re
import time
from pathlib import Path
from functools import lru_cache
from typing import Optional, Dict, Any
from threading import RLock

import duckdb

from app.core.config import settings

logger = logging.getLogger(__name__)

# Schema cache TTL in seconds
SCHEMA_CACHE_TTL = 60


class DuckDBService:
    """Service for managing DuckDB database operations."""
    
    # Whitelist pattern for table names (alphanumeric + underscore)
    TABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    
    # Default result limit to prevent memory issues
    DEFAULT_LIMIT = 1000
    
    def __init__(self):
        # backend/app/services/duckdb_service.py -> backend/
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.db_path = self.base_dir / "data" / "warehouse.db"
        self.uploads_dir = self.base_dir / "data" / "uploads"
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
        
        self.conn = duckdb.connect(str(self.db_path))
        
        # Schema cache
        self._schema_cache: Dict[str, Any] = {}
        self._schema_cache_time: float = 0
        self._cache_lock = RLock()
        
        # Connection lock for thread-safe access to DuckDB (RLock allows reentrant calls)
        self._conn_lock = RLock()
        
        # Auto-load existing CSVs if tables are missing
        self._restore_tables_from_uploads()

    def _restore_tables_from_uploads(self):
        """Restore tables from uploaded CSV files on startup."""
        try:
            existing_tables = [t[0] for t in self.get_tables()]
            for file_path in self.uploads_dir.glob("*.csv"):
                table_name = self._sanitize_table_name(file_path.stem)
                if table_name and table_name not in existing_tables:
                    logger.info(f"Restoring table {table_name} from {file_path}")
                    self.load_csv(str(file_path), table_name)
        except Exception as e:
            logger.exception(f"Error restoring tables: {e}")

    def _sanitize_table_name(self, name: str) -> Optional[str]:
        """
        Sanitize a table name to ensure it's safe for SQL.
        Returns None if the name cannot be sanitized.
        """
        # Replace common problematic characters
        sanitized = name.replace('-', '_').replace(' ', '_').replace('.', '_')
        
        # Remove any remaining invalid characters
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', sanitized)
        
        # Ensure it starts with a letter or underscore
        if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
            sanitized = '_' + sanitized
        
        # Validate against pattern
        if sanitized and self.TABLE_NAME_PATTERN.match(sanitized):
            return sanitized
        
        logger.warning(f"Could not sanitize table name: {name}")
        return None

    def validate_table_name(self, table_name: str) -> bool:
        """
        Validate that a table name is safe for SQL operations.
        Raises ValueError if invalid.
        """
        if not table_name:
            raise ValueError("Table name cannot be empty")
        
        if not self.TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(
                f"Invalid table name: {table_name}. "
                "Table names must start with a letter or underscore and contain only alphanumeric characters and underscores."
            )
        
        # Check for SQL keywords (basic protection)
        sql_keywords = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 
                       'ALTER', 'TRUNCATE', 'TABLE', 'DATABASE', 'UNION', 'JOIN'}
        if table_name.upper() in sql_keywords:
            raise ValueError(f"Table name cannot be a SQL keyword: {table_name}")
        
        return True

    def execute_query(self, query: str, limit: Optional[int] = None):
        """
        Execute a SQL query and return results with columns.
        Automatically applies a LIMIT if not present to prevent memory issues.
        """
        if limit is None:
            limit = self.DEFAULT_LIMIT
            
        try:
            # Add LIMIT if not present (only for SELECT queries)
            query_upper = query.strip().upper()
            if query_upper.startswith('SELECT') and 'LIMIT' not in query_upper:
                query = f"SELECT * FROM ({query}) AS subq LIMIT {limit}"
            
            with self._conn_lock:
                relation = self.conn.sql(query)
                columns = relation.columns
                result = relation.fetchall()
            
            # Convert to list of dicts
            data = []
            for row in result:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # Handle special types for JSON serialization
                    if hasattr(value, 'isoformat'):  # datetime
                        value = value.isoformat()
                    elif isinstance(value, (bytes, bytearray)):
                        value = value.decode('utf-8', errors='replace')
                    row_dict[col] = value
                data.append(row_dict)
                
            return {"columns": list(columns), "data": data}
        except Exception as e:
            logger.exception(f"Error executing query: {e}")
            raise

    def validate_query(self, query: str) -> tuple[bool, str]:
        """
        Validate SQL syntax without executing.
        Returns (is_valid, error_message).
        """
        try:
            # Use EXPLAIN to validate syntax
            with self._conn_lock:
                self.conn.sql(f"EXPLAIN {query}")
            return True, ""
        except Exception as e:
            return False, str(e)

    def load_csv(self, file_path: str, table_name: str):
        """Load a CSV file into a DuckDB table."""
        self.validate_table_name(table_name)
        try:
            # Use identifier quoting for safety
            query = f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM read_csv_auto(\'{file_path}\')'
            with self._conn_lock:
                self.conn.execute(query)
            # Invalidate schema cache
            self._invalidate_schema_cache()
            logger.info(f"Successfully loaded {file_path} into table {table_name}")
            return f"Successfully loaded {file_path} into table {table_name}"
        except Exception as e:
            logger.exception(f"Error loading CSV: {e}")
            raise

    def _invalidate_schema_cache(self):
        """Invalidate the schema cache."""
        with self._cache_lock:
            self._schema_cache = {}
            self._schema_cache_time = 0
            logger.debug("Schema cache invalidated")

    def _is_cache_valid(self) -> bool:
        """Check if schema cache is still valid."""
        return (time.time() - self._schema_cache_time) < SCHEMA_CACHE_TTL

    def get_tables(self):
        """Return a list of tables in the database."""
        with self._conn_lock:
            return self.conn.execute("SHOW TABLES").fetchall()

    def get_schema(self, table_name: str):
        """Return the schema of a specific table."""
        self.validate_table_name(table_name)
        with self._conn_lock:
            return self.conn.execute(f'DESCRIBE "{table_name}"').fetchall()

    def get_all_schemas(self, use_cache: bool = True) -> str:
        """Return a formatted string of all table schemas with caching."""
        cache_key = "all_schemas"
        
        # Check cache
        if use_cache:
            with self._cache_lock:
                if self._is_cache_valid() and cache_key in self._schema_cache:
                    logger.debug("Returning cached schema")
                    return self._schema_cache[cache_key]
        
        # Build schema string
        tables = self.get_tables()
        schema_parts = []
        
        for table in tables:
            table_name = table[0]
            try:
                schema = self.get_schema(table_name)
                schema_str = f"Table: {table_name}\nColumns:\n"
                for col in schema:
                    # col[0] is name, col[1] is type
                    schema_str += f"  - {col[0]} ({col[1]})\n"
                schema_parts.append(schema_str)
            except Exception as e:
                logger.warning(f"Could not get schema for table {table_name}: {e}")
        
        result = "\n".join(schema_parts)
        
        # Update cache
        with self._cache_lock:
            self._schema_cache[cache_key] = result
            self._schema_cache_time = time.time()
            
        return result

    def get_table_content(self, table_name: str, limit: int = 50):
        """Return the content of a table with a limit."""
        self.validate_table_name(table_name)
        try:
            with self._conn_lock:
                schema = self.get_schema(table_name)
                columns = [col[0] for col in schema]
                
                result = self.conn.execute(f'SELECT * FROM "{table_name}" LIMIT {int(limit)}').fetchall()
                
                data = []
                for row in result:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Handle special types for JSON serialization
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        elif isinstance(value, (bytes, bytearray)):
                            value = value.decode('utf-8', errors='replace')
                        row_dict[col] = value
                    data.append(row_dict)
                    
                return {"columns": columns, "data": data}
        except Exception as e:
            logger.exception(f"Error fetching table content: {e}")
            raise

    def delete_table(self, table_name: str):
        """Delete a table from the database."""
        self.validate_table_name(table_name)
        try:
            with self._conn_lock:
                self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            logger.info(f"Successfully deleted table {table_name}")
            return f"Successfully deleted table {table_name}"
        except Exception as e:
            logger.exception(f"Error deleting table {table_name}: {e}")
            raise

    def get_row_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        self.validate_table_name(table_name)
        with self._conn_lock:
            result = self.conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
            return result[0] if result else 0


# Singleton pattern with explicit maxsize
@lru_cache(maxsize=1)
def get_duckdb_service() -> DuckDBService:
    """Get or create the DuckDB service singleton."""
    return DuckDBService()


# Backward compatibility alias
duckdb_service = get_duckdb_service()
