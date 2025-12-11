import json
import os
from pathlib import Path
from typing import List, Dict
from pydantic import BaseModel

class Relationship(BaseModel):
    table_source: str
    column_source: str
    table_target: str
    column_target: str
    description: str = ""

class RelationshipService:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.data_dir = self.base_dir / "data"
        self.file_path = self.data_dir / "relationships.json"
        os.makedirs(self.data_dir, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self):
        if not self.file_path.exists():
            with open(self.file_path, "w") as f:
                json.dump([], f)

    def get_relationships(self) -> List[Dict]:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading relationships: {e}")
            return []

    def add_relationship(self, relationship: Relationship):
        relationships = self.get_relationships()
        # Check for duplicates
        for r in relationships:
            if (r["table_source"] == relationship.table_source and 
                r["column_source"] == relationship.column_source and 
                r["table_target"] == relationship.table_target and 
                r["column_target"] == relationship.column_target):
                return "Relationship already exists"
        
        relationships.append(relationship.dict())
        self._save_relationships(relationships)
        return "Relationship added successfully"

    def delete_relationship(self, table_source: str, column_source: str, table_target: str, column_target: str):
        relationships = self.get_relationships()
        new_relationships = [
            r for r in relationships 
            if not (r["table_source"] == table_source and 
                    r["column_source"] == column_source and 
                    r["table_target"] == table_target and 
                    r["column_target"] == column_target)
        ]
        self._save_relationships(new_relationships)
        return "Relationship deleted successfully"

    def _save_relationships(self, relationships: List[Dict]):
        with open(self.file_path, "w") as f:
            json.dump(relationships, f, indent=2)

    def reset_relationships(self):
        self._save_relationships([])
        return "All relationships deleted successfully"

    def get_formatted_relationships(self) -> str:
        relationships = self.get_relationships()
        if not relationships:
            return ""
        
        formatted = "Defined Relationships:\n"
        for r in relationships:
            formatted += f"- {r['table_source']}.{r['column_source']} references {r['table_target']}.{r['column_target']}\n"
        return formatted

relationship_service = RelationshipService()
