@echo off
cd /d "%~dp0"

echo Pornesc serviciile...
docker compose up -d --build

echo.
echo Starea serviciilor:
docker compose ps

echo.
echo n8n: http://localhost:5678
pause