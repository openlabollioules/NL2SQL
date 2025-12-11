from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import shutil
import os
from pathlib import Path
from app.services.duckdb_service import get_duckdb_service

router = APIRouter()

# backend/app/api/endpoints/upload.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def index_table(table_name: str):
    # Populate Vector Store
    from app.services.vector_store import vector_store
    from app.services.ollama_service import ollama_service
    from langchain_core.messages import HumanMessage
    
    try:
        schema = get_duckdb_service().get_schema(table_name)
        # schema is list of (name, type, ...)
        
        # Generate description for the table
        columns = [col[0] for col in schema]
        prompt = f"Generate a brief description for a table named '{table_name}' with columns: {', '.join(columns)}. Return just the description."
        response = ollama_service.generate_response([HumanMessage(content=prompt)])
        description = response.content
        
        # Add to vector store
        vector_store.add_documents(
            documents=[f"Table {table_name}: {description}"],
            metadatas=[{"table": table_name, "type": "table_description"}]
        )
        
        # Add column descriptions
        for col in schema:
            col_name = col[0]
            col_type = col[1]
            vector_store.add_documents(
                documents=[f"Column {col_name} in table {table_name} ({col_type})"],
                metadatas=[{"table": table_name, "column": col_name, "type": "column_definition"}]
            )
        print(f"Successfully indexed table {table_name}")
    except Exception as e:
        print(f"Error indexing table {table_name}: {e}")

    # Infer relationships
    try:
        all_tables = get_duckdb_service().get_tables()
        other_tables = [t[0] for t in all_tables if t[0] != table_name]
        
        if other_tables:
            other_schemas = ""
            for t in other_tables:
                other_schemas += f"Table {t}:\n"
                t_schema = get_duckdb_service().get_schema(t)
                for col in t_schema:
                    other_schemas += f"  - {col[0]} ({col[1]})\n"
            
            current_schema_str = f"Table {table_name}:\n"
            for col in schema:
                current_schema_str += f"  - {col[0]} ({col[1]})\n"
                
            prompt = f"""Analyze the following database schemas to identify potential foreign key relationships between the new table '{table_name}' and existing tables.
            
            New Table Schema:
            {current_schema_str}
            
            Existing Tables Schemas:
            {other_schemas}
            
            Identify relationships based on column names (e.g. client_id vs id, code_produit vs code).
            Return a list of relationships in this format: "Table A column X references Table B column Y".
            If no relationships are found, return "No relationships found".
            Keep it concise."""
            
            response = ollama_service.generate_response([HumanMessage(content=prompt)])
            relationships = response.content
            
            if "No relationships found" not in relationships:
                print(f"Inferred relationships for {table_name}: {relationships}")
                vector_store.add_documents(
                    documents=[f"Relationships for {table_name}: {relationships}"],
                    metadatas=[{"table": table_name, "type": "relationships"}]
                )
    except Exception as e:
        print(f"Error inferring relationships for {table_name}: {e}")

@router.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Load into DuckDB
    table_name = file.filename.split(".")[0]
    try:
        get_duckdb_service().load_csv(str(file_path), table_name)
        
        # Trigger background indexing
        background_tasks.add_task(index_table, table_name)
            
        return {"message": f"File {file.filename} uploaded and loaded into table {table_name}. Indexing in background."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tables")
def get_tables():
    try:
        tables = get_duckdb_service().get_tables()
        return {"tables": [t[0] for t in tables]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tables/{table_name}/preview")
def get_table_preview(table_name: str):
    try:
        content = get_duckdb_service().get_table_content(table_name)
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/tables/{table_name}")
def delete_table(table_name: str):
    try:
        get_duckdb_service().delete_table(table_name)
        return {"message": f"Table {table_name} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
