#!/usr/bin/env python3
"""
Beatport Playlist Downloader
Combines beatport_to_youtube_converter and youtube_search_downloader
"""

import sys
import os
from beatport_to_youtube_converter import (
    check_deps_installed,
    install_deps,
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
    print("Beatport to YouTube Music Downloader")
    print("=" * 60)

    # 1. Dependency checks
    if not check_deps_installed():
        install = input("\nrequests/beautifulsoup4 not installed. Install now? (y/n): ").lower()
        if install == 'y':
            if not install_deps():
                sys.exit(1)
        else:
            sys.exit(1)

    if not check_ytdlp_installed():
        install = input("\nyt-dlp is not installed. Install now? (y/n): ").lower()
        if install == 'y':
            if not install_ytdlp():
                sys.exit(1)
        else:
            sys.exit(1)

    # 2. Cookies & playlist URL
    cookies_file = None
    use_cookies = input("\nUse a cookies file for Beatport subscription (y/n, default: n): ").strip().lower()
    if use_cookies == 'y':
        cookies_file = input("Enter path to cookies file (default: cookies.txt): ").strip()
        if not cookies_file:
            cookies_file = 'cookies.txt'
        if not os.path.exists(cookies_file):
            print(f"Warning: Cookies file '{cookies_file}' not found.")
            cookies_file = None

    playlist_url = input("\nEnter Beatport playlist URL: ").strip()
    if not playlist_url:
        print("Error: No URL provided")
        sys.exit(1)

    # 3. Fetch tracks
    songs = get_playlist_songs(playlist_url, cookies_file=cookies_file)
    if not songs:
        sys.exit(1)

    show_preview(songs)

    # 4. Output settings
    output_file = 'temp_beatport_songs.txt'
    output_dir = input("\nEnter output directory (default: 'downloads'): ").strip()
    if not output_dir:
        output_dir = 'downloads'

    if not save_song_list(songs, output_file):
        print("Failed to save temporary song list.")
        sys.exit(1)

    # 5. Download via YouTube search
    print(f"\nStarting download of {len(songs)} songs to '{output_dir}' directory...")
    download_from_file(output_file, output_dir)

    # 6. Cleanup
    cleanup = input(f"\nDelete temporary song list '{output_file}'? (y/n): ").lower()
    if cleanup == 'y':
        try:
            os.remove(output_file)
            print(f"Deleted {output_file}")
        except Exception as e:
            print(f"Could not delete file: {e}")

    print("\nAll done!")


if __name__ == "__main__":
    main()
