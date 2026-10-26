@rem Tudo numa linha: a atualização pode reescrever este arquivo enquanto ele roda
@cd /d "%~dp0" & powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0atualizar.ps1" & echo. & pause
