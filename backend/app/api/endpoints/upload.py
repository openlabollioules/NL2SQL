"""
Upload Endpoints
Handles file uploads and triggers enhanced semantic indexation.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import shutil
import os
import logging
from pathlib import Path
from app.services.duckdb_service import get_duckdb_service

logger = logging.getLogger(__name__)
router = APIRouter()

# backend/app/api/endpoints/upload.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def index_table(table_name: str):
    """
    Enhanced table indexation with semantic descriptions and sample values.
    Indexes: table description, column descriptions, sample values, synonyms.
    """
    from app.services.vector_store import vector_store
    from app.services.ollama_service import ollama_service
    from langchain_core.messages import HumanMessage
    
    logger.info(f"Starting enhanced indexation for table: {table_name}")
    
    # Clear existing documents for this table (re-indexation support)
    cleared = vector_store.clear_table_documents(table_name)
    if cleared > 0:
        logger.info(f"Cleared {cleared} existing documents for {table_name}")
    
    try:
        schema = get_duckdb_service().get_schema(table_name)
        columns = [col[0] for col in schema]
        column_types = {col[0]: col[1] for col in schema}
        
        # Get row count
        try:
            row_count = get_duckdb_service().conn.execute(
                f'SELECT COUNT(*) FROM "{table_name}"'
            ).fetchone()[0]
        except:
            row_count = 0
        
        # 1. Generate and index TABLE DESCRIPTION
        table_prompt = f"""Génère une description concise en français pour une table de base de données.
        
Nom de la table: {table_name}
Colonnes: {', '.join(columns)}
Nombre de lignes: {row_count}

Réponds avec UNIQUEMENT la description (1-2 phrases), sans préambule."""

        response = ollama_service.generate_response([HumanMessage(content=table_prompt)])
        table_description = response.content.strip()
        
        vector_store.add_documents(
            documents=[f"Table {table_name}: {table_description}. Contient {row_count} lignes avec les colonnes: {', '.join(columns)}."],
            metadatas=[{"table": table_name, "type": "table_description"}]
        )
        logger.debug(f"Indexed table description for {table_name}")
        
        # 2. Index each COLUMN with semantic description and sample values
        for col in schema:
            col_name = col[0]
            col_type = col[1]
            
            # Get sample values (top 5 distinct non-null values)
            try:
                sample_query = f'''
                    SELECT DISTINCT "{col_name}" 
                    FROM "{table_name}" 
                    WHERE "{col_name}" IS NOT NULL 
                    LIMIT 5
                '''
                samples = get_duckdb_service().conn.execute(sample_query).fetchall()
                sample_values = [str(s[0]) for s in samples if s[0] is not None][:5]
            except Exception as e:
                logger.debug(f"Could not get samples for {col_name}: {e}")
                sample_values = []
            
            # Generate semantic column description
            col_prompt = f"""Analyse cette colonne de base de données et génère une description sémantique.

Table: {table_name}
Colonne: {col_name}
Type: {col_type}
Exemples de valeurs: {', '.join(sample_values) if sample_values else 'N/A'}

Réponds avec UNIQUEMENT:
1. Une description en français (1 phrase)
2. Des synonymes métier possibles (3-5 mots-clés séparés par des virgules)

