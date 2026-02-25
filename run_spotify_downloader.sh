#!/bin/bash
# run_spotify_downloader.sh
# Script to create virtual environment, install dependencies, and run spotify_downloader.py

# Exit on first error
set -e

# Make sure we are in the script's directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"

echo "============================================================"
echo "Spotify Downloader Setup & Run (macOS/Linux)"
echo "============================================================"

# Check if Python is installed
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python is not installed or not in your PATH."
    echo "Please install Python from https://www.python.org/downloads/"
    exit 1
fi

echo "[1/4] Using $PYTHON_CMD..."

# Create virtual environment if it doesn't exist
if [ ! -d "env" ]; then
    echo "[1/4] Creating virtual environment 'env'..."
    $PYTHON_CMD -m venv env
else
    echo "[1/4] Virtual environment 'env' already exists."
fi

# Activate virtual environment
echo "[2/4] Activating virtual environment..."
source env/bin/activate

# Install or upgrade dependencies
echo "[3/4] Installing dependencies (spotdl, spotipy, yt-dlp)..."
pip install --upgrade pip spotdl spotipy yt-dlp

# Run the python script
echo "[4/4] Starting download_spotify_playlist.py..."
echo "============================================================"
python download_spotify_playlist.py
