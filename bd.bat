@echo off
echo Dang khoi dong Backend...
start "Backend" cmd /k "uvicorn main:app --reload --port 8000"

echo Dang khoi dong Frontend...
start "Frontend" cmd /k "cd frontend && npm run build && npm run dev"

echo Da khoi dong xong!
pause