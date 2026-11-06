@echo off
chcp 65001 >nul
title SIM - Scherer Investments Money
cd /d "%~dp0"

:: Verifica se o Python esta instalado
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Python nao encontrado no PATH do Windows.
    echo Instale o Python 3.11+ em https://www.python.org/downloads/ marcando "Add Python to PATH".
    pause
    exit /b 1
)

:: Abre o navegador em modo Aplicativo (Chrome, Edge ou navegador padrao)
where chrome.exe >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" chrome.exe --app=http://localhost:8000
) else (
    where msedge.exe >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        start "" msedge.exe --app=http://localhost:8000
    ) else (
        start "" "http://localhost:8000"
    )
)

:: Verifica se a porta 8000 ja esta em uso (servidor ja rodando em segundo plano)
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Servidor SIM ja esta ativo na porta 8000. Janela do aplicativo aberta!
    timeout /t 2 >nul
    exit /b 0
)

echo Iniciando servidor SIM local na porta 8000...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
