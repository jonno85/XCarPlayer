import logging
import re
import subprocess
from pathlib import Path

from app.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTDL_BIN

log = logging.getLogger("nas-agent.spotify")

# spotDL progress line patterns
_RE_FOUND = re.compile(r"Found\s+(\d+)\s+song", re.IGNORECASE)
_RE_DONE = re.compile(r'Downloaded\s+"(.+?)"', re.IGNORECASE)
_RE_FAIL = re.compile(r'Failed to download\s+"(.+?)"[:\s]+(.*)', re.IGNORECASE)


def download(job: dict, playlist_dir: Path) -> None:
    """Download a Spotify playlist by calling the spotDL CLI in its isolated venv."""
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise RuntimeError(
            "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env"
        )

    cmd = [
        SPOTDL_BIN,
        job["playlist_url"],
        "--client-id", SPOTIFY_CLIENT_ID,
        "--client-secret", SPOTIFY_CLIENT_SECRET,
        "--output", "{artists} - {title}",
        "--format", "mp3",
        "--bitrate", "320k",
        "--print-errors",
    ]

    log.info("[%s] Running spotDL: %s", job["id"], job["playlist_url"])

    proc = subprocess.Popen(
        cmd,
        cwd=str(playlist_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        log.debug("[%s] spotdl: %s", job["id"], line)

        if m := _RE_FOUND.search(line):
            job["tracks_total"] = int(m.group(1))

        elif m := _RE_DONE.search(line):
            job["tracks_done"] += 1
            job["current_track"] = m.group(1)
            log.info("[%s] Done: %s", job["id"], m.group(1))

        elif m := _RE_FAIL.search(line):
            job["tracks_failed"] += 1
            job["failed_tracks"].append({"title": m.group(1), "error": m.group(2).strip()})
            log.warning("[%s] Failed: %s — %s", job["id"], m.group(1), m.group(2).strip())

    proc.wait()
    job["current_track"] = None

    if proc.returncode != 0 and job["tracks_done"] == 0:
        raise RuntimeError(f"spotDL exited with code {proc.returncode}")
