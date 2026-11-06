@echo off
chcp 65001 >nul
title SIM - Instalador e Atualizador Windows
cd /d "%~dp0"

echo ============================================================================
echo   SIM - Scherer Investments Money ^| Instalador e Atualizador (Windows)
echo ============================================================================
echo.

:: 1. Verifica Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Python 3.11+ nao encontrado no PATH.
    echo Baixe e instale em https://www.python.org/downloads/ marcando "Add Python to PATH".
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [OK] Detectado: %%i

:: 2. Backup preventivo caso ja exista banco de dados
if exist "sim_database.db" (
    echo.
    echo [1/4] Criando backup preventivo do banco de dados antes de atualizar...
    python -c "from app.backup_service import create_backup; b = create_backup(label='pre_update'); print('      Backup salvo em:', b['backup_dir'], '| Integridade:', b['integrity_check'])"
) else (
    echo.
    echo [1/4] Banco sim_database.db ainda nao existe ^(sera criado automaticamente no primeiro uso^).
)

:: 3. Instala/atualiza dependencias do requirements.txt
echo.
echo [2/4] Verificando e instalando pacotes do requirements.txt...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Falha ao instalar pacotes do requirements.txt. Verifique sua conexao com a internet.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas e atualizadas com sucesso.

:: 4. Inicializa/migra esquema do banco SQLite de forma segura
echo.
echo [3/4] Aplicando migracoes seguras do banco de dados...
python -c "from app.database import init_db; init_db(); print('      Esquema SQLite verificado com sucesso.')"

:: 5. Cria atalho na Area de Trabalho apontando para Iniciar_SIM_Silencioso.vbs
echo.
echo [4/4] Criando atalho na Area de Trabalho ^(SIM - Investimentos^)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
  "$lnk = $ws.CreateShortcut((Join-Path $desktop 'SIM - Investimentos.lnk')); " ^
  "$lnk.TargetPath = 'wscript.exe'; " ^
  "$lnk.Arguments = '\"' + (Join-Path '%~dp0' 'Iniciar_SIM_Silencioso.vbs') + '\"'; " ^
  "$lnk.WorkingDirectory = '%~dp0'; " ^
  "$lnk.Description = 'SIM - Sistema de Inteligencia de Mercado e Gestao de Carteira'; " ^
  "if (Test-Path (Join-Path '%~dp0' 'static\icon.ico')) { $lnk.IconLocation = (Join-Path '%~dp0' 'static\icon.ico') }; " ^
  "$lnk.Save(); " ^
  "Write-Host '      Atalho criado em:' (Join-Path $desktop 'SIM - Investimentos.lnk')"

echo.
echo ============================================================================
echo   Instalacao / Atualizacao concluida com sucesso!
echo   Voce pode abrir o SIM pelo atalho "SIM - Investimentos" na Area de Trabalho
echo   ou executando Iniciar_SIM.bat.
echo ============================================================================
echo.
pause
