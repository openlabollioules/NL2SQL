"""
Application Configuration
Uses Pydantic Settings for environment-based configuration.
"""
from typing import List, Union

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Project Info
    PROJECT_NAME: str = "Data Intelligence Platform"
    API_V1_STR: str = "/api/v1"
    
    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[str] = []

    # Ollama Settings (local LLM)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str = "qwen3:32b"
    OLLAMA_SQL_MODEL: str = "qwen3:32b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    
    # Logging
    LOG_LEVEL: str = "INFO"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """
        Parse CORS origins from comma-separated string or list.
        """
        if isinstance(v, str):
            if v.startswith("["):
                # JSON array format
                import json
                return json.loads(v)
            elif v:
                # Comma-separated format
                return [origin.strip() for origin in v.split(",") if origin.strip()]
            return []
        elif isinstance(v, list):
            return v
        return []

    model_config = {
        "case_sensitive": True,
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


settings = Settings()
