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

## Endpoints

- `GET /api/health` -> `{ "status": "ok" }`
- `GET /api/projects`
- `GET /api/members`
- `POST /api/simulate` -> `{ projectId: string, memberIds: string[] }`

## Notes

- `uvicorn` が見つからない場合は `uv run uvicorn app.main:app --reload` を使用してください
