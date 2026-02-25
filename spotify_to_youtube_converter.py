#!/usr/bin/env python3
"""
Spotify Playlist to YouTube Converter
Extracts songs from a Spotify playlist and converts them to a format for YouTube download.

Requirements:
    pip install spotipy

Setup:
    1. Go to https://developer.spotify.com/dashboard
    2. Create an app (any name)
    3. Get your Client ID and Client Secret
    4. System will ask you to authenticate once
"""

import subprocess
import sys
import os
import json

def check_spotipy_installed():
    """Check if spotipy is installed"""
    try:
        import spotipy
        return True
    except ImportError:
        return False

def install_spotipy():
    """Install spotipy package"""
    print("Installing spotipy...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'spotipy'])
        print("✓ spotipy installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("✗ Failed to install spotipy")
        return False

def get_spotify_credentials():
    """Get Spotify API credentials from user"""
    creds_file = 'spotify_credentials.json'
    
    if os.path.exists(creds_file):
        try:
            with open(creds_file, 'r') as f:
                creds = json.load(f)
                if creds.get('client_id') and creds.get('client_secret'):
                    return creds['client_id'], creds['client_secret']
        except Exception:
            pass

    print("\n" + "="*60)
    print("Get your Spotify API credentials:")
    print("="*60)
    print("1. Go to: https://developer.spotify.com/dashboard")
    print("2. Login/Create account (free)")
    print("3. Click 'Create an App'")
    print("4. Accept terms and create")
    print("5. You'll see Client ID and Client Secret")
    print("="*60)
    
    client_id = input("\nEnter your Spotify Client ID: ").strip()
    client_secret = input("Enter your Spotify Client Secret: ").strip()
    
    if not client_id or not client_secret:
        print("Error: Credentials are required")
        return None, None
        
    try:
        with open(creds_file, 'w') as f:
            json.dump({'client_id': client_id, 'client_secret': client_secret}, f, indent=4)
        print("✓ Credentials saved locally to spotify_credentials.json")
    except Exception as e:
        print(f"Warning: Could not save credentials: {e}")
    
    return client_id, client_secret

def extract_playlist_id(playlist_url):
    """Extract playlist ID from Spotify URL"""
    # Handle different URL formats:
    # https://open.spotify.com/playlist/PLAYLIST_ID
    # https://open.spotify.com/playlist/PLAYLIST_ID?si=...
    
    if 'playlist/' not in playlist_url:
        print("Error: Invalid Spotify playlist URL")
        return None
    
    try:
        # Extract ID between 'playlist/' and '?'
        parts = playlist_url.split('playlist/')[1].split('?')[0]
        return parts
    except:
        print("Error: Could not parse playlist URL")
        return None

def get_playlist_songs(client_id, client_secret, playlist_url):
    """
    Get all songs from a Spotify playlist
    
    Args:
        client_id (str): Spotify API Client ID
        client_secret (str): Spotify API Client Secret
        playlist_url (str): Spotify playlist URL
    
    Returns:
        list: List of dicts with 'artist' and 'title' keys
    """
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        print("Error: spotipy not installed")
        return None
    
    # Extract playlist ID
    playlist_id = extract_playlist_id(playlist_url)
    if not playlist_id:
        return None
    
    try:
        # Authenticate with Spotify
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri="http://127.0.0.1:8888/callback",
            scope="playlist-read-private user-read-private"
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        
        # Obtener el mercado (país) del usuario para playlists algorítmicas de Spotify
        # Las playlists como Daily Mix y Discover Weekly requieren el parámetro market para no retornar 404
        try:
            user_info = sp.current_user()
            market = user_info.get('country', 'IT')
        except Exception:
            market = 'US'

        # Get playlist tracks
        print(f"\nFetching playlist songs...")
        results = sp.playlist_tracks(playlist_id, market=market)
        
        songs = []
        while results:
            for item in results['items']:
                track = item['track']
                if track and track['artists']:
                    artist = track['artists'][0]['name']
                    title = track['name']
                    songs.append({
                        'artist': artist,
                        'title': title,
                        'full_name': f"{artist} - {title}"
                    })
            
            # Get next page if available
            if results['next']:
                results = sp.next(results)
            else:
                break
        
        return songs
    
    except Exception as e:
        print(f"Error fetching playlist: {e}")
        print("\nTroubleshooting:")
        print("  • Check your Client ID and Client Secret")
        print("  • Make sure the playlist URL is correct")
        print("  • The playlist should be public or owned by your account")
        return None

def save_song_list(songs, output_file='songs.txt'):
    """
    Save song list to a text file
    
    Args:
        songs (list): List of song dicts
        output_file (str): Output filename
    """
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
    """Show preview of songs"""
    print(f"\nPlaylist Preview ({min(limit, len(songs))} of {len(songs)} songs):")
    print("-" * 60)
    for i, song in enumerate(songs[:limit], 1):
        print(f"{i:2d}. {song['full_name']}")
    if len(songs) > limit:
        print(f"... and {len(songs) - limit} more")
    print("-" * 60)

def main():
    print("=" * 60)
    print("Spotify Playlist to YouTube Converter")
    print("=" * 60)
    
    # Check if spotipy is installed
    if not check_spotipy_installed():
        print("\nspotipy is not installed.")
        install = input("Would you like to install it now? (y/n): ").lower()
        if install == 'y':
            if not install_spotipy():
                sys.exit(1)
        else:
            print("Please install spotipy manually: pip install spotipy")
            sys.exit(1)
    
    # Get Spotify credentials
    client_id, client_secret = get_spotify_credentials()
    if not client_id or not client_secret:
        sys.exit(1)
    
    # Get playlist URL from user
    playlist_url = input("\nEnter Spotify playlist URL: ").strip()
    if not playlist_url:
        print("Error: No URL provided")
        sys.exit(1)
    
    # Fetch playlist songs
    songs = get_playlist_songs(client_id, client_secret, playlist_url)
    if not songs:
        sys.exit(1)
    
    # Show preview
    show_preview(songs)
    
    # Ask for output filename
    output_file = input("\nEnter output filename (default: 'songs.txt'): ").strip()
    if not output_file:
        output_file = 'songs.txt'
    
    # Save to file
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
