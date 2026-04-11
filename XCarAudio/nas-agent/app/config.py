import os
from pathlib import Path

API_KEY: str = os.getenv("API_KEY", "")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable is not set")

MUSIC_DIR: Path = Path(os.getenv("MUSIC_DIR", "/music"))

# Optional Spotify app credentials (Client Credentials flow) for public playlist metadata.
SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
