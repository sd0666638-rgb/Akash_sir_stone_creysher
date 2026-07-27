@echo off
title Stone Crusher ERP Control
set "PROJECT_ROOT=%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\StoneCrusher-Control.ps1" -Action Menu
exit /b %ERRORLEVEL%