Format:
Description: <description>
Synonymes: <synonyme1>, <synonyme2>, ..."""

            try:
                response = ollama_service.generate_response([HumanMessage(content=col_prompt)])
                col_analysis = response.content.strip()
                
                # Parse response
                description_line = ""
                synonyms_line = ""
                for line in col_analysis.split('\n'):
                    if line.lower().startswith('description:'):
                        description_line = line.split(':', 1)[1].strip()
                    elif line.lower().startswith('synonyme'):
                        synonyms_line = line.split(':', 1)[1].strip()
                
                # Build rich column document
                col_doc = f"Colonne '{col_name}' dans table '{table_name}' (type: {col_type})"
                if description_line:
                    col_doc += f". {description_line}"
                if sample_values:
                    col_doc += f". Exemples: {', '.join(sample_values[:3])}"
                if synonyms_line:
                    col_doc += f". Termes associés: {synonyms_line}"
                
                vector_store.add_documents(
                    documents=[col_doc],
                    metadatas=[{
                        "table": table_name, 
                        "column": col_name,
                        "type": "column_description",
                        "data_type": col_type
                    }]
                )
                
            except Exception as e:
                # Fallback: index basic column info
                logger.warning(f"LLM description failed for {col_name}, using basic: {e}")
                basic_doc = f"Colonne '{col_name}' dans table '{table_name}' (type: {col_type})"
                if sample_values:
                    basic_doc += f". Exemples: {', '.join(sample_values[:3])}"
                
                vector_store.add_documents(
                    documents=[basic_doc],
                    metadatas=[{
                        "table": table_name,
                        "column": col_name, 
                        "type": "column_definition",
                        "data_type": col_type
                    }]
                )
        
        logger.info(f"Successfully indexed table {table_name} with {len(columns)} columns")
        
    except Exception as e:
        logger.exception(f"Error indexing table {table_name}: {e}")

    # 3. Infer RELATIONSHIPS with other tables
    try:
        all_tables = get_duckdb_service().get_tables()
        other_tables = [t[0] for t in all_tables if t[0] != table_name]
        
        if other_tables:
            other_schemas = ""
            for t in other_tables[:5]:  # Limit to 5 tables to avoid prompt overflow
                other_schemas += f"Table {t}:\n"
                t_schema = get_duckdb_service().get_schema(t)
                for col in t_schema[:10]:  # Limit columns per table
                    other_schemas += f"  - {col[0]} ({col[1]})\n"
            
            current_schema_str = f"Table {table_name}:\n"
            for col in schema:
                current_schema_str += f"  - {col[0]} ({col[1]})\n"
                
            rel_prompt = f"""Analyse ces schémas pour identifier les relations potentielles.

Nouvelle table:
{current_schema_str}

Tables existantes:
{other_schemas}

Identifie les colonnes qui semblent être des clés étrangères (même nom, suffixe _id, etc.).
Réponds avec une liste de relations au format:
"table_source.colonne -> table_cible.colonne"

Si aucune relation, réponds "Aucune relation trouvée"."""
            
            response = ollama_service.generate_response([HumanMessage(content=rel_prompt)])
            relationships = response.content.strip()
            
            if "aucune" not in relationships.lower():
                vector_store.add_documents(
                    documents=[f"Relations identifiées pour {table_name}: {relationships}"],
                    metadatas=[{"table": table_name, "type": "relationships"}]
                )
                logger.info(f"Indexed relationships for {table_name}")
                
    except Exception as e:
        logger.warning(f"Error inferring relationships for {table_name}: {e}")


@router.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a CSV/Excel file and load it into DuckDB."""
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Load into DuckDB
    table_name = file.filename.split(".")[0]
    try:
        get_duckdb_service().load_csv(str(file_path), table_name)
        
        # Trigger background indexing
        background_tasks.add_task(index_table, table_name)
            
        return {
            "message": f"Fichier {file.filename} chargé dans la table {table_name}. Indexation sémantique en cours...",
            "table": table_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex")
async def reindex_all_tables(background_tasks: BackgroundTasks):
    """Re-index all existing tables in the database."""
    try:
        tables = get_duckdb_service().get_tables()
        table_names = [t[0] for t in tables]
        
        for table_name in table_names:
            background_tasks.add_task(index_table, table_name)
        
        return {
            "message": f"Ré-indexation de {len(table_names)} tables en cours...",
            "tables": table_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex/{table_name}")
async def reindex_table(table_name: str, background_tasks: BackgroundTasks):
    """Re-index a specific table."""
    try:
        # Verify table exists
        tables = [t[0] for t in get_duckdb_service().get_tables()]
        if table_name not in tables:
            raise HTTPException(status_code=404, detail=f"Table {table_name} not found")
        
        background_tasks.add_task(index_table, table_name)
        
        return {"message": f"Ré-indexation de {table_name} en cours..."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector-stats")
def get_vector_stats():
    """Get statistics about the vector store."""
    from app.services.vector_store import vector_store
    return vector_store.get_stats()


@router.get("/tables")
def get_tables():
    """List all tables in the database."""
    try:
        tables = get_duckdb_service().get_tables()
        return {"tables": [t[0] for t in tables]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_name}/preview")
def get_table_preview(table_name: str):
    """Get a preview of table content."""
    try:
        content = get_duckdb_service().get_table_content(table_name)
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tables/{table_name}")
def delete_table(table_name: str):
    """Delete a table and its vector store documents."""
    from app.services.vector_store import vector_store
    
    try:
        get_duckdb_service().delete_table(table_name)
        cleared = vector_store.clear_table_documents(table_name)
        return {
            "message": f"Table {table_name} supprimée",
            "vectors_cleared": cleared
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
