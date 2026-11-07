Option Explicit
Dim shell, files, scriptPath, command, result
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
scriptPath = files.BuildPath(files.GetParentFolderName(WScript.ScriptFullName), "start_quota_supervisor.ps1")
command = Chr(34) & shell.ExpandEnvironmentStrings("%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe") & Chr(34) _
    & " -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File " _
    & Chr(34) & scriptPath & Chr(34)
' GUI host + hidden child: no console is created on logon. Preserve exit code for Task Scheduler.
result = shell.Run(command, 0, True)
WScript.Quit result
