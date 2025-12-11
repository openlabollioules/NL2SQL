from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.messages import BaseMessage
from typing import List

from app.core.config import settings

class OllamaService:
    def __init__(self):
        self.chat_llm = ChatOllama(model=settings.OLLAMA_CHAT_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0)
        self.sql_llm = ChatOllama(model=settings.OLLAMA_SQL_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0)
        self.embeddings = OllamaEmbeddings(model=settings.OLLAMA_EMBED_MODEL, base_url=settings.OLLAMA_BASE_URL)

    def generate_response(self, messages: List[BaseMessage]) -> BaseMessage:
        return self.chat_llm.invoke(messages)

    def generate_sql(self, messages: List[BaseMessage]) -> BaseMessage:
        return self.sql_llm.invoke(messages)

    def stream_response(self, messages: List[BaseMessage]):
        return self.chat_llm.stream(messages)
        
    def get_embeddings(self):
        return self.embeddings

ollama_service = OllamaService()
