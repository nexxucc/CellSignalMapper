@echo off
REM Cell Signal Mapper - Windows Test Launcher
REM Uses Anaconda Python with all dependencies

echo ========================================
echo Cell Signal Mapper - Testing on Windows
echo ========================================
echo.

REM Use pip3's Python (Anaconda)
pip3 --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: pip3 not found
    echo Please install Anaconda or Python with pip
    pause
    exit /b 1
)

REM Run with Anaconda Python
python src\main.py %*
