#!/usr/bin/env python3
"""
YouTube Search & Download Music
Given a list of song names, search YouTube and download them automatically.
Great for downloading playlists without API rate limits!

Requirements:
    pip install yt-dlp requests beautifulsoup4

Usage:
    python youtube_search_downloader.py

You can either:
    1. Provide a text file with song names (one per line)
    2. Enter song names manually
    3. Provide a Spotify track URL
"""

import subprocess
import sys
import os
import re

def spotify_url_to_song_name(url):
    """
    Extract artist and track name from a Spotify track URL by scraping OG tags.

    Args:
        url (str): Spotify track URL (e.g. https://open.spotify.com/track/...)

    Returns:
        str: Search query like "Artist - Track Name", or None on failure
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print("Missing dependencies. Run: pip install requests beautifulsoup4")
        return None

    if not re.match(r'https?://open\.spotify\.com/track/', url):
        print("Not a valid Spotify track URL.")
        return None

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        print(f"Failed to fetch Spotify page: {exc}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # og:title = track name, og:description = "Artist · Song · Year"
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    if og_title and og_desc:
        track = og_title.get("content", "").strip()
        artist = og_desc.get("content", "").split("·")[0].strip()
        if track and artist:
            return f"{artist} - {track}"

    # Fallback: <title> is "Track Name - song and lyrics by Artist | Spotify"
    title_tag = soup.find("title")
    if title_tag:
        title = re.sub(r"\s*\|.*$", "", title_tag.text)  # strip "| Spotify"
        if " - " in title:
            track, rest = title.split(" - ", 1)
            artist = re.sub(r"^(song and lyrics|lyrics) by\s+", "", rest, flags=re.IGNORECASE).strip()
            if track and artist:
                return f"{artist} - {track}"

    print("Could not extract track info from Spotify page.")
    return None


def check_ffmpeg_installed():
    """Check if ffmpeg is installed"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

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

LOUDNORM_TARGET = 'I=-9:TP=-1.0:LRA=6'
ENCODER_BY_FORMAT = {'mp3': 'libmp3lame', 'm4a': 'aac'}

def _two_pass_loudnorm(path, audio_format):
    """Two-pass EBU R128 normalization in-place. Returns measurement dict or None."""
    import json, tempfile, shutil, re

    # Pass 1: measure
    pass1 = subprocess.run(
        ['ffmpeg', '-hide_banner', '-nostats', '-i', path,
         '-af', f'loudnorm={LOUDNORM_TARGET}:print_format=json',
         '-f', 'null', '-'],
        capture_output=True, check=True,
    )
    stderr = pass1.stderr.decode(errors='replace')
    match = re.search(r'\{[^{}]*"input_i"[^{}]*\}', stderr, re.DOTALL)
    if not match:
        print('    (could not parse loudnorm measurements)')
        return None
    m = json.loads(match.group(0))

    # Pass 2: apply with measured values + linear=true for single-gain normalization
    encoder = ENCODER_BY_FORMAT.get(audio_format, 'copy')
    ext = os.path.splitext(path)[1]
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext, dir=os.path.dirname(path) or '.')
    os.close(tmp_fd)
    filter_str = (
        f"loudnorm={LOUDNORM_TARGET}"
        f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
        f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
        f":offset={m['target_offset']}:linear=true:print_format=summary"
    )
    pass2 = subprocess.run(
        ['ffmpeg', '-hide_banner', '-nostats', '-y', '-i', path,
         '-af', filter_str, '-c:a', encoder, '-b:a', '192k', tmp_path],
        capture_output=True, check=True,
    )
    shutil.move(tmp_path, path)
    return m

