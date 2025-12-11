import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os

DB_PATH = "history.db"

class HistoryService:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Create sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Create messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    type TEXT DEFAULT 'text',
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            """)
            conn.commit()

    def create_session(self, session_id: str, title: str = "Nouvelle conversation"):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO sessions (id, title) VALUES (?, ?)",
                (session_id, title)
            )
            conn.commit()
            return session_id

    def get_sessions(self) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def add_message(self, session_id: str, role: str, content: str, msg_type: str = 'text', metadata: Dict = None):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Ensure session exists
            self.create_session(session_id)
            
            cursor.execute(
                """
                INSERT INTO messages (session_id, role, content, type, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, msg_type, json.dumps(metadata) if metadata else None)
            )
            conn.commit()
            
            # Update session title if it's the first user message
            if role == 'user':
                # Check if it's the first message
                cursor.execute("SELECT count(*) FROM messages WHERE session_id = ?", (session_id,))
                count = cursor.fetchone()[0]
                if count <= 2: # allowing for initial system/welcome messages
                    # Generate a simple title from content (truncate)
                    title = (content[:30] + '...') if len(content) > 30 else content
                    cursor.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
                    conn.commit()

    def get_messages(self, session_id: str) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
            rows = cursor.fetchall()
            messages = []
            for row in rows:
                msg = dict(row)
                if msg['metadata']:
                    msg['metadata'] = json.loads(msg['metadata'])
                messages.append(msg)
            return messages

    def delete_session(self, session_id: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()

    def delete_all_sessions(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM sessions")
            conn.commit()

history_service = HistoryService()
