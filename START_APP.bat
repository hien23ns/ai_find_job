@echo off
setlocal
title ai-find-job Launcher

cd /d "%~dp0"

REM Find Python executable
set "PY_CMD=python"
where %PY_CMD% >nul 2>nul
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    ) else (
        where py >nul 2>nul
        if %errorlevel% equ 0 (
            set "PY_CMD=py -3"
        ) else (
            echo [ERROR] Python not found in PATH or standard installation directories.
            echo Please install Python 3.11+ and check "Add Python to PATH".
            echo.
            pause
            exit /b 1
        )
    )
)

REM Run Python launcher with UTF-8 encoding
set PYTHONIOENCODING=utf-8
%PY_CMD% -m src.launcher %*
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with error code %errorlevel%.
    pause
    exit /b %errorlevel%
)

endlocal
exit /b 0
