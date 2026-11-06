' ============================================================================
' SIM - Inicializador Silencioso para Windows (sem janela de terminal aberta)
' Inicia o servidor FastAPI em segundo plano (se ainda nao estiver rodando)
' e abre a interface do SIM em modo aplicativo.
' ============================================================================
Option Explicit

Dim fso, shell, appDir, checkCmd, rc
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = appDir

' Verifica se a porta 8000 ja esta escutando
checkCmd = "cmd.exe /c netstat -ano | findstr "":8000 "" | findstr ""LISTENING"""
rc = shell.Run(checkCmd, 0, True)

If rc <> 0 Then
    ' Inicia o servidor FastAPI em background oculto (0 = oculto, False = nao bloqueia)
    shell.Run "cmd.exe /c python -m uvicorn app.main:app --host 0.0.0.0 --port 8000", 0, False
    WScript.Sleep 1800
End If

' Tenta abrir em modo App no Chrome ou Edge; caso contrario abre no navegador padrao
On Error Resume Next
Err.Clear
shell.Run "chrome.exe --app=http://localhost:8000", 1, False
If Err.Number <> 0 Then
    Err.Clear
    shell.Run "msedge.exe --app=http://localhost:8000", 1, False
    If Err.Number <> 0 Then
        Err.Clear
        shell.Run "http://localhost:8000", 1, False
    End If
End If
On Error GoTo 0
