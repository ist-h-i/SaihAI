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

You can also edit `src/assets/runtime-config.json` directly for local testing.

## Pages

- `/dashboard`
- `/simulator`
- `/genome`
- `/login`