def download_song(song_name, output_dir='downloads', audio_format='mp3', normalize=False):
    """
    Search YouTube for a song and download it

    Args:
        song_name (str): Song name (artist and title)
        output_dir (str): Directory to save the song
        audio_format (str): Audio format — 'mp3' or 'm4a'

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        search_url = f"ytsearch:{song_name}"
        output_tmpl = os.path.join(output_dir, '%(title)s.%(ext)s')

        cmd = [
            'yt-dlp', '-x',
            '--audio-format', audio_format,
            '--audio-quality', '192',
            '-o', output_tmpl,
            '--no-warnings', '-q',
            '--print', 'after_move:filepath',
            search_url,
        ]
        result = subprocess.run(cmd, check=True, capture_output=True)
        final_path = result.stdout.decode(errors='replace').strip().splitlines()[-1] if result.stdout else ''

        print(f"  ✓ Downloaded: {song_name}")
        if normalize and final_path and os.path.exists(final_path):
            print('    normalizing (two-pass EBU R128)…')
            m = _two_pass_loudnorm(final_path, audio_format)
            if m:
                print(f"    input_i={m['input_i']} LUFS  tp={m['input_tp']} dBTP  lra={m['input_lra']} LU  → target -9 LUFS")
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors='replace') if e.stderr else ''
        print(f"  ✗ Failed: {song_name}")
        if stderr.strip():
            print(f"    {stderr.strip()}")
        return False

def download_from_file(file_path, output_dir='downloads', audio_format='mp3', normalize=False):
    """
    Download songs from a text file

    Args:
        file_path (str): Path to text file with song names (one per line)
        output_dir (str): Directory to save downloaded songs
        audio_format (str): Audio format — 'mp3' or 'm4a'
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
        if download_song(song, output_dir, audio_format, normalize):
            successful += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"Download complete!")
    print(f"  ✓ Successful: {successful}")
    print(f"  ✗ Failed: {failed}")
    print(f"  Saved to: {output_dir}")

def download_manual(output_dir='downloads', audio_format='mp3', normalize=False):
    """
    Let user enter song names manually

    Args:
        output_dir (str): Directory to save downloaded songs
        audio_format (str): Audio format — 'mp3' or 'm4a'
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
        if download_song(song, output_dir, audio_format, normalize):
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

    # Check if ffmpeg is installed (required for mp3/m4a conversion)
    if not check_ffmpeg_installed():
        print("\nWarning: ffmpeg is not installed. Audio conversion to mp3/m4a will fail.")
        print("Install it with: brew install ffmpeg  (macOS) or https://ffmpeg.org/download.html")

    # Select audio format
    print("\nSelect audio format:")
    print("  1. mp3  (requires ffmpeg)")
    print("  2. m4a  (requires ffmpeg, better quality at same size)")
    fmt_choice = input("\nEnter choice (1 or 2, default: 1): ").strip()
    audio_format = 'm4a' if fmt_choice == '2' else 'mp3'

    norm_choice = input("\nNormalize audio loudness (EBU R128, -9 LUFS / DJ-set)? (y/n, default: n): ").strip().lower()
    normalize = norm_choice == 'y'

    # Get output directory
    output_dir = input("\nEnter output directory (default: 'downloads'): ").strip()
    if not output_dir:
        output_dir = 'downloads'

    # Choose input method
    print("\nSelect input method:")
    print("  1. From text file (one song per line)")
    print("  2. Manual entry")
    print("  3. Spotify or Beatport URL (track or playlist)")

    choice = input("\nEnter choice (1, 2 or 3): ").strip()

    if choice == '1':
        file_path = input("Enter path to text file: ").strip()
        download_from_file(file_path, output_dir, audio_format, normalize)
    elif choice == '2':
        download_manual(output_dir, audio_format, normalize)
    elif choice == '3':
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Ask for cookies if they want to download from Beatport subscription
        cookies_file = None
        use_cookies = input("\nUse a cookies file for Beatport subscription (y/n, default: n): ").strip().lower()
        if use_cookies == 'y':
            cookies_file = input("Enter path to cookies file (default: cookies.txt): ").strip()
            if not cookies_file:
                cookies_file = 'cookies.txt'
            if not os.path.exists(cookies_file):
                print(f"Warning: Cookies file '{cookies_file}' not found.")
                cookies_file = None

        while True:
            url = input("\nEnter Spotify/Beatport URL (or 'exit' to quit): ").strip()
            if url.lower() == 'exit':
                break
            if not url:
                continue

            if 'spotify.com' in url:
                song_name = spotify_url_to_song_name(url)
                if song_name:
                    print(f"Detected: {song_name}")
                    download_song(song_name, output_dir, audio_format, normalize)
            elif 'beatport.com' in url:
                try:
                    from beatport_to_youtube_converter import get_playlist_songs
                    songs = get_playlist_songs(url, cookies_file=cookies_file)
                    if songs:
                        print(f"Detected {len(songs)} tracks from Beatport:")
                        for idx, song in enumerate(songs, 1):
                            print(f"  [{idx}/{len(songs)}] {song['full_name']}")
                            download_song(song['full_name'], output_dir, audio_format, normalize)
                    else:
                        print("No tracks could be extracted from the Beatport URL.")
                except Exception as exc:
                    print(f"Error parsing Beatport URL: {exc}")
            else:
                print("Unsupported URL. Please enter a Spotify track or Beatport track/playlist URL.")
    else:
        print("Invalid choice")
        sys.exit(1)

if __name__ == "__main__":
    main()
