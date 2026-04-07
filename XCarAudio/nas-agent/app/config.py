import os
from pathlib import Path

API_KEY: str = os.getenv("API_KEY", "")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable is not set")

MUSIC_DIR: Path = Path(os.getenv("MUSIC_DIR", "/music"))
