# Multi-Agent-RAG-Orchestration

Foundation for a production-ready multi-agent RAG orchestration service. The system combines FastAPI, React/TypeScript, PostgreSQL 16 with pgvector, and Alembic database migrations.

## Prerequisites

- Git
- Python 3.11 or later
- Node.js 18 or later with npm
- Docker Desktop with Docker Compose

## Project Structure

```text
.
├── backend/            FastAPI service, database models, and tests
│   ├── alembic/        Database migration scripts
│   ├── app/            Application source code (api, core, db, models)
│   └── tests/          Unit and integration test suites
├── frontend/           React and TypeScript application (Vite)
├── docs/               Project documentation and setup guides
├── .github/            GitHub pull request template
├── .env.example        Environment variable reference
└── docker-compose.yml  PostgreSQL with pgvector configuration
```

## Setup and Running

Follow the exact steps below to set up and start the development environment:

### 1. Configure Environment Variables

Copy `.env.example` to `.env` in the repository root:

```bash
cp .env.example .env
```

Ensure `DATABASE_URL`, `CORS_ORIGINS`, and `TEST_DATABASE_URL` are configured properly.

### 2. Start PostgreSQL

Start the PostgreSQL 16 container with pgvector:

```bash
docker compose up -d postgres
```

The database container listens on `localhost:5432`. The default development database is `multi_agent_rag`.

### 3. Install Backend Dependencies

Navigate to the `backend` directory and set up a Python virtual environment:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:
- Windows (PowerShell): `.\.venv\Scripts\Activate.ps1`
- Windows (CMD): `.\.venv\Scripts\activate.bat`
- macOS / Linux: `source .venv/bin/activate`

Install dependencies:

```bash
pip install -r requirements.txt
```

### 4. Run Database Migrations

Apply Alembic migrations to the development database:

```bash
alembic upgrade head
```

### 5. Start the Backend Service

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 6. Verify Service and Swagger UI

- **Health check:** `GET http://127.0.0.1:8000/health` -> `{"status":"ok"}`
- **Interactive Swagger UI:** `http://127.0.0.1:8000/docs`

### 7. Install and Run Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` to access the application.

---

## Authentication API: User Registration

### Endpoint
`POST /api/auth/register`

### Request Body (JSON)
```json
{
  "email": "user@example.com",
  "name": "Nguyen Van A",
  "password": "Password123"
}
```

- **Validation rules:**
  - `email`: Valid email format, trimmed and normalized to lowercase.
  - `name`: Required, non-empty, trimmed, maximum 100 characters.
  - `password`: Required, minimum 8 characters, hashed using Argon2id.

### Response (HTTP 201 Created)
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Nguyen Van A",
  "message": "Đăng ký thành công"
}
```

*Sensitive data note: Passwords, password hashes, and tokens are never returned.*

### Status Codes
- `201 Created`: User successfully registered.
- `400 Bad Request`: Empty/whitespace name or password, name > 100 chars, or password < 8 chars.
- `409 Conflict`: Email is already registered.
- `422 Unprocessable Entity`: Missing fields or invalid email syntax.
- `500 Internal Server Error`: Unexpected database or system error.

### Frontend Integration Note
Upon receiving HTTP 201, the Frontend should redirect the user to the Login screen. CAPONE-8 does not implement auto-login, JWT tokens, cookies, or sessions.

---

## Running Tests

From the `backend` directory with the virtual environment activated:

### Run Unit Tests (SQLite in-memory)
```bash
python -m pytest tests/test_auth.py tests/test_cors.py tests/test_health.py -v
```

### Run PostgreSQL Integration Tests

1. Create the dedicated test database in PostgreSQL (if not already created):

```bash
docker exec multi-agent-rag-postgres psql -U postgres -c "CREATE DATABASE multi_agent_rag_test;"
```

2. Apply Alembic migrations to the test database:

- **Windows (PowerShell):**
  ```powershell
  $env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/multi_agent_rag_test"
  alembic upgrade head
  $env:DATABASE_URL = $null
  ```
- **macOS / Linux (Bash):**
  ```bash
  DATABASE_URL="postgresql://postgres:postgres@localhost:5432/multi_agent_rag_test" alembic upgrade head
  ```

3. Run PostgreSQL integration tests:

```bash
python -m pytest tests/test_auth_postgres.py -v
```

### Run All Tests (31 tests)
```bash
python -m pytest -v
```

---

## Branches

- `main`: Production-ready baseline.
- `dev`: Integration branch for ongoing development.
- `feature/...`: Scoped feature branches branched from and merged into `dev`.
