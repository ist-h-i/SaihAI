@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
rem Normalize ROOT to not end with "\" to avoid cmd quote parsing issues (e.g., "C:\path\")
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo === SaihAI dev start ===
echo Repo: "%ROOT%"
echo.

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] "npm" not found in PATH.
  echo Run dev-setup.bat first (after installing Node.js^).
  goto :pause_on_error
)

set "BACKEND_CMD="
where uv >nul 2>nul
if not errorlevel 1 (
  set "BACKEND_CMD=uv run uvicorn app.main:app --reload"
) else (
  where uvicorn >nul 2>nul
  if not errorlevel 1 (
    set "BACKEND_CMD=uvicorn app.main:app --reload"
  ) else (
    echo [ERROR] Neither "uv" nor "uvicorn" found in PATH.
    echo Run dev-setup.bat first (and ensure uv is installed^).
    goto :pause_on_error
  )
)

set "DB_CMD=python scripts/db_tool.py"
where uv >nul 2>nul
if not errorlevel 1 (
  set "DB_CMD=uv run python scripts/db_tool.py"
)

set "BACKEND_PORT=%BACKEND_PORT%"
if "%BACKEND_PORT%"=="" set "BACKEND_PORT=8000"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%BACKEND_PORT% .*LISTENING"') do set "BACKEND_PORT_IN_USE=1"
if "%BACKEND_PORT_IN_USE%"=="1" if "%BACKEND_PORT%"=="8000" if "%BACKEND_PORT%"=="%BACKEND_PORT%" (
  echo [WARN] Port %BACKEND_PORT% is already in use. Switching backend port to 8001.
  set "BACKEND_PORT=8001"
)
set "BACKEND_PORT_IN_USE="

set "FRONTEND_PORT=%FRONTEND_PORT%"
if "%FRONTEND_PORT%"=="" set "FRONTEND_PORT=4200"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%FRONTEND_PORT% .*LISTENING"') do set "FRONTEND_PORT_IN_USE=1"
if "%FRONTEND_PORT_IN_USE%"=="1" if "%FRONTEND_PORT%"=="4200" if "%FRONTEND_PORT%"=="%FRONTEND_PORT%" (
  echo [WARN] Port %FRONTEND_PORT% is already in use. Switching frontend port to 4201.
  set "FRONTEND_PORT=4201"
)
set "FRONTEND_PORT_IN_USE="

set "DATABASE_URL=sqlite:///./saihai.db"
if "%SAIHAI_API_BASE_URL%"=="" set "SAIHAI_API_BASE_URL=http://localhost:%BACKEND_PORT%/api/v1"

if not exist "%ROOT%\frontend\node_modules" (
  echo [WARN] frontend\\node_modules not found. Run dev-setup.bat first.
)

if not exist "%ROOT%\backend\.venv" (
  echo [WARN] backend\\.venv not found. Run dev-setup.bat first.
)

echo Starting backend...
pushd "%ROOT%\backend" >nul
if errorlevel 1 (
  echo [ERROR] backend directory not found: "%ROOT%\backend"
  goto :pause_on_error
)
if /i not "%SKIP_DB_INIT%"=="1" (
  echo Initializing local database...
  %DB_CMD% up
  if errorlevel 1 goto :pause_on_error
  %DB_CMD% seed
  if errorlevel 1 goto :pause_on_error
)
if /i "%NO_NEW_WINDOW%"=="1" (
  start "" /b cmd /c %BACKEND_CMD% --port %BACKEND_PORT%
) else (
  start "SaihAI Backend" cmd /k %BACKEND_CMD% --port %BACKEND_PORT%
)
popd >nul

echo Starting frontend...
pushd "%ROOT%\frontend" >nul
if errorlevel 1 (
  echo [ERROR] frontend directory not found: "%ROOT%\frontend"
  goto :pause_on_error
)
if /i "%NO_NEW_WINDOW%"=="1" (
  start "" /b cmd /c npm run start -- --port %FRONTEND_PORT%
) else (
  start "SaihAI Frontend" cmd /k npm run start -- --port %FRONTEND_PORT%
)
popd >nul

echo.
echo Backend:  http://localhost:%BACKEND_PORT%/api/health
echo Frontend: http://localhost:%FRONTEND_PORT%
exit /b 0

:pause_on_error
echo.
echo Press any key to close...
pause >nul
exit /b 1
