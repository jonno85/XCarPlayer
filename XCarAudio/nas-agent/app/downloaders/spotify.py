"""
Spotify downloader.

The iOS app fetches a short-lived access token on-device (device IPs are not
blocked by Spotify) and passes it in the job payload. The agent uses it
directly to query the Spotify API for track metadata, then downloads each
track from YouTube via yt-dlp.
"""

import json
import logging
import urllib.request
from pathlib import Path

from app.downloaders.base import safe_name, ydl_download, ydl_opts_for_search

log = logging.getLogger("nas-agent.spotify")

_TRACKS_URL = (
    "https://api.spotify.com/v1/playlists/{id}/tracks"
    "?fields=items(track(name,artists)),next&limit=100"
)


def _playlist_tracks(playlist_id: str, token: str) -> list[dict]:
    tracks = []
    url: str | None = _TRACKS_URL.format(id=playlist_id)

    while url:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        for item in data.get("items", []):
            track = item.get("track")
            if track:
                tracks.append({
                    "title": track["name"],
                    "artist": ", ".join(a["name"] for a in track["artists"]),
                })
        url = data.get("next")

    return tracks


def _playlist_id(url: str) -> str:
    if "spotify.com/playlist/" in url:
        return url.split("spotify.com/playlist/")[1].split("?")[0].split("/")[0]
    if url.startswith("spotify:playlist:"):
        return url.split(":")[2]
    raise ValueError(f"Cannot extract playlist ID from URL: {url}")


def download(job: dict, playlist_dir: Path) -> None:
    token = job.get("spotify_token")
    if not token:
        raise RuntimeError("spotify_token is required — set sp_dc in the app Settings and retry")

    pid = _playlist_id(job["playlist_url"])
    log.info("[%s] Fetching tracks for playlist %s", job["id"], pid)

    tracks = _playlist_tracks(pid, token)
    job["tracks_total"] = len(tracks)
    log.info("[%s] %d tracks found", job["id"], len(tracks))

    for track in tracks:
        title, artist = track["title"], track["artist"]
        job["current_track"] = f"{artist} - {title}"

        output_path = playlist_dir / f"{safe_name(artist)} - {safe_name(title)}.%(ext)s"
        try:
            ydl_download(f"{artist} {title} audio", ydl_opts_for_search(output_path))
            job["tracks_done"] += 1
            log.info("[%s] Done: %s - %s", job["id"], artist, title)
        except Exception as exc:
            job["tracks_failed"] += 1
            job["failed_tracks"].append({"title": title, "error": str(exc)})
            log.warning("[%s] Failed: %s — %s", job["id"], title, exc)

    job["current_track"] = None
