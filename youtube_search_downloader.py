#!/usr/bin/env python3
"""
YouTube Search & Download Music
Given a list of song names, search YouTube and download them automatically.
Great for downloading playlists without API rate limits!

Requirements:
    pip install yt-dlp

Usage:
    python youtube_search_downloader.py
    
You can either:
    1. Provide a text file with song names (one per line)
    2. Enter song names manually
"""

import subprocess
import sys
import os

def check_ytdlp_installed():
    """Check if yt-dlp is installed"""
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def install_ytdlp():
    """Install yt-dlp package"""
    print("Installing yt-dlp...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'yt-dlp'])
        print("✓ yt-dlp installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("✗ Failed to install yt-dlp")
        return False

def download_song(song_name, output_dir='downloads'):
    """
    Search YouTube for a song and download it
    
    Args:
        song_name (str): Song name (artist and title)
        output_dir (str): Directory to save the song
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # yt-dlp can search and download in one command
        search_url = f"ytsearch:{song_name}"
        
        subprocess.run([
            'yt-dlp',
            '-x',  # Extract audio only
            '--audio-format', 'mp3',
            '--audio-quality', '192',
            '-o', os.path.join(output_dir, '%(title)s.%(ext)s'),
            '--no-warnings',
            '-q',  # Quiet mode
            search_url
        ], check=True, capture_output=True)
        
        print(f"  ✓ Downloaded: {song_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed: {song_name}")
        return False

def download_from_file(file_path, output_dir='downloads'):
    """
    Download songs from a text file
    
    Args:
        file_path (str): Path to text file with song names (one per line)
        output_dir (str): Directory to save downloaded songs
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return
    
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")
    
    # Read song names
    with open(file_path, 'r') as f:
        songs = [line.strip() for line in f if line.strip()]
    
    if not songs:
        print("Error: No songs found in file")
        return
    
    print(f"\nDownloading {len(songs)} songs...\n")
    
    successful = 0
    failed = 0
    
    for i, song in enumerate(songs, 1):
        print(f"[{i}/{len(songs)}] {song}")
        if download_song(song, output_dir):
            successful += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Download complete!")
    print(f"  ✓ Successful: {successful}")
    print(f"  ✗ Failed: {failed}")
    print(f"  Saved to: {output_dir}")

def download_manual(output_dir='downloads'):
    """
    Let user enter song names manually
    
    Args:
        output_dir (str): Directory to save downloaded songs
    """
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")
    
    print("\nEnter song names (one per line).")
    print("Type 'done' when finished.\n")
    
    songs = []
    while True:
        song = input("Song name: ").strip()
        if song.lower() == 'done':
            break
        if song:
            songs.append(song)
    
    if not songs:
        print("No songs entered")
        return
    
    print(f"\nDownloading {len(songs)} songs...\n")
    
    successful = 0
    failed = 0
    
    for i, song in enumerate(songs, 1):
        print(f"[{i}/{len(songs)}] {song}")
        if download_song(song, output_dir):
            successful += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Download complete!")
    print(f"  ✓ Successful: {successful}")
    print(f"  ✗ Failed: {failed}")
    print(f"  Saved to: {output_dir}")

def main():
    print("=" * 60)
    print("YouTube Search & Download Music")
    print("=" * 60)
    
    # Check if yt-dlp is installed
    if not check_ytdlp_installed():
        print("yt-dlp is not installed.")
        install = input("Would you like to install it now? (y/n): ").lower()
        if install == 'y':
            if not install_ytdlp():
                sys.exit(1)
        else:
            print("Please install yt-dlp manually: pip install yt-dlp")
            sys.exit(1)
    
    # Get output directory
    output_dir = input("\nEnter output directory (default: 'downloads'): ").strip()
    if not output_dir:
        output_dir = 'downloads'
    
    # Choose input method
    print("\nSelect input method:")
    print("  1. From text file (one song per line)")
    print("  2. Manual entry")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == '1':
        file_path = input("Enter path to text file: ").strip()
        download_from_file(file_path, output_dir)
    elif choice == '2':
        download_manual(output_dir)
    else:
        print("Invalid choice")
        sys.exit(1)

if __name__ == "__main__":
    main()
