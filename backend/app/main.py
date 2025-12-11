from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
# from app.api import endpoints # Will be added later

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/")
def root():
    return {"message": "Data Intelligence Platform API"}

from app.api.endpoints import chat, upload, relationships, history

app.include_router(chat.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(relationships.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1/history")
