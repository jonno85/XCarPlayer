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
echo "[3/4] Installing dependencies..."
pip install --upgrade pip spotdl spotipy yt-dlp requests beautifulsoup4

# Install ffmpeg if missing (required for mp3/m4a conversion)
if ! command -v ffmpeg &>/dev/null; then
    if command -v brew &>/dev/null; then
        echo "ffmpeg not found. Installing via Homebrew..."
        brew install ffmpeg
    else
        echo "Warning: ffmpeg not found and Homebrew is not available."
        echo "Install ffmpeg manually: https://ffmpeg.org/download.html"
    fi
fi

# Select which downloader to run
echo ""
echo "============================================================"
echo "Select downloader:"
echo "  1. Spotify playlist downloader (download_spotify_playlist.py)"
echo "  2. YouTube search downloader with Spotify/Beatport URL support (youtube_search_downloader.py)"
echo "  3. Beatport playlist downloader (download_beatport_playlist.py)"
echo "============================================================"
read -rp "Enter choice (1, 2 or 3): " CHOICE

echo "[4/4] Starting downloader..."
echo "============================================================"
if [ "$CHOICE" = "1" ]; then
    python download_spotify_playlist.py
elif [ "$CHOICE" = "2" ]; then
    python youtube_search_downloader.py
elif [ "$CHOICE" = "3" ]; then
    python download_beatport_playlist.py
else
    echo "Invalid choice."
    exit 1
fi
