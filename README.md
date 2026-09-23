# Multi-Agent-RAG-Orchestration

Foundation for a production-ready multi-agent RAG orchestration service. The initial setup provides a FastAPI health endpoint, a React frontend, and a local PostgreSQL environment with pgvector.

## Prerequisites

- Git
- Python 3.11 or later
- Node.js 18 or later with npm
- Docker Desktop with Docker Compose

## Project structure

```text
.
├── backend/        FastAPI service and tests
├── frontend/       React and TypeScript application
├── docs/           Project documentation
├── .github/        GitHub pull request template
├── .env.example    Environment variable reference
└── docker-compose.yml
```

## Run PostgreSQL

Copy `.env.example` values into your shell or local environment configuration as needed, then start the development database:

```bash
docker compose up -d postgres
```

PostgreSQL listens on `localhost:5432`. The default development database is `multi_agent_rag`.

## Run the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On macOS or Linux, activate the virtual environment with `source .venv/bin/activate`.

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

## Health endpoint

With the backend running, request:

```text
GET http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Branches

- `main` contains the stable project baseline.
- `dev` is the shared integration branch for ongoing development.
