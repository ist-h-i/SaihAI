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
- `LOG_LEVEL` (default: `INFO`)
- `LOG_FILE` (optional: file path to write logs, daily rotation, keep 3 days)
- `LOG_HTTP_REQUESTS` (default: `1`)

Migrations and seed:

```powershell
cd backend
uv run python scripts/db_tool.py up
uv run python scripts/db_tool.py seed --force
```

Rollback the latest migration:

```powershell
uv run python scripts/db_tool.py down
```

## Endpoints

- `GET /api/health` -> `{ "status": "ok" }`
- `GET /api/projects`
- `GET /api/members`
- `POST /api/simulate` -> `{ projectId: string, memberIds: string[] }`
- `POST /api/v1/auth/login`
- `GET /api/v1/me`
- `POST /api/v1/logs/frontend`
- `GET /api/v1/bedrock/status`
- `POST /api/v1/bedrock/invoke`

## Bedrock (optional)

Environment variables:

- `AWS_REGION`
- `AWS_BEDROCK_MODEL_ID`

Auth:

- Uses `boto3` credential resolution (e.g., `AWS_PROFILE`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`).

Quick check:

```powershell
curl -sS -X POST `
  -H "Authorization: Bearer <your-jwt>" `
  -H "Content-Type: application/json" `
  http://localhost:8000/api/v1/bedrock/invoke `
  -d '{"prompt":"Say hello as JSON only: {\"ok\":true}","allowMock":true}'
```

## Notes

- `uvicorn` が見つからない場合は `uv run uvicorn app.main:app --reload` を使用してください
- すべてのHTTPレスポンスに `X-Request-ID` を返します（リクエストで `X-Request-ID` を指定すると相関できます）
