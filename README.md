# Cashout IA

Cashout IA is an intelligent data analysis platform that combines a **DuckDB**-powered backend with a **React** frontend to provide natural language querying, SQL execution, and advanced data modeling capabilities.

## Structure

- **`backend/`**: FastAPI server, Agent logic, DuckDB integration.
- **`frontend/`**: React + TypeScript + Vite application.

## Quick Start

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to start using the application.
