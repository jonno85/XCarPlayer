import logging
from pathlib import Path

from app.downloaders.base import safe_name, ydl_download, ydl_extract_info, ydl_opts_for_search

log = logging.getLogger("nas-agent.beatport")


def download(job: dict, playlist_dir: Path) -> None:
    """Extract track list from a Beatport URL, then download each via YouTube search."""
    info = ydl_extract_info(job["playlist_url"], flat=True)
    entries = info.get("entries") or [info]
    job["tracks_total"] = len(entries)
    log.info("[%s] %d tracks found", job["id"], len(entries))

    for entry in entries:
        title = entry.get("title") or "Unknown"
        artist = entry.get("artist") or entry.get("uploader") or ""
        job["current_track"] = f"{artist} - {title}" if artist else title

        output_path = playlist_dir / f"{safe_name(artist)} - {safe_name(title)}.%(ext)s"
        query = f"{artist} {title} audio" if artist else f"{title} audio"

        try:
            ydl_download(query, ydl_opts_for_search(output_path))
            job["tracks_done"] += 1
            log.info("[%s] Done: %s - %s", job["id"], artist, title)
        except Exception as exc:
            job["tracks_failed"] += 1
            job["failed_tracks"].append({"title": title, "error": str(exc)})
            log.warning("[%s] Failed: %s — %s", job["id"], title, exc)

    job["current_track"] = None
