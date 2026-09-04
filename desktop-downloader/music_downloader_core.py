"""Shared download, configuration, and update logic for Music Library Downloader.

Service URLs are used for metadata or user-provided YouTube downloads only. This
module does not access Spotify or Beatport audio streams.
"""

from __future__ import annotations

import hashlib
import csv
import io
import json
import os
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen


APP_NAME = "Music Library Downloader"
APP_VERSION = "1.3.0"
DEFAULT_GITHUB_REPOSITORY = "jonno85/XCarPlayer"
DEFAULT_LIBRARY_DIRECTORY = Path.home() / "Music" / "Music Library"
SUPPORTED_SOURCES = {"youtube", "spotify", "beatport", "text"}
SUPPORTED_COOKIE_BROWSERS = {"", "brave", "chrome", "chromium", "edge", "firefox", "opera", "safari", "vivaldi"}
SUPPORTED_AUDIO_FORMATS = {"mp3", "m4a", "flac", "wav", "opus"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".flac", ".wav", ".opus", ".ogg", ".aac"}


class InputError(ValueError):
    """A validation error that can be displayed directly in the local UI."""


def application_data_directory() -> Path:
    """Return the conventional per-user configuration directory for this OS."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif os.sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "music-library-downloader"


class ConfigStore:
    """Persists non-sensitive preferences outside the repository checkout."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.path = config_path or application_data_directory() / "settings.json"

    def defaults(self) -> Dict[str, str]:
        return {
            "download_dir": str(DEFAULT_LIBRARY_DIRECTORY),
            "github_repository": DEFAULT_GITHUB_REPOSITORY,
            "language": "en",
            "audio_format": "mp3",
        }

    def load(self) -> Dict[str, str]:
        settings = self.defaults()
        try:
            with self.path.open("r", encoding="utf-8") as config_file:
                saved = json.load(config_file)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return settings

        if not isinstance(saved, dict):
            return settings
        for key in settings:
            value = saved.get(key)
            if isinstance(value, str) and value.strip():
                settings[key] = value.strip()
        return settings

    def save(self, values: Dict[str, Any]) -> Dict[str, str]:
        output_directory = str(values.get("download_dir", "")).strip()
        repository = str(values.get("github_repository", "")).strip()
        if not output_directory:
            raise InputError("Choose a default music folder first.")
        if not repository:
            raise InputError("Enter the GitHub repository used for update checks.")

        normalized = {
            "download_dir": str(Path(output_directory).expanduser()),
            "github_repository": repository,
            "language": "it" if values.get("language") == "it" else "en",
            "audio_format": (
                str(values.get("audio_format"))
                if values.get("audio_format") in SUPPORTED_AUDIO_FORMATS
                else "mp3"
            ),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as config_file:
            json.dump(normalized, config_file, indent=2)
        temporary_path.replace(self.path)
        return normalized


@dataclass(frozen=True)
class Track:
    """A normalized request for one downloadable audio item."""

    title: str
    artist: str = ""
    direct_url: str = ""

    @property
    def label(self) -> str:
        if self.artist:
            return f"{self.artist} — {self.title}"
        return self.title or "YouTube item"

    @property
    def search_query(self) -> str:
        return f"{self.label} official audio"


def parse_text_tracks(text: str) -> List[Track]:
    """Parse a one-song-per-line text list, ignoring comments and duplicates."""
    tracks: List[Track] = []
    seen = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        if " - " in line:
            artist, title = (part.strip() for part in line.split(" - ", 1))
            tracks.append(Track(title=title or line, artist=artist))
        else:
            tracks.append(Track(title=line))
    if not tracks:
        raise InputError("Add at least one song. Use one song per line.")
    return tracks


def parse_import_tracks(text: str, filename: str = "") -> List[Track]:
    """Parse exporter TXT or CSV content into normalized tracks."""
    if filename.lower().endswith(".csv") or _looks_like_csv(text):
        tracks = _parse_csv_tracks(text)
        if tracks:
            return _unique_tracks(tracks)
    return parse_text_tracks(text)


def _looks_like_csv(text: str) -> bool:
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    normalized = first_line.casefold()
    return ("," in first_line or ";" in first_line) and any(
        word in normalized for word in ("artist", "title", "track", "song")
    )


def _parse_csv_tracks(text: str) -> List[Track]:
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        rows = list(csv.reader(io.StringIO(text), dialect))
    except (csv.Error, UnicodeError):
        return []
    if not rows:
        return []

    def header_key(value: str) -> str:
        return re.sub(r"[^a-z]", "", value.casefold())

    headers = [header_key(value) for value in rows[0]]
    artist_names = {"artist", "artists", "artistname", "artistnames"}
    title_names = {"title", "track", "trackname", "song", "songtitle", "name"}
    artist_index = next((i for i, value in enumerate(headers) if value in artist_names), None)
    title_index = next((i for i, value in enumerate(headers) if value in title_names), None)
    if artist_index is None or title_index is None:
        return []
    tracks = []
    for row in rows[1:]:
        if max(artist_index, title_index) >= len(row):
            continue
        artist, title = row[artist_index].strip(), row[title_index].strip()
        if title:
            tracks.append(Track(title=title, artist=artist))
    return tracks


def parse_spotify_url(url: str) -> Tuple[str, str]:
    """Return the Spotify item type and ID for a public track or playlist URL."""
    value = url.strip()
    uri_match = re.fullmatch(r"spotify:(track|playlist):([A-Za-z0-9]+)", value)
    if uri_match:
        return uri_match.group(1), uri_match.group(2)

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "open.spotify.com":
        raise InputError("Paste a Spotify track or playlist link from open.spotify.com.")
    path_match = re.fullmatch(r"/(?:intl-[a-z]{2}/)?(track|playlist)/([A-Za-z0-9]+)", parsed.path)
    if not path_match:
        raise InputError("Use a Spotify track or playlist link, not an artist or album link.")
    return path_match.group(1), path_match.group(2)


def validate_source_url(source: str, url: str) -> str:
    """Ensure the chosen provider matches a supported public URL."""
    value = url.strip()
    if not value:
        raise InputError("Paste a link first.")
    if source == "spotify":
        parse_spotify_url(value)
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower().split(":")[0]
    accepted_hosts = {
        "youtube": {"youtube.com", "www.youtube.com", "music.youtube.com", "youtu.be"},
        "beatport": {"beatport.com", "www.beatport.com"},
    }
    if parsed.scheme not in {"http", "https"} or host not in accepted_hosts.get(source, set()):
        source_name = {"youtube": "YouTube", "beatport": "Beatport"}.get(source, source)
        raise InputError(f"Paste a valid {source_name} link.")
    return value


def spotify_tracks(url: str) -> List[Track]:
    """Read metadata from a public Spotify embed page without API credentials."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as error:
        raise InputError("Spotify support is still installing. Restart the app and try again.") from error

    item_type, item_id = parse_spotify_url(url)
    page_urls = [
        f"https://open.spotify.com/embed/{item_type}/{item_id}",
        f"https://open.spotify.com/{item_type}/{item_id}",
    ]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    last_error: Optional[Exception] = None
    for page_url in page_urls:
        try:
            response = requests.get(page_url, headers=headers, timeout=20)
            response.raise_for_status()
            next_data = BeautifulSoup(response.text, "html.parser").find(
                "script", id="__NEXT_DATA__"
            )
            if not next_data or not next_data.string:
                continue
            tracks = _spotify_tracks_from_embed_data(json.loads(next_data.string), item_type)
            if tracks:
                return _unique_tracks(tracks)
        except (requests.RequestException, json.JSONDecodeError) as error:
            last_error = error
            continue
    raise InputError(
        "Spotify could not read this public link. Make sure the playlist is public, "
        "or import an exporter TXT/CSV file below."
    ) from last_error


def _spotify_tracks_from_embed_data(data: Dict[str, Any], item_type: str) -> List[Track]:
    """Handle the current Spotify embed payload and its previous playlist shape."""
    try:
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]
    except (KeyError, TypeError):
        entity = {}
    if item_type == "track" and isinstance(entity, dict):
        title = str(entity.get("title") or entity.get("name") or "").strip()
        artists = entity.get("artists") or []
        artist = ", ".join(
            str(value.get("name", "")).strip()
            for value in artists
            if isinstance(value, dict) and value.get("name")
        )
        if title:
            return [Track(title=title, artist=artist)]

    track_list = entity.get("trackList", []) if isinstance(entity, dict) else []
    tracks = [
        Track(title=str(item.get("title", "")).strip(), artist=str(item.get("subtitle", "")).strip())
        for item in track_list
        if isinstance(item, dict) and item.get("title")
    ]
    if tracks:
        return tracks

    try:
        items = data["props"]["pageProps"]["componentProps"]["tracks"]["items"]
    except (KeyError, TypeError):
        return []
    return [
        Track(
            title=str(item["track"]["name"]).strip(),
            artist=", ".join(
                str(artist.get("name", "")).strip()
                for artist in item["track"].get("artists", [])
                if artist.get("name")
            ),
        )
        for item in items
        if isinstance(item, dict) and item.get("track", {}).get("name")
    ]


def beatport_tracks(url: str) -> List[Track]:
    """Read track metadata from a public Beatport page without reading audio."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as error:
        raise InputError("Beatport support is still installing. Restart the app and try again.") from error

    validate_source_url("beatport", url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as error:
        raise InputError("Beatport could not open this link. Check the link and try again.") from error

    soup = BeautifulSoup(response.text, "html.parser")
    tracks: List[Track] = []
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and next_data.string:
        try:
            tracks.extend(_beatport_tracks_from_data(json.loads(next_data.string)))
        except json.JSONDecodeError:
            pass

    for structured_data in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if structured_data.string:
            try:
                tracks.extend(_beatport_tracks_from_structured_data(json.loads(structured_data.string)))
            except json.JSONDecodeError:
                pass

    tracks = _unique_tracks(tracks)
    if not tracks:
        raise InputError(
            "No tracks were found on this Beatport page. The page may be private or "
            "Beatport may have changed its public page format."
        )
    return tracks


def _beatport_tracks_from_data(data: Any) -> List[Track]:
    tracks: List[Track] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            title = str(node.get("name", "")).strip()
            artists = node.get("artists")
            if title and isinstance(artists, list) and artists:
                names = []
                for artist in artists:
                    if isinstance(artist, dict) and artist.get("name"):
                        names.append(str(artist["name"]).strip())
                    elif isinstance(artist, str) and artist.strip():
                        names.append(artist.strip())
                if names:
                    tracks.append(Track(title=title, artist=", ".join(names)))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return tracks


def _beatport_tracks_from_structured_data(data: Any) -> List[Track]:
    nodes = data if isinstance(data, list) else [data]
    tracks: List[Track] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("@type")
        if node_type not in {"MusicRecording", "MusicPlaylist", "ItemList"}:
            continue
        items = node.get("track") or node.get("itemListElement") or [node]
        if not isinstance(items, list):
            items = [items]
        for item in items:
            item = item.get("item", item) if isinstance(item, dict) else {}
            if not isinstance(item, dict):
                continue
            title = str(item.get("name", "")).strip()
            artist = item.get("byArtist") or item.get("artist") or ""
            if isinstance(artist, dict):
                artist = artist.get("name", "")
            elif isinstance(artist, list):
                artist = ", ".join(
                    entry.get("name", "") if isinstance(entry, dict) else str(entry) for entry in artist
                )
            if title and str(artist).strip():
                tracks.append(Track(title=title, artist=str(artist).strip()))
    return tracks


def _unique_tracks(tracks: List[Track]) -> List[Track]:
    unique: List[Track] = []
    seen = set()
    for track in tracks:
        if not track.title:
            continue
        key = (track.artist.casefold(), track.title.casefold(), track.direct_url.casefold())
        if key not in seen:
            seen.add(key)
            unique.append(track)
    return unique


def safe_filename(value: str, fallback: str = "audio") -> str:
    """Create a cross-platform filename stem from service metadata."""
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")
    return (normalized[:160].rstrip(" .") or fallback)


def ffmpeg_path() -> str:
    """Locate the per-platform ffmpeg binary installed by imageio-ffmpeg."""
    try:
        import imageio_ffmpeg
    except ImportError as error:
        raise InputError("Audio conversion support is still installing. Restart the app and try again.") from error
    return imageio_ffmpeg.get_ffmpeg_exe()


def normalized_track_key(value: str) -> str:
    """Normalize a title or filename for conservative duplicate detection."""
    value = Path(value).stem
    value = re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", value, flags=re.UNICODE))
    return value.casefold().strip()


class LibraryHistory:
    """Persistent, non-destructive index of downloads and existing library files."""

    def __init__(self, history_path: Optional[Path] = None) -> None:
        self.path = history_path or application_data_directory() / "history.json"
        self._lock = threading.Lock()

    def entries(self) -> List[Dict[str, Any]]:
        with self._lock:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                return []
        if not isinstance(raw, list):
            return []
        entries = []
        for item in raw:
            if not isinstance(item, dict) or not item.get("path"):
                continue
            path = Path(str(item["path"]))
            entry = dict(item)
            entry["available"] = path.is_file()
            entries.append(entry)
        return sorted(entries, key=lambda item: str(item.get("downloaded_at", "")), reverse=True)

    def record(
        self,
        path: Path,
        track: Track,
        source: str,
        audio_format: str,
        playlist_id: str,
        source_url: str = "",
    ) -> Dict[str, Any]:
        resolved = path.expanduser().resolve()
        entry = {
            "id": uuid.uuid4().hex,
            "title": track.title or resolved.stem,
            "artist": track.artist,
            "label": track.label if track.title != "YouTube item" else resolved.stem,
            "path": str(resolved),
            "format": audio_format,
            "source": source,
            "source_url": source_url,
            "playlist_id": playlist_id,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "available": True,
        }
        with self._lock:
            existing = self._read_unlocked()
            existing = [item for item in existing if str(item.get("path")) != str(resolved)]
            existing.insert(0, entry)
            self._write_unlocked(existing[:2000])
        return entry

    def scan(self, directory: Path) -> Dict[str, Any]:
        root = directory.expanduser().resolve()
        if not root.is_dir():
            raise InputError("The selected music folder does not exist yet.")
        files = [
            path for path in root.rglob("*")
            if path.is_file() and path.suffix.casefold() in AUDIO_EXTENSIONS
        ]
        indexed_paths = {str(Path(item["path"]).resolve()) for item in self.entries()}
        return {
            "directory": str(root),
            "total": len(files),
            "tracked": sum(str(path.resolve()) in indexed_paths for path in files),
            "untracked": sum(str(path.resolve()) not in indexed_paths for path in files),
            "files": [
                {
                    "name": path.name,
                    "path": str(path.resolve()),
                    "format": path.suffix.lstrip(".").lower(),
                    "tracked": str(path.resolve()) in indexed_paths,
                }
                for path in sorted(files, key=lambda item: item.name.casefold())[:500]
            ],
        }

    def find_existing(self, directory: Path, track: Track) -> Optional[Path]:
        if not directory.is_dir() or track.title == "YouTube item":
            return None
        desired = normalized_track_key(
            f"{track.artist} {track.title}" if track.artist else track.title
        )
        for path in directory.iterdir():
            if path.is_file() and path.suffix.casefold() in AUDIO_EXTENSIONS:
                candidate = normalized_track_key(path.name)
                if candidate == desired:
                    return path
        return None

    def resolve_media(self, entry_id: str) -> Path:
        for entry in self.entries():
            if entry.get("id") == entry_id:
                path = Path(str(entry["path"])).resolve()
                if path.is_file() and path.suffix.casefold() in AUDIO_EXTENSIONS:
                    return path
                raise InputError("That audio file is no longer available.")
        raise InputError("That history item was not found.")

    def _read_unlocked(self) -> List[Dict[str, Any]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []

    def _write_unlocked(self, entries: List[Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


class DownloadManager:
    """Runs yt-dlp jobs in background threads and exposes safe status snapshots."""

    def __init__(self, history: Optional[LibraryHistory] = None) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.history = history or LibraryHistory()

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        source = str(payload.get("source", "")).lower()
        if source not in SUPPORTED_SOURCES:
            raise InputError("Choose YouTube, Spotify, Beatport, or a text list.")
        audio_format = str(payload.get("audio_format", "mp3")).lower()
        if audio_format not in SUPPORTED_AUDIO_FORMATS:
            raise InputError("Choose MP3, M4A, FLAC, WAV, or Opus.")
        if not payload.get("rights_confirmed"):
            raise InputError("Confirm that you have the rights or permission to download these tracks.")

        output_value = str(payload.get("output_dir", "")).strip()
        if not output_value:
            raise InputError("Choose a music folder first.")
        output_directory = Path(output_value).expanduser()
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "source": source,
            "state": "preparing",
            "message": "Preparing your download…",
            "current": "",
            "total": 0,
            "completed": 0,
            "failed": 0,
            "existing": 0,
            "output_dir": str(output_directory),
            "audio_format": audio_format,
            "log": [],
            "items": [],
            "playlist_path": "",
            "needs_browser_cookies": False,
        }
        with self._lock:
            self._jobs[job_id] = job
        thread = threading.Thread(
            target=self._run,
            args=(job_id, payload, output_directory),
            name=f"music-download-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
        return self.snapshot(job_id)

    def preview(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve editable metadata and compare it to the destination library."""
        tracks = self._tracks_for_payload(payload, allow_prepared=False)
        output_value = str(payload.get("output_dir", "")).strip()
        output_directory = Path(output_value).expanduser() if output_value else None
        return {
            "source": str(payload.get("source", "")).lower(),
            "source_url": str(payload.get("url", "")).strip(),
            "total": len(tracks),
            "tracks": [
                {
                    "artist": track.artist,
                    "title": track.title,
                    "existing": bool(
                        output_directory
                        and self.history.find_existing(output_directory, track)
                    ),
                    "included": True,
                }
                for track in tracks
            ],
        }

    def snapshot(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise InputError("That download session no longer exists.")
            return dict(
                self._jobs[job_id],
                log=list(self._jobs[job_id]["log"]),
                items=[dict(item) for item in self._jobs[job_id]["items"]],
            )

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(changes)

    def _log(self, job_id: str, message: str) -> None:
        with self._lock:
            log = self._jobs[job_id]["log"]
            log.append(message)
            del log[:-80]

    def _run(self, job_id: str, payload: Dict[str, Any], output_directory: Path) -> None:
        try:
            output_directory.mkdir(parents=True, exist_ok=True)
            tracks = self._tracks_for_payload(payload)
            self._update(
                job_id,
                state="downloading",
                total=len(tracks),
                message=f"Downloading {len(tracks)} track{'s' if len(tracks) != 1 else ''}…",
            )
            self._log(job_id, f"Saving to {output_directory}")
            saved_paths: List[Path] = []
            for index, track in enumerate(tracks, start=1):
                self._update(job_id, current=track.label, message=f"Downloading {index} of {len(tracks)}")
                self._log(job_id, f"[{index}/{len(tracks)}] {track.label}")
                existing_path = self.history.find_existing(output_directory, track)
                if existing_path:
                    history_entry = self.history.record(
                        existing_path,
                        track,
                        "existing",
                        existing_path.suffix.lstrip("."),
                        job_id,
                        str(payload.get("url", "")),
                    )
                    with self._lock:
                        self._jobs[job_id]["existing"] += 1
                        self._jobs[job_id]["items"].append({
                            "label": track.label,
                            "status": "existing",
                            "media_id": history_entry["id"],
                        })
                    saved_paths.append(existing_path)
                    self._log(job_id, f"Already in library: {existing_path.name}")
                    continue
                try:
                    saved_path = self._download_track(job_id, track, output_directory, payload)
                    history_entry = self.history.record(
                        saved_path,
                        track,
                        str(payload.get("source")),
                        str(payload.get("audio_format", "mp3")),
                        job_id,
                        str(payload.get("url", "")),
                    )
                    with self._lock:
                        self._jobs[job_id]["completed"] += 1
                        self._jobs[job_id]["items"].append({
                            "label": track.label,
                            "status": "downloaded",
                            "media_id": history_entry["id"],
                        })
                    saved_paths.append(saved_path)
                except Exception as error:  # Keep processing a list after a failed match.
                    with self._lock:
                        self._jobs[job_id]["failed"] += 1
                        self._jobs[job_id]["items"].append({
                            "label": track.label,
                            "status": "failed",
                            "media_id": "",
                        })
                        if "sign in to confirm you're not a bot" in str(error).lower():
                            self._jobs[job_id]["needs_browser_cookies"] = True
                    self._log(job_id, f"Could not download {track.label}: {error}")
            if payload.get("rekordbox_playlist") and saved_paths:
                playlist_path = self._write_m3u8(
                    output_directory,
                    str(payload.get("playlist_name", "")).strip(),
                    saved_paths,
                )
                self._update(job_id, playlist_path=str(playlist_path))
                self._log(job_id, f"Rekordbox playlist: {playlist_path.name}")
            result = self.snapshot(job_id)
            if result["completed"] or result["existing"]:
                self._update(
                    job_id,
                    state="complete",
                    current="",
                    message=(
                        f"Finished: {result['completed']} saved"
                        + (f", {result['existing']} already in library" if result["existing"] else "")
                        + (f", {result['failed']} skipped." if result["failed"] else ".")
                    ),
                )
            else:
                if result["needs_browser_cookies"]:
                    message = (
                        "YouTube asked you to sign in. Under the YouTube link, choose the "
                        "browser where you are signed in, then try again."
                    )
                else:
                    message = "No tracks were downloaded. See details below."
                self._update(
                    job_id,
                    state="failed",
                    current="",
                    message=message,
                )
        except InputError as error:
            self._update(job_id, state="failed", message=str(error), current="")
            self._log(job_id, str(error))
        except Exception as error:
            self._update(job_id, state="failed", message="The download stopped unexpectedly.", current="")
            self._log(job_id, f"Unexpected error: {error}")

    def _tracks_for_payload(
        self, payload: Dict[str, Any], allow_prepared: bool = True
    ) -> List[Track]:
        if allow_prepared and isinstance(payload.get("prepared_tracks"), list):
            tracks = []
            for item in payload["prepared_tracks"][:5000]:
                if not isinstance(item, dict) or item.get("included") is False:
                    continue
                title = str(item.get("title", "")).strip()
                artist = str(item.get("artist", "")).strip()
                if title:
                    tracks.append(Track(title=title, artist=artist))
            if not tracks:
                raise InputError("Select at least one track from the preview.")
            return _unique_tracks(tracks)
        source = str(payload.get("source", "")).lower()
        if source == "text":
            return parse_import_tracks(
                str(payload.get("tracks", "")),
                str(payload.get("filename", "")),
            )
        url = str(payload.get("url", ""))
        if source == "youtube":
            validate_source_url("youtube", url)
            browser = self._youtube_cookie_browser(payload)
            if str(payload.get("download_type", "single")) == "playlist":
                return self._youtube_playlist_tracks(url, browser)
            return [self._youtube_single_track(url, browser)]
        if source == "spotify":
            return spotify_tracks(url)
        return beatport_tracks(url)

    def _youtube_cookie_browser(self, payload: Dict[str, Any]) -> str:
        browser = str(payload.get("youtube_browser", "")).strip().lower()
        if browser not in SUPPORTED_COOKIE_BROWSERS:
            raise InputError("Choose a supported browser for YouTube sign-in, or leave it set to none.")
        return browser

    def _youtube_playlist_tracks(self, url: str, browser: str) -> List[Track]:
        """Expand a playlist once so the UI can report useful item progress."""
        try:
            import yt_dlp
        except ImportError as error:
            raise InputError("Download support is still installing. Restart the app and try again.") from error

        options = {"extract_flat": "in_playlist", "quiet": True, "no_warnings": True}
        if browser:
            options["cookiesfrombrowser"] = (browser,)
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                playlist = downloader.extract_info(url, download=False)
        except Exception as error:
            raise InputError("YouTube could not read this playlist. Check the link and try again.") from error

        tracks = []
        for entry in playlist.get("entries") or []:
            if not entry:
                continue
            entry_url = entry.get("webpage_url") or entry.get("url")
            if entry.get("ie_key") == "Youtube" and entry_url and not str(entry_url).startswith("http"):
                entry_url = f"https://www.youtube.com/watch?v={entry_url}"
            if entry_url:
                tracks.append(Track(title=str(entry.get("title") or "YouTube item"), direct_url=str(entry_url)))
        if not tracks:
            raise InputError("YouTube did not return any playable items from this playlist.")
        return tracks

    def _youtube_single_track(self, url: str, browser: str) -> Track:
        try:
            import yt_dlp
        except ImportError as error:
            raise InputError("Download support is still installing. Restart the app and try again.") from error
        options: Dict[str, Any] = {"quiet": True, "no_warnings": True, "noplaylist": True}
        if browser:
            options["cookiesfrombrowser"] = (browser,)
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=False)
        except Exception as error:
            raise InputError("YouTube could not read this item. Check the link or sign-in option.") from error
        return Track(
            title=str(info.get("track") or info.get("title") or "YouTube item"),
            artist=str(info.get("artist") or info.get("uploader") or ""),
            direct_url=url,
        )

    def _download_track(
        self,
        job_id: str,
        track: Track,
        output_directory: Path,
        payload: Dict[str, Any],
    ) -> Path:
        try:
            import yt_dlp
        except ImportError as error:
            raise InputError("Download support is still installing. Restart the app and try again.") from error

        if track.artist:
            filename = safe_filename(f"{track.artist} - {track.title}")
        elif track.direct_url:
            filename = "%(title)s"
        else:
            filename = safe_filename(track.title)
        is_youtube_playlist = (
            bool(track.direct_url)
            and str(payload.get("download_type", "single")) == "playlist"
            and track.title == "YouTube item"
        )
        audio_format = str(payload.get("audio_format", "mp3")).lower()
        postprocessor: Dict[str, Any] = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
        }
        if audio_format == "mp3":
            postprocessor["preferredquality"] = "320"
        options = {
            "format": "bestaudio/best",
            "outtmpl": str(output_directory / f"{filename}.%(ext)s"),
            "ffmpeg_location": ffmpeg_path(),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "windowsfilenames": True,
            "overwrites": False,
            "noplaylist": not is_youtube_playlist,
            "postprocessors": [
                postprocessor,
                {"key": "FFmpegMetadata", "add_metadata": True},
            ],
            "progress_hooks": [self._progress_hook(job_id, track.label)],
        }
        browser = self._youtube_cookie_browser(payload)
        if browser:
            options["cookiesfrombrowser"] = (browser,)
        if track.artist:
            options["postprocessor_args"] = {
                "FFmpegMetadata": [
                    "-metadata",
                    f"title={track.title}",
                    "-metadata",
                    f"artist={track.artist}",
                ]
            }
        source = track.direct_url or f"ytsearch1:{track.search_query}"
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([source])
        expected_path = output_directory / f"{filename}.{audio_format}"
        if expected_path.is_file():
            return expected_path
        candidates = sorted(
            (
                path for path in output_directory.iterdir()
                if path.is_file() and path.suffix.casefold() == f".{audio_format}"
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise InputError("The converter finished but the output file could not be found.")
        return candidates[0]

    def _write_m3u8(self, directory: Path, name: str, paths: List[Path]) -> Path:
        playlist_name = safe_filename(name or f"Rekordbox {datetime.now():%Y-%m-%d %H%M}")
        playlist_path = directory / f"{playlist_name}.m3u8"
        lines = ["#EXTM3U"]
        for path in paths:
            try:
                lines.append(path.resolve().relative_to(directory.resolve()).as_posix())
            except ValueError:
                lines.append(str(path.resolve()))
        playlist_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
        return playlist_path

    def _progress_hook(self, job_id: str, label: str) -> Callable[[Dict[str, Any]], None]:
        def update_progress(status: Dict[str, Any]) -> None:
            if status.get("status") != "downloading":
                return
            downloaded = status.get("downloaded_bytes") or 0
            total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
            if total:
                percentage = min(99, int((downloaded / total) * 100))
                self._update(job_id, current=f"{label} · {percentage}%")

        return update_progress


def get_update_status(
    project_root: Path, github_repository: str = DEFAULT_GITHUB_REPOSITORY
) -> Dict[str, Any]:
    """Compare this checkout to its tracked remote without modifying it."""
    if not (project_root / ".git").exists():
        return _github_release_status(github_repository)
    try:
        branch = _git(project_root, "branch", "--show-current")
        if not branch:
            return {"supported": False, "message": "Updates need a normal Git branch checkout."}
        dirty = bool(_git(project_root, "status", "--porcelain"))
        _git(project_root, "fetch", "origin", branch)
        local = _git(project_root, "rev-parse", "HEAD")
        remote = _git(project_root, "rev-parse", f"origin/{branch}")
        if local == remote:
            message = "Your copy is up to date."
        elif dirty:
            message = "An update is available, but local changes must be committed or moved first."
        else:
            message = "An update is ready to install."
        return {
            "supported": True,
            "available": local != remote,
            "can_install": local != remote and not dirty,
            "message": message,
        }
    except (OSError, subprocess.CalledProcessError):
        return {"supported": False, "message": "Could not reach the GitHub update source right now."}


def install_update(
    project_root: Path, github_repository: str = DEFAULT_GITHUB_REPOSITORY
) -> Dict[str, Any]:
    """Fast-forward a clean Git checkout to its current remote branch."""
    status = get_update_status(project_root, github_repository)
    if not status.get("supported"):
        return status
    if not status.get("available"):
        return status
    if not status.get("can_install"):
        return status
    try:
        branch = _git(project_root, "branch", "--show-current")
        _git(project_root, "pull", "--ff-only", "origin", branch)
        return {
            "supported": True,
            "updated": True,
            "message": "Update installed. Close this window and launch the app again.",
        }
    except (OSError, subprocess.CalledProcessError):
        return {"supported": False, "message": "The update could not be installed. Your files were left unchanged."}


def _git(project_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def _github_release_status(github_repository: str) -> Dict[str, Any]:
    """Check the latest public GitHub release for packaged, no-install copies."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", github_repository):
        return {"supported": False, "message": "The configured GitHub repository is not valid."}
    url = f"https://api.github.com/repos/{github_repository}/releases/latest"
    try:
        request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": APP_NAME})
        with urlopen(request, timeout=10) as response:  # nosec B310 - fixed GitHub API URL
            release = json.load(response)
    except OSError:
        return {
            "supported": False,
            "message": "Could not check GitHub releases right now. Your app is unchanged.",
        }

    tag = str(release.get("tag_name", "")).lstrip("v")
    release_url = str(release.get("html_url", ""))
    if tag == APP_VERSION:
        return {"supported": False, "available": False, "message": "Your packaged app is up to date."}
    if tag:
        return {
            "supported": False,
            "available": True,
            "message": f"Version {tag} is available. Download it from the GitHub Releases page to update.",
            "release_url": release_url,
        }
    return {
        "supported": False,
        "message": "Updates are published on GitHub Releases. Download the latest release to update this copy.",
    }


def requirements_hash(requirements_path: Path) -> str:
    """Expose a stable requirements checksum for the bootstrapper and tests."""
    return hashlib.sha256(requirements_path.read_bytes()).hexdigest()
