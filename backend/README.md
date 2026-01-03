# SaihAI Backend (FastAPI)

## Setup

```powershell
cd backend
uv sync
```

## Run

```powershell
cd backend
uvicorn app.main:app --reload
```

## Database

Environment variables:

- `DATABASE_URL` (default: `sqlite:///./saihai.db`)
- `DEV_LOGIN_PASSWORD` (default: `saihai`)
- `JWT_SECRET` (default: `dev-secret`)
- `JWT_TTL_MINUTES` (default: `480`)

Migrations and seed:

```powershell
cd backend
python scripts/db_tool.py up
python scripts/db_tool.py seed --force
```

Rollback the latest migration:

```powershell
python scripts/db_tool.py down
```

## Endpoints

- `GET /api/health` -> `{ "status": "ok" }`
- `GET /api/projects`
- `GET /api/members`
- `POST /api/simulate` -> `{ projectId: string, memberIds: string[] }`
- `POST /api/v1/auth/login`
- `GET /api/v1/me`

## Notes

- `uvicorn` が見つからない場合は `uv run uvicorn app.main:app --reload` を使用してください
