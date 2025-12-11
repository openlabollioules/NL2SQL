import duckdb
import os
from pathlib import Path
from app.core.config import settings
from functools import lru_cache
import re

class DuckDBService:
    def __init__(self):
        # backend/app/services/duckdb_service.py -> backend/
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.db_path = self.base_dir / "data" / "warehouse.db"
        self.uploads_dir = self.base_dir / "data" / "uploads"
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
        
        self.conn = duckdb.connect(str(self.db_path))
        
        # Auto-load existing CSVs if tables are missing
        self._restore_tables_from_uploads()

    def _restore_tables_from_uploads(self):
        try:
            existing_tables = [t[0] for t in self.get_tables()]
            for file_path in self.uploads_dir.glob("*.csv"):
                table_name = file_path.stem
                if table_name not in existing_tables:
                    print(f"Restoring table {table_name} from {file_path}")
                    self.load_csv(str(file_path), table_name)
        except Exception as e:
            print(f"Error restoring tables: {e}")

    def execute_query(self, query: str):
        """Executes a SQL query and returns the result with columns."""
        try:
            # Use fetchall() to get data
            relation = self.conn.sql(query)
            columns = relation.columns
            result = relation.fetchall()
            
            # Convert to list of dicts
            data = []
            for row in result:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i]
                data.append(row_dict)
                
            return {"columns": columns, "data": data}
        except Exception as e:
            print(f"Error executing query: {e}")
            raise e

    def validate_table_name(self, table_name: str):
        # Allow almost anything to prevent 500s on weird filenames
        # Just prevent double quotes which break our SQL identifier quoting
        if '"' in table_name or ';' in table_name:
             raise ValueError(f"Invalid table name: {table_name}")

    def load_csv(self, file_path: str, table_name: str):
        """Loads a CSV file into a DuckDB table."""
        self.validate_table_name(table_name)
        try:
            # Quote table name to handle special chars
            query = f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM read_csv_auto(\'{file_path}\')'
            self.conn.execute(query)
            return f"Successfully loaded {file_path} into table {table_name}"
        except Exception as e:
            print(f"Error loading CSV: {e}")
            raise e

    def get_tables(self):
        """Returns a list of tables in the database."""
        return self.conn.execute("SHOW TABLES").fetchall()

    def get_schema(self, table_name: str):
        """Returns the schema of a specific table."""
        self.validate_table_name(table_name)
        return self.conn.execute(f'DESCRIBE "{table_name}"').fetchall()

    def get_all_schemas(self):
        """Returns a formatted string of all table schemas."""
        tables = self.get_tables()
        schema_str = ""
        for table in tables:
            table_name = table[0]
            schema = self.get_schema(table_name)
            schema_str += f"Table: {table_name}\nColumns:\n"
            for col in schema:
                # col[0] is name, col[1] is type
                schema_str += f"  - {col[0]} ({col[1]})\n"
            schema_str += "\n"
        return schema_str

    def get_table_content(self, table_name: str, limit: int = 50):
        """Returns the content of a table with a limit."""
        self.validate_table_name(table_name)
        try:
            # Get columns first to return structured data
            schema = self.get_schema(table_name)
            columns = [col[0] for col in schema]
            
            # Fetch data
            result = self.conn.execute(f'SELECT * FROM "{table_name}" LIMIT {limit}').fetchall()
            
            # Convert to list of dicts for easier JSON serialization
            data = []
            for row in result:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i]
                data.append(row_dict)
                
            return {"columns": columns, "data": data}
        except Exception as e:
            print(f"Error fetching table content: {e}")
            raise e

    def delete_table(self, table_name: str):
        """Deletes a table from the database."""
        self.validate_table_name(table_name)
        try:
            self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            return f"Successfully deleted table {table_name}"
        except Exception as e:
            print(f"Error deleting table {table_name}: {e}")
            raise e

@lru_cache()
def get_duckdb_service():
    return DuckDBService()
