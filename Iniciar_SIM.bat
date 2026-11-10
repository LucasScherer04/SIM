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

:: Verifica se a porta 8000 ja esta em uso (servidor ja rodando em segundo plano)
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Servidor SIM ja esta ativo na porta 8000. Abrindo janela do aplicativo...
    call :OPEN_BROWSER
    timeout /t 2 >nul
    exit /b 0
)

:: Dispara verificador em segundo plano que aguarda o servidor responder antes de abrir o navegador
start "" /b powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command ^
  "for ($i = 0; $i -lt 100; $i++) { " ^
  "  try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/manifest.json' -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop; if ($r.StatusCode -eq 200) { break } } catch {} " ^
  "  Start-Sleep -Milliseconds 300 " ^
  "}; " ^
  "$candidates = @(" ^
  "  (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe')," ^
  "  (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe')," ^
  "  (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')," ^
  "  (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe')," ^
  "  (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe')" ^
  "); " ^
  "$found = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1; " ^
  "if ($found) { Start-Process -FilePath $found -ArgumentList '--app=http://localhost:8000' } else { Start-Process 'http://localhost:8000' }"

echo Iniciando servidor SIM local na porta 8000...
echo A janela do aplicativo abrira automaticamente assim que o servidor estiver pronto.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
exit /b 0

:OPEN_BROWSER
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app=http://localhost:8000
    goto :EOF
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --app=http://localhost:8000
    goto :EOF
)
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    start "" "%LocalAppData%\Google\Chrome\Application\chrome.exe" --app=http://localhost:8000
    goto :EOF
)
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app=http://localhost:8000
    goto :EOF
)
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app=http://localhost:8000
    goto :EOF
)
start "" "http://localhost:8000"
goto :EOF
