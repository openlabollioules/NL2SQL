from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.history_service import history_service

router = APIRouter()

class SessionCreate(BaseModel):
    session_id: str
    title: Optional[str] = "Nouvelle conversation"

class MessageCreate(BaseModel):
    session_id: str
    role: str
    content: str
    type: str = "text"
    metadata: Optional[Dict[str, Any]] = None

@router.get("/sessions")
async def get_sessions():
    return history_service.get_sessions()

@router.post("/sessions")
async def create_session(session: SessionCreate):
    history_service.create_session(session.session_id, session.title)
    return {"status": "success", "session_id": session.session_id}

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    history_service.delete_session(session_id)
    return {"status": "success"}

@router.delete("/sessions")
async def delete_all_sessions():
    history_service.delete_all_sessions()
    return {"status": "success"}

@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    return history_service.get_messages(session_id)
