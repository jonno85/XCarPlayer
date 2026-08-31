import logging
from pathlib import Path

import yt_dlp

from app.downloaders.base import YDL_AUDIO_POSTPROCESSORS

log = logging.getLogger("nas-agent.youtube")


def download(job: dict, playlist_dir: Path) -> None:
    """Download a YouTube playlist directly via yt-dlp."""
    url = job["playlist_url"]

    # Pre-fetch track count without downloading
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    job["tracks_total"] = len(info.get("entries") or [info])
    log.info("[%s] %d tracks found", job["id"], job["tracks_total"])

    def _on_progress(d: dict) -> None:
        if d["status"] == "finished":
            job["tracks_done"] += 1
        title = d.get("filename") or d.get("info_dict", {}).get("title")
        if title:
            job["current_track"] = Path(title).stem

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(playlist_dir / "%(uploader)s - %(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": YDL_AUDIO_POSTPROCESSORS,
        "progress_hooks": [_on_progress],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    job["current_track"] = None
