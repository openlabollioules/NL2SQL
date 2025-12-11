from fastapi import APIRouter, HTTPException
from app.services.relationship_service import relationship_service, Relationship
from app.services.duckdb_service import get_duckdb_service

router = APIRouter()

@router.delete("/relationships/all")
def reset_relationships():
    try:
        result = relationship_service.reset_relationships()
        return {"message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/relationships/mermaid")
def get_schema_mermaid():
    try:
        tables = get_duckdb_service().get_tables()
        relationships = relationship_service.get_relationships()
        
        mermaid_str = "erDiagram\n"
        
        # Helper to format names for Mermaid
        def format_name(name):
            # Mermaid erDiagram supports quoted names for entities with spaces/accents
            return f'"{name}"'

        for table in tables:
            original_name = table[0]
            table_name = format_name(original_name)
            
            mermaid_str += f'    {table_name} {{\n'
            
            schema = get_duckdb_service().get_schema(original_name)
            for col in schema:
                col_name = col[0]
                col_type = col[1]
                # Sanitize column name: remove ? and other special chars that break Mermaid
                # Keep alphanumeric and underscores
                import re
                safe_col_name = re.sub(r'[^a-zA-Z0-9_]', '_', col_name)
                mermaid_str += f'        {col_type} {safe_col_name}\n'
            mermaid_str += "    }\n"
            
        # Add relationships
        for rel in relationships:
            source = format_name(rel['table_source'])
            target = format_name(rel['table_target'])
            
            mermaid_str += f'    {source} }}o--|| {target} : "references"\n'
            
        return {"mermaid": mermaid_str}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/relationships")
def get_relationships():
    return relationship_service.get_relationships()

@router.post("/relationships")
def add_relationship(relationship: Relationship):
    try:
        result = relationship_service.add_relationship(relationship)
        return {"message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/relationships")
def delete_relationship(table_source: str, column_source: str, table_target: str, column_target: str):
    try:
        result = relationship_service.delete_relationship(table_source, column_source, table_target, column_target)
        return {"message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tables/{table_name}/columns")
def get_table_columns(table_name: str):
    try:
        schema = get_duckdb_service().get_schema(table_name)
        # schema is list of (name, type, ...)
        columns = [col[0] for col in schema]
        return {"columns": columns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import FileResponse
from fastapi import UploadFile, File
import shutil
import json

@router.get("/relationships/export")
def export_relationships():
    try:
        file_path = relationship_service.file_path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="No configuration file found")
        return FileResponse(path=file_path, filename="relationships.json", media_type='application/json')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/relationships/import")
async def import_relationships(file: UploadFile = File(...)):
    try:
        content = await file.read()
        # Validate JSON
        try:
            data = json.loads(content)
            if not isinstance(data, list):
                raise ValueError("Invalid format: expected a list of relationships")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")
            
        # Overwrite file
        with open(relationship_service.file_path, "wb") as f:
            f.write(content)
            
        return {"message": "Configuration imported successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
