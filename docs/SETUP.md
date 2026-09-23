# Local setup on Windows

## Prerequisites

Install Git, Docker Desktop, Python 3.11 or later, and Node.js 18 or later. Confirm Docker Desktop is running before starting the database.

## Environment

Use `.env.example` as the reference for local environment variables. Do not commit a local `.env` file. Set `DATABASE_URL` to the PostgreSQL connection string used by your environment.

## Database

From the repository root, start PostgreSQL with pgvector:

```powershell
docker compose up -d postgres
```

Check its status with:

```powershell
docker compose ps
```

## Backend

```powershell
Set-Location backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/health` to confirm the service responds with `{"status":"ok"}`.

## Frontend

Open a second PowerShell window:

```powershell
Set-Location frontend
npm install
npm run dev
```

Follow the local URL printed by Vite.
