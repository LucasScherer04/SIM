@echo off
title SIM - Scherer Investments Money Server
cd /d "%~dp0"
echo Iniciando servidor SIM (PC e Celular na porta 8000)...
start "" chrome.exe --app=http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
