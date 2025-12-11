# Cashout IA - Backend

Backend API for the Cashout IA application, built with **FastAPI** and **DuckDB**.

## Features

- **DuckDB Integration**: Efficient in-process SQL OLAP database.
- **Dependency Injection**: Modular service architecture (e.g., `DuckDBService`).
- **Agentic AI**: Tools and endpoints for AI-driven data analysis (SQL generation, chart suggestion).
- **WebSocket**: Real-time chat interface support.
- **REST API**: Endpoints for file uploads, table management, and relationships.

## Setup

1. **Prerequisites**: Python 3.10+
2. **Create Virtual Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   # OR if using uv/poetry
   uv sync
   ```

## Running the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive documentation (Swagger UI): `http://localhost:8000/docs`.

## Key Directories

- `app/api`: REST and WebSocket endpoints.
- `app/services`: Business logic (Agent, DuckDB, Relationships).
- `data/`: Storage for DuckDB database and uploaded files.
