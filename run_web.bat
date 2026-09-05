@echo off
cd /d "%~dp0"
:loop
"venv\Scripts\python.exe" -m uvicorn app.web.server:app --host 127.0.0.1 --port 8000 >> logs\web.log 2>&1
echo %date% %time% Web server exited, restarting in 10 seconds... >> logs\web.log
timeout /t 10 /nobreak >nul
goto loop
