#!/usr/bin/env python3
"""
Spotify Playlist Downloader
Combines spotify_to_youtube_converter and youtube_search_downloader
"""

import sys
import os
from spotify_to_youtube_converter import (
    check_spotipy_installed, 
    install_spotipy, 
    get_spotify_credentials, 
    get_playlist_songs, 
    show_preview,
    save_song_list
)
from youtube_search_downloader import (
    check_ytdlp_installed, 
    install_ytdlp, 
    download_from_file
)

def main():
    print("=" * 60)
    print("Spotify to YouTube Music Downloader (Combined)")
    print("=" * 60)
    
    # 1. Dependency Checks
    if not check_spotipy_installed():
        install = input("\nspotipy is not installed. Install now? (y/n): ").lower()
        if install == 'y':
            if not install_spotipy(): sys.exit(1)
        else:
            sys.exit(1)
            
    if not check_ytdlp_installed():
        install = input("\nyt-dlp is not installed. Install now? (y/n): ").lower()
        if install == 'y':
            if not install_ytdlp(): sys.exit(1)
        else:
            sys.exit(1)
            
    # 2. Get Spotify Credentials
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        client_id, client_secret = get_spotify_credentials()
        if not client_id or not client_secret:
            sys.exit(1)
            
    # 3. Get Playlist URL
    playlist_url = input("\nEnter Spotify playlist URL: ").strip()
    if not playlist_url:
        print("Error: No URL provided")
        sys.exit(1)
        
    # Get songs from Spotify
    songs = get_playlist_songs(client_id, client_secret, playlist_url)
    if not songs:
        sys.exit(1)
        
    show_preview(songs)
    
    # 4. Settings for output
    output_file = 'temp_spotify_songs.txt'
    output_dir = input("\nEnter output directory (default: 'downloads'): ").strip()
    if not output_dir:
        output_dir = 'downloads'
        
    # Extract and save list to local file
    if not save_song_list(songs, output_file):
        print("Failed to save temporary song list.")
        sys.exit(1)
        
    # 5. Download songs from list using youtube_search_downloader
    print(f"\nStarting download of {len(songs)} songs to '{output_dir}' directory...")
    download_from_file(output_file, output_dir)
    
    # 6. Cleanup
    cleanup = input(f"\nDo you want to delete the temporary song list file '{output_file}'? (y/n): ").lower()
    if cleanup == 'y':
        try:
            os.remove(output_file)
            print(f"Deleted {output_file}")
        except Exception as e:
            print(f"Could not delete file: {e}")
            
    print("\nAll done!")

if __name__ == "__main__":
    main()
