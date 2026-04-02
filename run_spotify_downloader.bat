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
echo [3/4] Installing dependencies...
python -m pip install --upgrade pip spotdl spotipy yt-dlp requests beautifulsoup4

:: Install ffmpeg if missing (required for mp3/m4a conversion)
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    where winget >nul 2>&1
    if %errorlevel% equ 0 (
        echo ffmpeg not found. Installing via winget...
        winget install --id Gyan.FFmpeg -e --silent
    ) else (
        echo Warning: ffmpeg not found. Install it from https://ffmpeg.org/download.html
    )
)

:: Select which downloader to run
echo.
echo ============================================================
echo Select downloader:
echo   1. Spotify playlist downloader (download_spotify_playlist.py)
echo   2. YouTube search downloader with Spotify URL support (youtube_search_downloader.py)
echo ============================================================
set /p CHOICE="Enter choice (1 or 2): "

echo [4/4] Starting downloader...
echo ============================================================
if "%CHOICE%"=="1" (
    python download_spotify_playlist.py
) else if "%CHOICE%"=="2" (
    python youtube_search_downloader.py
) else (
    echo Invalid choice.
    exit /b 1
)

echo ============================================================
pause
