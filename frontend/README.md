# SaihAI Frontend (Angular + Signals + Tailwind)

## Setup

```powershell
cd frontend
npm i
```

## Run

```powershell
cd frontend
npm start
```

## API config

The frontend reads `/assets/runtime-config.json` at boot. `npm start` and `npm run build`
regenerate it from environment variables.

- `SAIHAI_API_BASE_URL` (default: `http://localhost:8000/api/v1`)
- `SAIHAI_AUTH_TOKEN` (optional Bearer token)
- `SAIHAI_LOG_LEVEL` (optional: `debug` | `info` | `warn` | `error`)
- `SAIHAI_LOG_TO_SERVER` (optional: `true` to POST logs to backend)
- `SAIHAI_SERVER_LOG_LEVEL` (optional: minimum level for server logs)

`SAIHAI_LOG_LEVEL=debug` のとき、API通信（開始/終了/所要時間）をコンソールに出力します（`X-Request-ID`でbackendログと相関可能）。

You can also edit `src/assets/runtime-config.json` directly for local testing.

## Pages

- `/dashboard`
- `/simulator`
- `/genome`
- `/login`
