@echo off
REM OTC Signal Engine - Windows Run Script
REM Usage: run.bat [mode]
REM Modes: manual (default), simulate, screen

setlocal

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Parse arguments
set MODE=manual
if "%1"=="simulate" set MODE=simulate
if "%1"=="screen" set MODE=screen
if "%1"=="-s" set MODE=simulate
if "%1"=="-c" set MODE=screen

REM Run the engine
echo Starting OTC Signal Engine in %MODE% mode...
echo.

if "%MODE%"=="simulate" (
    python src\main.py --simulate
) else if "%MODE%"=="screen" (
    python src\main.py --screen
) else (
    python src\main.py
)

echo.
echo Engine stopped.
pause
