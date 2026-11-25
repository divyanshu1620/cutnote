@echo off
set "PATH=%PATH%;C:\Program Files\nodejs"
start "CutNote Backend" cmd /k "cd /d %~dp0backend && .\venv\Scripts\uvicorn.exe app.main:app --reload"
start "CutNote Frontend" cmd /k "cd /d %~dp0cutnote-frontend && npm run dev"
timeout /t 3 /nobreak >nul
start http://localhost:5173
