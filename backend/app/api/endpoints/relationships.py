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


@router.get("/relationships/graphviz")
def get_schema_graphviz():
    """Generate a DOT (Graphviz) diagram of the database schema."""
    import re
    try:
        tables = get_duckdb_service().get_tables()
        relationships = relationship_service.get_relationships()
        
        # Start DOT graph with ER-style settings
        dot = '''digraph ERDiagram {
    graph [
        rankdir=LR
        splines=ortho
        nodesep=0.8
        ranksep=1.2
        bgcolor="#ffffff"
        fontname="Helvetica"
    ]
    node [
        shape=none
        fontname="Helvetica"
        fontsize=11
    ]
    edge [
        fontname="Helvetica"
        fontsize=9
        color="#6b7280"
        arrowhead=crow
        arrowtail=none
    ]
    
'''
        
        # Color palette for tables
        colors = [
            ("#3b82f6", "#dbeafe"),  # Blue
            ("#10b981", "#d1fae5"),  # Green
            ("#f59e0b", "#fef3c7"),  # Amber
            ("#8b5cf6", "#ede9fe"),  # Purple
            ("#ec4899", "#fce7f3"),  # Pink
            ("#06b6d4", "#cffafe"),  # Cyan
            ("#f97316", "#ffedd5"),  # Orange
        ]
        
        def sanitize_name(name):
            """Sanitize name for DOT format."""
            return re.sub(r'[^a-zA-Z0-9_]', '_', name)
        
        def escape_html(text):
            """Escape HTML special chars."""
            return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Generate table nodes as HTML-like records
        for idx, table in enumerate(tables):
            original_name = table[0]
            safe_name = sanitize_name(original_name)
            header_color, row_color = colors[idx % len(colors)]
            
            schema = get_duckdb_service().get_schema(original_name)
            
            # Build HTML-like label for the table
            label = f'''<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">
            <TR><TD BGCOLOR="{header_color}" COLSPAN="2"><FONT COLOR="white"><B>{escape_html(original_name)}</B></FONT></TD></TR>
'''
            for col in schema:
                col_name = col[0]
                col_type = col[1]
                safe_col = escape_html(col_name)
                safe_type = escape_html(col_type)
                label += f'            <TR><TD BGCOLOR="{row_color}" ALIGN="LEFT" PORT="{sanitize_name(col_name)}">{safe_col}</TD><TD BGCOLOR="#f9fafb" ALIGN="LEFT"><FONT COLOR="#6b7280">{safe_type}</FONT></TD></TR>\n'
            
            label += '        </TABLE>>'
            
            dot += f'    {safe_name} [label={label}]\n\n'
        
        # Add relationships as edges
        for rel in relationships:
            source_table = sanitize_name(rel['table_source'])
            source_col = sanitize_name(rel['column_source'])
            target_table = sanitize_name(rel['table_target'])
            target_col = sanitize_name(rel['column_target'])
            
            dot += f'    {source_table}:{source_col} -> {target_table}:{target_col} [xlabel="" constraint=true]\n'
        
        dot += '}\n'
        
        return {"graphviz": dot}
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
