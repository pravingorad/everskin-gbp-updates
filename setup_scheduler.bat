@echo off
:: ============================================================
::  EVERSKIN GBP AUTO-POST — WINDOWS TASK SCHEDULER SETUP
::  Run this as Administrator ONCE to schedule daily posting.
::  Posts every day at 9:00 AM automatically.
:: ============================================================

echo.
echo ============================================================
echo   EVERSKIN GBP — Setting up Daily Task Scheduler
echo ============================================================
echo.

:: Get the current directory (where scripts live)
SET SCRIPT_DIR=%~dp0
SET PYTHON_SCRIPT=%SCRIPT_DIR%run_daily.py

:: Find Python path
FOR /F "tokens=*" %%i IN ('where python') DO SET PYTHON_PATH=%%i

IF "%PYTHON_PATH%"=="" (
    echo ERROR: Python not found. Please install Python first.
    pause
    exit /b 1
)

echo Python found at: %PYTHON_PATH%
echo Script path    : %PYTHON_SCRIPT%
echo.

:: Delete existing task if it exists (clean reinstall)
schtasks /delete /tn "EverskinGBPPost" /f >nul 2>&1

:: Create the scheduled task
:: Runs daily at 9:00 AM, starts immediately if missed
schtasks /create ^
    /tn "EverskinGBPPost" ^
    /tr "\"%PYTHON_PATH%\" \"%PYTHON_SCRIPT%\"" ^
    /sc DAILY ^
    /st 09:00 ^
    /ru "%USERNAME%" ^
    /rl HIGHEST ^
    /f ^
    /sd %date% ^
    /it

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo   SUCCESS! Task scheduled.
    echo   Name    : EverskinGBPPost
    echo   Runs    : Every day at 9:00 AM
    echo   Script  : %PYTHON_SCRIPT%
    echo ============================================================
    echo.
    echo To verify: Open Task Scheduler and look for "EverskinGBPPost"
    echo To test now: schtasks /run /tn "EverskinGBPPost"
    echo To remove : schtasks /delete /tn "EverskinGBPPost" /f
    echo.
) ELSE (
    echo.
    echo ERROR: Failed to create task. Try running as Administrator.
    echo Right-click setup_scheduler.bat and select "Run as Administrator"
    echo.
)

pause
