"""Shared download, configuration, and update logic for Music Library Downloader.

Service URLs are used for metadata or user-provided YouTube downloads only. This
module does not access Spotify or Beatport audio streams.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen


APP_NAME = "Music Library Downloader"
APP_VERSION = "1.0.0"
DEFAULT_GITHUB_REPOSITORY = "jonno85/XCarPlayer"
DEFAULT_LIBRARY_DIRECTORY = Path.home() / "Music" / "Music Library"
SUPPORTED_SOURCES = {"youtube", "spotify", "beatport", "text"}


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


def spotify_tracks(url: str, client_id: str, client_secret: str) -> List[Track]:
    """Read metadata from a public Spotify track or playlist using app credentials."""
    if not client_id.strip() or not client_secret.strip():
        raise InputError(
            "Spotify needs a Client ID and Client Secret. Create a free app at "
            "developer.spotify.com/dashboard, then paste both values above."
        )
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ImportError as error:
        raise InputError("Spotify support is still installing. Restart the app and try again.") from error

    item_type, item_id = parse_spotify_url(url)
    try:
        client = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=client_id.strip(),
                client_secret=client_secret.strip(),
            )
        )
        if item_type == "track":
            track = client.track(item_id)
            return [_spotify_track_to_track(track)]

        results = client.playlist_items(
            item_id,
            fields="items(track(name,artists(name),is_local)),next",
            additional_types=("track",),
        )
        tracks: List[Track] = []
        while results:
            for item in results.get("items", []):
                track = item.get("track") or {}
                if track.get("is_local"):
                    continue
                if track.get("name") and track.get("artists"):
                    tracks.append(_spotify_track_to_track(track))
            results = client.next(results) if results.get("next") else None
    except Exception as error:
        raise InputError(
            "Spotify could not read this link. Confirm that it is public and that your "
            "Client ID and Secret are valid."
        ) from error

    if not tracks:
        raise InputError("Spotify did not return any downloadable track metadata.")
    return _unique_tracks(tracks)


def _spotify_track_to_track(track: Dict[str, Any]) -> Track:
    artists = ", ".join(
        artist.get("name", "").strip() for artist in track.get("artists", []) if artist.get("name")
    )
    return Track(title=track.get("name", "").strip(), artist=artists)


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


class DownloadManager:
    """Runs yt-dlp jobs in background threads and exposes safe status snapshots."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        source = str(payload.get("source", "")).lower()
        if source not in SUPPORTED_SOURCES:
            raise InputError("Choose YouTube, Spotify, Beatport, or a text list.")
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
            "output_dir": str(output_directory),
            "log": [],
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

    def snapshot(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise InputError("That download session no longer exists.")
            return dict(self._jobs[job_id], log=list(self._jobs[job_id]["log"]))

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
            for index, track in enumerate(tracks, start=1):
                self._update(job_id, current=track.label, message=f"Downloading {index} of {len(tracks)}")
                self._log(job_id, f"[{index}/{len(tracks)}] {track.label}")
                try:
                    self._download_track(job_id, track, output_directory, payload)
                    with self._lock:
                        self._jobs[job_id]["completed"] += 1
                except Exception as error:  # Keep processing a list after a failed match.
                    with self._lock:
                        self._jobs[job_id]["failed"] += 1
                    self._log(job_id, f"Could not download {track.label}: {error}")
            result = self.snapshot(job_id)
            if result["completed"]:
                self._update(
                    job_id,
                    state="complete",
                    current="",
                    message=(
                        f"Finished: {result['completed']} saved"
                        + (f", {result['failed']} skipped." if result["failed"] else ".")
                    ),
                )
            else:
                self._update(
                    job_id,
                    state="failed",
                    current="",
                    message="No tracks were downloaded. See details below.",
                )
        except InputError as error:
            self._update(job_id, state="failed", message=str(error), current="")
            self._log(job_id, str(error))
        except Exception as error:
            self._update(job_id, state="failed", message="The download stopped unexpectedly.", current="")
            self._log(job_id, f"Unexpected error: {error}")

    def _tracks_for_payload(self, payload: Dict[str, Any]) -> List[Track]:
        source = str(payload.get("source", "")).lower()
        if source == "text":
            return parse_text_tracks(str(payload.get("tracks", "")))
        url = str(payload.get("url", ""))
        if source == "youtube":
            validate_source_url("youtube", url)
            if str(payload.get("download_type", "single")) == "playlist":
                return self._youtube_playlist_tracks(url)
            return [Track(title="YouTube item", direct_url=url)]
        if source == "spotify":
            return spotify_tracks(
                url,
                str(payload.get("spotify_client_id", "")),
                str(payload.get("spotify_client_secret", "")),
            )
        return beatport_tracks(url)

    def _youtube_playlist_tracks(self, url: str) -> List[Track]:
        """Expand a playlist once so the UI can report useful item progress."""
        try:
            import yt_dlp
        except ImportError as error:
            raise InputError("Download support is still installing. Restart the app and try again.") from error

        options = {"extract_flat": "in_playlist", "quiet": True, "no_warnings": True}
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

    def _download_track(
        self,
        job_id: str,
        track: Track,
        output_directory: Path,
        payload: Dict[str, Any],
    ) -> None:
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
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                },
                {"key": "FFmpegMetadata", "add_metadata": True},
            ],
            "progress_hooks": [self._progress_hook(job_id, track.label)],
        }
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
