' ============================================================================
' SIM - Inicializador Silencioso para Windows (sem janela de terminal aberta)
' Inicia o servidor FastAPI em segundo plano (se ainda nao estiver rodando),
' aguarda o servidor responder HTTP na porta 8000 e abre a interface em modo App.
' ============================================================================
Option Explicit

Dim fso, shell, appDir
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = appDir

Function IsPortListening()
    Dim checkCmd, rc
    checkCmd = "cmd.exe /c netstat -ano | findstr "":8000 "" | findstr ""LISTENING"""
    rc = shell.Run(checkCmd, 0, True)
    If rc = 0 Then
        IsPortListening = True
    Else
        IsPortListening = False
    End If
End Function

Function IsServerReady()
    IsServerReady = False
    If Not IsPortListening() Then
        Exit Function
    End If

    On Error Resume Next
    Err.Clear
    Dim http, status
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    If Err.Number <> 0 Then
        Err.Clear
        Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    End If
    If Err.Number <> 0 Then
        Err.Clear
        On Error GoTo 0
        Exit Function
    End If
    If http Is Nothing Then
        On Error GoTo 0
        Exit Function
    End If

    http.setTimeouts 1000, 1000, 1000, 1000
    http.Open "GET", "http://127.0.0.1:8000/manifest.json", False
    http.Send
    If Err.Number = 0 Then
        status = 0
        status = http.Status
        If Err.Number = 0 Then
            If status >= 200 Then
                If status < 500 Then
                    IsServerReady = True
                End If
            End If
        End If
    End If
    Err.Clear
    On Error GoTo 0
End Function

' Verifica se o servidor ja esta pronto e respondendo HTTP na porta 8000
If Not IsServerReady() Then
    If Not IsPortListening() Then
        ' Inicia o servidor FastAPI em background oculto (0 = oculto, False = nao bloqueia)
        shell.Run "cmd.exe /c python -m uvicorn app.main:app --host 0.0.0.0 --port 8000", 0, False
    End If

    ' Aguarda ate 30 segundos (100 x 300ms) ate o servidor responder HTTP de fato
    Dim attempts
    For attempts = 1 To 100
        If IsServerReady() Then
            Exit For
        End If
        WScript.Sleep 300
    Next
End If

' Localiza Chrome ou Edge nos caminhos padrao do Windows para abrir em modo App
Dim browserCandidates(4), browserPath, candidate, i
browserCandidates(0) = shell.ExpandEnvironmentStrings("%ProgramFiles%\Google\Chrome\Application\chrome.exe")
browserCandidates(1) = shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe")
browserCandidates(2) = shell.ExpandEnvironmentStrings("%LocalAppData%\Google\Chrome\Application\chrome.exe")
browserCandidates(3) = shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")
browserCandidates(4) = shell.ExpandEnvironmentStrings("%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")

browserPath = ""
For i = 0 To UBound(browserCandidates)
    candidate = browserCandidates(i)
    If fso.FileExists(candidate) Then
        browserPath = candidate
        Exit For
    End If
Next

On Error Resume Next
Err.Clear
If browserPath <> "" Then
    shell.Run """" & browserPath & """ --app=http://localhost:8000", 1, False
Else
    shell.Run "chrome.exe --app=http://localhost:8000", 1, False
    If Err.Number <> 0 Then
        Err.Clear
        shell.Run "msedge.exe --app=http://localhost:8000", 1, False
        If Err.Number <> 0 Then
            Err.Clear
            shell.Run "http://localhost:8000", 1, False
        End If
    End If
End If
On Error GoTo 0
