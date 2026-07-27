@echo off
setlocal
cd /d "%~dp0"

echo Stone Crusher ERP - New Computer Setup
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup\setup-windows.ps1" %*
set "SETUP_EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%SETUP_EXIT_CODE%"=="0" (
    echo Setup did not complete. Review the message above, correct the issue, and run this file again.
) else (
    echo Setup finished successfully. Use Start Stone Crusher.cmd to open the application.
)
echo.
pause
exit /b %SETUP_EXIT_CODE%
