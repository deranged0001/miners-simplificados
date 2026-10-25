@echo off
rem Dois cliques aqui instalam tudo. O trabalho de verdade fica no instalar.ps1.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
pause
