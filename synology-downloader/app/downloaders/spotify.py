"""
Spotify downloader.

The iOS app fetches a short-lived access token on-device (device IPs are not
blocked by Spotify) and passes it in the job payload. The agent uses it
directly to query the Spotify API for track metadata, then downloads each
track from YouTube via yt-dlp.
"""

import json
import logging
import re
import urllib.error
import urllib.request
from base64 import b64encode
from pathlib import Path
from urllib.parse import urlencode

from app.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from app.downloaders.base import safe_name, ydl_download, ydl_opts_for_search

log = logging.getLogger("nas-agent.spotify")

_TRACKS_URL = (
    "https://api.spotify.com/v1/playlists/{id}/tracks"
    "?fields=items(track(name,artists)),next&limit=100"
)
_ACCESS_TOKEN_URL = "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"
_CLIENT_TOKEN_URL = "https://accounts.spotify.com/api/token"
_SCRAPE_URLS = [
    "https://open.spotify.com/embed/playlist/{id}",
    "https://open.spotify.com/playlist/{id}",
]
_SCRAPE_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_STATE_FILENAME = ".spotify_playlist_state.json"


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
                    "id": track.get("id"),
                    "title": track["name"],
                    "artist": ", ".join(a["name"] for a in track["artists"]),
                })
        url = data.get("next")

    return tracks


def _extract_sp_dc(credential: str) -> str | None:
    match = re.search(r"(?:^|[;\s])sp_dc=([^;\s]+)", credential)
    if match:
        return match.group(1)
    if credential.startswith("sp_dc="):
        return credential.split("=", 1)[1].strip()
    return None


