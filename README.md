# SaihAI Tactical Simulator (Monorepo)

FastAPI（モック）+ Angular（standalone / Signals-first）+ Tailwind の最小構成で、「戦術シミュレーター」をまず動かすための雛形です。

## Structure

```
backend/   FastAPI API (mock)
frontend/  Angular app (signals-first) + Tailwind
```

## Dev

### Windows (recommended)

#### One-time setup

```powershell
.\dev-setup.bat
```

#### Start (2nd time and later)

```powershell
.\dev-start.bat
```

### Backend

```powershell
cd backend
uv sync
uvicorn app.main:app --reload
```

### Frontend

```powershell
cd frontend
npm i
npm start
```

## Acceptance Quick Check

- Backend: `GET http://localhost:8000/api/health` -> `{ "status": "ok" }`
- Frontend: `http://localhost:4200` -> `/dashboard` `/simulator` `/genome`
- Simulator: 案件/メンバー選択 -> “AI自動編成” -> 予算バー・タイムライン・3プランが表示

## Notes

- DB/認証/本格LLM接続は未実装（モックデータ + 簡易スコアリング）
- `.agent/` は Golden Profile（Plan→Patch→Review→Decision）用のルール一式です
