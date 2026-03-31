#!/usr/bin/env python3
"""
Beatport Playlist to YouTube Converter
Extracts songs from a Beatport playlist page for YouTube download.

Requirements:
    pip install requests beautifulsoup4

No API key needed — reads the public playlist page directly.
"""

import subprocess
import sys
import json


def check_deps_installed():
    try:
        import requests
        import bs4
        return True
    except ImportError:
        return False


def install_deps():
    print("Installing requests and beautifulsoup4...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'requests', 'beautifulsoup4'])
        print("✓ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("✗ Failed to install dependencies")
        return False


def get_playlist_songs(playlist_url):
    """
    Get all songs from a public Beatport playlist.

    Beatport uses Next.js, which embeds all page data in a
    <script id="__NEXT_DATA__"> JSON blob — no browser/API key needed.

    Args:
        playlist_url (str): Beatport playlist URL

    Returns:
        list: List of dicts with 'artist', 'title', 'full_name' keys, or None on error
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print("Error: requests/beautifulsoup4 not installed")
        return None

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'en-US,en;q=0.9',
    }

    print(f"\nFetching Beatport playlist...")
    try:
        response = requests.get(playlist_url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching page: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Beatport (Next.js) embeds all data in <script id="__NEXT_DATA__">
    next_data_tag = soup.find('script', id='__NEXT_DATA__')
    if not next_data_tag:
        print("Error: Could not find __NEXT_DATA__ in page. The page structure may have changed.")
        return None

    try:
        data = json.loads(next_data_tag.string)
    except json.JSONDecodeError as e:
        print(f"Error parsing page data: {e}")
        return None

    songs = _extract_tracks(data)

    if not songs:
        print("Error: No tracks found. The playlist may be private or the page structure changed.")
        return None

    return songs


def _extract_tracks(data):
    """
    Recursively walk the JSON tree looking for objects that look like
    Beatport tracks: have both 'name' and 'artists' keys.
    """
    songs = []
    seen = set()

    def walk(node):
        if isinstance(node, dict):
            name = node.get('name', '').strip()
            artists = node.get('artists')
            # A track node has 'name' (str) and 'artists' (non-empty list)
            if name and isinstance(artists, list) and artists:
                artist_name = ''
                if isinstance(artists[0], dict):
                    artist_name = artists[0].get('name', '').strip()
                elif isinstance(artists[0], str):
                    artist_name = artists[0].strip()

                key = (artist_name.lower(), name.lower())
                if artist_name and key not in seen:
                    seen.add(key)
                    songs.append({
                        'artist': artist_name,
                        'title': name,
                        'full_name': f"{artist_name} - {name}"
                    })
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return songs


def save_song_list(songs, output_file='songs.txt'):
    try:
        with open(output_file, 'w') as f:
            for song in songs:
                f.write(song['full_name'] + '\n')
        print(f"\n✓ Saved {len(songs)} songs to: {output_file}")
        return True
    except Exception as e:
        print(f"Error saving file: {e}")
        return False


def show_preview(songs, limit=10):
    print(f"\nPlaylist Preview ({min(limit, len(songs))} of {len(songs)} songs):")
    print("-" * 60)
    for i, song in enumerate(songs[:limit], 1):
        print(f"{i:2d}. {song['full_name']}")
    if len(songs) > limit:
        print(f"... and {len(songs) - limit} more")
    print("-" * 60)


def main():
    print("=" * 60)
    print("Beatport Playlist to YouTube Converter")
    print("=" * 60)

    if not check_deps_installed():
        install = input("\nrequests/beautifulsoup4 not installed. Install now? (y/n): ").lower()
        if install == 'y':
            if not install_deps():
                sys.exit(1)
        else:
            sys.exit(1)

    playlist_url = input("\nEnter Beatport playlist URL: ").strip()
    if not playlist_url:
        print("Error: No URL provided")
        sys.exit(1)

    songs = get_playlist_songs(playlist_url)
    if not songs:
        sys.exit(1)

    show_preview(songs)

    output_file = input("\nEnter output filename (default: 'songs.txt'): ").strip()
    if not output_file:
        output_file = 'songs.txt'

    if save_song_list(songs, output_file):
        print("\n" + "=" * 60)
        print("Next steps:")
        print("=" * 60)
        print(f"1. Run: python youtube_search_downloader.py")
        print(f"2. Select: Option 1 (From text file)")
        print(f"3. Enter filename: {output_file}")
        print("=" * 60)


if __name__ == "__main__":
    main()
