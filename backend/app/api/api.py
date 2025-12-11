from fastapi import APIRouter
from app.api.endpoints import chat, upload, relationships

api_router = APIRouter()
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(relationships.router, tags=["relationships"])