def _token_from_sp_dc(sp_dc: str) -> str:
    req = urllib.request.Request(
        _ACCESS_TOKEN_URL,
        headers={
            "Cookie": f"sp_dc={sp_dc}",
            "App-Platform": "WebPlayer",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    token = data.get("accessToken")
    if not token or data.get("isAnonymous", True):
        raise RuntimeError("Spotify rejected the provided sp_dc cookie")
    return token


def _token_from_credential(credential: str) -> str:
    value = credential.strip()
    if not value:
        raise RuntimeError("Spotify credential is empty")

    sp_dc = _extract_sp_dc(value)
    if sp_dc:
        return _token_from_sp_dc(sp_dc)

    if value.lower().startswith("bearer "):
        return value.split(" ", 1)[1].strip()
    return value


def _token_from_client_credentials() -> str | None:
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        log.warning("SPOTIFY_CLIENT_ID/SPOTIFY_CLIENT_SECRET not set — skipping client credentials")
        return None

    basic = b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode("utf-8")).decode("ascii")
    body = urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    req = urllib.request.Request(
        _CLIENT_TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        token = data.get("access_token")
        if token:
            log.info("Obtained Spotify client credentials token (expires_in=%s)", data.get("expires_in"))
        else:
            log.warning("Spotify token endpoint returned no access_token: %s", data)
        return token
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        log.warning("Spotify client credentials HTTP %d: %s", exc.code, body_text)
        return None
    except Exception as exc:
        log.warning("Failed to obtain Spotify app token from client credentials: %s", exc)
        return None


def _playlist_tracks_via_scrape(playlist_id: str) -> list[dict]:
    """Fetch track list by scraping the public Spotify page — no credentials needed."""
    for url_template in _SCRAPE_URLS:
        url = url_template.format(id=playlist_id)
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _SCRAPE_UA, "Accept-Language": "en-US,en;q=0.9"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            log.debug("Scrape fetch failed for %s: %s", url, exc)
            continue

        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
            html, re.DOTALL,
        )
        if not match:
            continue

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

        tracks = _dig_tracks_from_next_data(data)
        if tracks:
            log.info("Scraped %d tracks from %s", len(tracks), url)
            return tracks

    raise RuntimeError(
        "Could not scrape track list from Spotify. "
        "The playlist may be private or Spotify changed their page structure."
    )


def _dig_tracks_from_next_data(data: dict) -> list[dict]:
    # Shape 1: embed page — entity.trackList[].{title, subtitle}
    try:
        track_list = data["props"]["pageProps"]["state"]["data"]["entity"]["trackList"]
        return [
            {"title": t["title"], "artist": t.get("subtitle", ""), "id": t.get("uid")}
            for t in track_list
            if t.get("title")
        ]
    except (KeyError, TypeError):
        pass

    # Shape 2: web player — componentProps.tracks.items[].track
    try:
        items = data["props"]["pageProps"]["componentProps"]["tracks"]["items"]
        return [
            {
                "title": i["track"]["name"],
                "artist": ", ".join(a["name"] for a in i["track"]["artists"]),
                "id": i["track"].get("id"),
            }
            for i in items
            if i.get("track")
        ]
    except (KeyError, TypeError):
        pass

    return []


def _playlist_id(url: str) -> str:
    if "spotify.com/playlist/" in url:
        return url.split("spotify.com/playlist/")[1].split("?")[0].split("/")[0]
    if url.startswith("spotify:playlist:"):
        return url.split(":")[2]
    raise ValueError(f"Cannot extract playlist ID from URL: {url}")


def _track_key(track: dict) -> str:
    tid = track.get("id")
    if tid:
        return f"id:{tid}"
    return f"text:{track.get('artist', '').strip().lower()}::{track.get('title', '').strip().lower()}"


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, playlist_id: str, tracks: list[dict]) -> None:
    snapshot = {
        "playlist_id": playlist_id,
        "track_keys": [_track_key(t) for t in tracks],
        "tracks": tracks,
    }
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def download(job: dict, playlist_dir: Path) -> None:
    token: str | None = None
    token_source: str | None = None

    if job.get("spotify_token"):
        token = job["spotify_token"]
        token_source = "user_token"
    elif job.get("spotify_credential"):
        try:
            token = _token_from_credential(job["spotify_credential"])
            token_source = "manual_credential"
        except Exception as exc:
            log.warning("[%s] Credential exchange failed (%s) — will try scrape", job["id"], exc)

    if not token:
        token = _token_from_client_credentials()
        if token:
            token_source = "client_credentials"

    pid = _playlist_id(job["playlist_url"])
    log.info("[%s] Fetching tracks for playlist %s (%s)", job["id"], pid, token_source or "scrape")

    tracks: list[dict] | None = None

    if token:
        try:
            tracks = _playlist_tracks(pid, token)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            log.warning("[%s] Spotify API HTTP %d (%s): %s", job["id"], exc.code, token_source, body_text)
            if token_source in ("user_token", "manual_credential") and exc.code == 401:
                raise RuntimeError(
                    "Spotify token is invalid or expired. Refresh login or update the manual credential."
                ) from exc
            if exc.code not in (401, 403, 404):
                raise
            log.info("[%s] API access denied (HTTP %d) — falling back to page scrape", job["id"], exc.code)

    if tracks is None:
        tracks = _playlist_tracks_via_scrape(pid)

    state_path = playlist_dir / _STATE_FILENAME
    previous_state = _load_state(state_path)
    previous_keys = set(previous_state.get("track_keys", [])) if previous_state.get("playlist_id") == pid else set()
    current_keys = [_track_key(track) for track in tracks]
    current_key_set = set(current_keys)

    added_keys = current_key_set - previous_keys
    removed_keys = previous_keys - current_key_set
    unchanged_count = len(current_key_set & previous_keys)

    job["spotify_changes"] = {
        "had_previous_snapshot": bool(previous_keys),
        "added_count": len(added_keys),
        "removed_count": len(removed_keys),
        "unchanged_count": unchanged_count,
    }

    tracks_to_download = tracks if not previous_keys else [t for t in tracks if _track_key(t) in added_keys]
    job["tracks_total"] = len(tracks_to_download)
    log.info(
        "[%s] tracks=%d to_download=%d added=%d removed=%d unchanged=%d",
        job["id"],
        len(tracks),
        len(tracks_to_download),
        len(added_keys),
        len(removed_keys),
        unchanged_count,
    )

    for track in tracks_to_download:
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

    _save_state(state_path, pid, tracks)
    job["current_track"] = None
