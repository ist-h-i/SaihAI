@echo off
setlocal EnableExtensions

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
  goto :pause_on_error
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] "npm" not found in PATH.
  echo Install Node.js (includes npm^): https://nodejs.org/
  goto :pause_on_error
)

echo [backend] uv sync
pushd "%ROOT%\backend" >nul
if errorlevel 1 (
  echo [ERROR] backend directory not found: "%ROOT%\backend"
  goto :pause_on_error
)
call uv sync
if errorlevel 1 (
  popd >nul
  echo [ERROR] backend setup failed (uv sync^).
  goto :pause_on_error
)
popd >nul

echo [frontend] npm ci
pushd "%ROOT%\frontend" >nul
if errorlevel 1 (
  echo [ERROR] frontend directory not found: "%ROOT%\frontend"
  goto :pause_on_error
)
call npm ci
if errorlevel 1 (
  popd >nul
  echo [ERROR] frontend setup failed (npm ci^).
  echo If this is a dev machine, you can try: npm install
  goto :pause_on_error
)
popd >nul

echo.
echo Setup complete.
echo Next: run dev-start.bat
exit /b 0

:pause_on_error
echo.
echo Press any key to close...
pause >nul
exit /b 1
