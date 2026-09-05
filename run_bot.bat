@echo off
cd /d "%~dp0"
:loop
ipconfig /flushdns >nul 2>&1
"venv\Scripts\python.exe" main.py >> logs\bot.log 2>&1
echo %date% %time% Bot exited, restarting in 30 seconds... >> logs\bot.log
timeout /t 30 /nobreak >nul
goto loop
