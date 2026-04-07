import os
from pathlib import Path

API_KEY: str = os.getenv("API_KEY", "")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable is not set")

SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")

MUSIC_DIR: Path = Path(os.getenv("MUSIC_DIR", "/music"))

# spotDL lives in its own venv to avoid the fastapi<0.104 conflict
SPOTDL_BIN: str = os.getenv("SPOTDL_BIN", "/opt/spotdl-venv/bin/spotdl")
