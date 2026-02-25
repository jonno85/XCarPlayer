@echo off
setlocal
:: run_spotify_downloader.bat
:: Script to create virtual environment, install dependencies, and run spotify_downloader.py

echo ============================================================
echo Spotify Downloader Setup ^& Run (Windows)
echo ============================================================

:: Make sure we are in the script's directory
cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in your PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist "env\" (
    echo [1/4] Creating virtual environment 'env'...
    python -m venv env
) else (
    echo [1/4] Virtual environment 'env' already exists.
)

:: Activate virtual environment
echo [2/4] Activating virtual environment...
call env\Scripts\activate.bat

:: Install or upgrade dependencies
echo [3/4] Installing dependencies (spotdl, spotipy, yt-dlp)...
python -m pip install --upgrade pip spotdl spotipy yt-dlp

:: Run the python script
echo [4/4] Starting download_spotify_playlist.py...
echo ============================================================
python download_spotify_playlist.py

echo ============================================================
pause
