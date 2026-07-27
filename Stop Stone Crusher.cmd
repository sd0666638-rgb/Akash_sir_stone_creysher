@echo off
title Stop Stone Crusher ERP
set "PROJECT_ROOT=%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\StoneCrusher-Control.ps1" -Action Stop
set "RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESULT%
