@echo off
setlocal

set "ROOT=%~dp0"
rem Normalize ROOT to not end with "\" to avoid cmd quote parsing issues (e.g., "C:\path\")
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo === SaihAI dev setup (one-time) ===
echo Repo: "%ROOT%"
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo [ERROR] "uv" not found in PATH.
  echo Install uv: https://docs.astral.sh/uv/
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] "npm" not found in PATH.
  echo Install Node.js (includes npm^): https://nodejs.org/
  exit /b 1
)

echo [backend] uv sync
pushd "%ROOT%\backend" >nul
uv sync
if errorlevel 1 (
  popd >nul
  echo [ERROR] backend setup failed (uv sync^).
  exit /b 1
)
popd >nul

echo [frontend] npm ci
pushd "%ROOT%\frontend" >nul
call npm ci
if errorlevel 1 (
  popd >nul
  echo [ERROR] frontend setup failed (npm ci^).
  echo If this is a dev machine, you can try: npm install
  exit /b 1
)
popd >nul

echo.
echo Setup complete.
echo Next: run dev-start.bat
exit /b 0
