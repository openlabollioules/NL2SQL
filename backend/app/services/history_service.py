"""
History Service
Manages conversation history using SQLite with connection pooling.
"""
import sqlite3
import json
import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from queue import Queue, Empty

logger = logging.getLogger(__name__)

# Database path relative to backend directory
DB_PATH = Path(__file__).resolve().parent.parent.parent / "history.db"

# Connection pool settings
POOL_SIZE = 5
POOL_TIMEOUT = 30.0


class ConnectionPool:
    """Thread-safe SQLite connection pool."""
    
    def __init__(self, database: str, pool_size: int = POOL_SIZE):
        self.database = str(database)
        self.pool_size = pool_size
        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._initialized = False
        
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimal settings."""
        conn = sqlite3.connect(
            self.database,
            check_same_thread=False,
            timeout=POOL_TIMEOUT
        )
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.row_factory = sqlite3.Row
        return conn
    
    def initialize(self):
        """Pre-populate the connection pool."""
        with self._lock:
            if self._initialized:
                return
            for _ in range(self.pool_size):
                self._pool.put(self._create_connection())
            self._initialized = True
            logger.info(f"Connection pool initialized with {self.pool_size} connections")
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        if not self._initialized:
            self.initialize()
            
        conn = None
        try:
            # Try to get from pool, create new if pool is empty
            try:
                conn = self._pool.get(timeout=POOL_TIMEOUT)
            except Empty:
                logger.warning("Connection pool exhausted, creating new connection")
                conn = self._create_connection()
            
            yield conn
            
        finally:
            if conn:
                try:
                    # Return to pool if there's room, otherwise close
                    self._pool.put_nowait(conn)
                except:
                    conn.close()
    
    def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Empty:
                break
        self._initialized = False


class HistoryService:
    """Service for managing conversation history."""
    
    def __init__(self):
        self._pool = ConnectionPool(DB_PATH)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create messages table with indexes
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
            
            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session 
                ON messages(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_created 
                ON sessions(created_at DESC)
            """)
            
            conn.commit()
            logger.info("Database schema initialized")

    def create_session(self, session_id: str, title: str = "Nouvelle conversation") -> str:
        """Create a new session if it doesn't exist."""
        with self._pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO sessions (id, title) VALUES (?, ?)",
                (session_id, title)
            )
            conn.commit()
            return session_id

    def get_sessions(self, limit: int = 50) -> List[Dict]:
        """Get all sessions ordered by creation date."""
        with self._pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str, 
        msg_type: str = 'text', 
        metadata: Optional[Dict] = None
    ):
        """Add a message to a session."""
        with self._pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Ensure session exists
            cursor.execute(
                "INSERT OR IGNORE INTO sessions (id, title) VALUES (?, ?)",
                (session_id, "Nouvelle conversation")
            )
            
            # Insert message
            cursor.execute(
                """
                INSERT INTO messages (session_id, role, content, type, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, msg_type, json.dumps(metadata) if metadata else None)
            )
            
            # Update session title from first user message
            if role == 'user':
                cursor.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id = ? AND role = 'user'",
                    (session_id,)
                )
                count = cursor.fetchone()[0]
                if count <= 1:
                    title = (content[:30] + '...') if len(content) > 30 else content
                    cursor.execute(
                        "UPDATE sessions SET title = ? WHERE id = ?",
                        (title, session_id)
                    )
            
            conn.commit()

    def get_messages(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Get all messages for a session."""
        with self._pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM messages 
                WHERE session_id = ? 
                ORDER BY created_at ASC 
                LIMIT ?
                """,
                (session_id, limit)
            )
            
            messages = []
            for row in cursor.fetchall():
                msg = dict(row)
                if msg['metadata']:
                    try:
                        msg['metadata'] = json.loads(msg['metadata'])
                    except json.JSONDecodeError:
                        msg['metadata'] = None
                messages.append(msg)
            return messages

    def delete_session(self, session_id: str):
        """Delete a session and all its messages."""
        with self._pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            logger.info(f"Deleted session: {session_id}")

    def delete_all_sessions(self):
        """Delete all sessions and messages."""
        with self._pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM sessions")
            conn.commit()
            logger.info("Deleted all sessions")

    def get_session_count(self) -> int:
        """Get total number of sessions."""
        with self._pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sessions")
            return cursor.fetchone()[0]

    def cleanup_old_sessions(self, days: int = 30):
        """Delete sessions older than specified days."""
        with self._pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM messages WHERE session_id IN (
                    SELECT id FROM sessions 
                    WHERE created_at < datetime('now', ? || ' days')
                )
                """,
                (f"-{days}",)
            )
            cursor.execute(
                "DELETE FROM sessions WHERE created_at < datetime('now', ? || ' days')",
                (f"-{days}",)
            )
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Cleaned up {deleted} old sessions")
            return deleted


# Singleton instance
history_service = HistoryService()
