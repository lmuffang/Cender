@echo off
echo Starting CV Email Sender...
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

echo Docker is running. Starting application...
echo.

REM Create necessary directories
if not exist "data" mkdir data
if not exist "credentials" mkdir credentials
if not exist "backend" mkdir backend
if not exist "frontend" mkdir frontend

REM Start Docker Compose
docker-compose up --build

pause