@echo off
setlocal
rem Start Music Library Downloader on Windows.
cd /d "%~dp0"

py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
  py -3 "%~dp0launch.py"
) else (
  python --version >nul 2>&1
  if %errorlevel% equ 0 (
    python "%~dp0launch.py"
  ) else (
    echo Python 3.9+ is needed once to start this app:
    echo https://www.python.org/downloads/
  )
)

if %errorlevel% neq 0 pause
