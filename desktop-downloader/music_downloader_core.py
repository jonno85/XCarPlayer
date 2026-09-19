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
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen


from dj_styling import build_dj_card, camelot_from_key, prepare_dj_assets, preview_line

APP_NAME = "Music Library Downloader"
APP_VERSION = "1.7.0"
DEFAULT_GITHUB_REPOSITORY = "jonno85/XCarPlayer"
DEFAULT_LIBRARY_DIRECTORY = Path.home() / "Music" / "Music Library"
SUPPORTED_SOURCES = {"youtube", "spotify", "beatport", "text", "search"}
SUPPORTED_COOKIE_BROWSERS = {"", "brave", "chrome", "chromium", "edge", "firefox", "opera", "safari", "vivaldi"}
SUPPORTED_AUDIO_FORMATS = {"mp3", "m4a", "flac", "wav", "opus"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".flac", ".wav", ".opus", ".ogg", ".aac"}


class InputError(ValueError):
    """A validation error that can be displayed directly in the local UI."""


class DownloadStopped(Exception):
    """Raised when the user stops an in-progress download job."""


class DownloadPaused(Exception):
    """Raised to abort the current file so the job can wait until resume."""


ACTIVE_JOB_STATES = {"preparing", "downloading", "paused"}


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
    duration_ms: int = 0
    bpm: int = 0
    musical_key: str = ""
    camelot: str = ""
    genre: str = ""
    mix_name: str = ""
    analysis_source: str = ""
    released_at: str = ""

    @property
    def label(self) -> str:
        if self.artist:
            return f"{self.artist} — {self.title}"
        return self.title or "YouTube item"

    @property
    def search_query(self) -> str:
        if self.artist:
            return f"{self.artist} - {self.title}"
        return self.title


def _optional_int(value: Any) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _preview_track_payload(track: Track, existing: bool = False) -> Dict[str, Any]:
    card = build_dj_card(
        artist=track.artist,
        title=track.title,
        bpm=track.bpm,
        musical_key=track.musical_key,
        camelot=track.camelot,
        genre=track.genre,
        mix_name=track.mix_name,
        duration_ms=track.duration_ms,
        analysis_source=track.analysis_source,
    )
    return {
        "artist": track.artist,
        "title": track.title,
        "duration_ms": track.duration_ms,
        "bpm": track.bpm,
        "musical_key": track.musical_key,
        "camelot": track.camelot or card.get("camelot") or "",
        "genre": track.genre,
        "mix_name": track.mix_name,
        "analysis_source": track.analysis_source,
        "released_at": track.released_at,
        "dj_hint": preview_line(card),
        "stems_useful": list(card.get("stems", {}).get("useful") or []),
        "existing": existing,
        "included": True,
    }


def _track_from_prepared_item(item: Dict[str, Any]) -> Optional[Track]:
    title = str(item.get("title", "")).strip()
    if not title:
        return None
    return Track(
        title=title,
        artist=str(item.get("artist", "")).strip(),
        direct_url=str(item.get("direct_url") or item.get("url") or "").strip(),
        duration_ms=_optional_int(item.get("duration_ms")),
        bpm=_optional_int(item.get("bpm")),
        musical_key=str(item.get("musical_key") or item.get("key") or "").strip(),
        camelot=str(item.get("camelot") or "").strip(),
        genre=str(item.get("genre") or "").strip(),
        mix_name=str(item.get("mix_name") or "").strip(),
        analysis_source=str(item.get("analysis_source") or "").strip(),
        released_at=release_date_text(item),
    )


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
    date_names = {"releasedate", "released", "date", "year", "albumreleasedate", "publishdate"}
    artist_index = next((i for i, value in enumerate(headers) if value in artist_names), None)
    title_index = next((i for i, value in enumerate(headers) if value in title_names), None)
    date_index = next((i for i, value in enumerate(headers) if value in date_names), None)
    if artist_index is None or title_index is None:
        return []
    tracks = []
    for row in rows[1:]:
        if max(artist_index, title_index) >= len(row):
            continue
        artist, title = row[artist_index].strip(), row[title_index].strip()
        released_at = ""
        if date_index is not None and date_index < len(row):
            released_at = release_date_text(row[date_index])
        if title:
            tracks.append(Track(title=title, artist=artist, released_at=released_at))
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


def _spotify_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _spotify_artist_names(node: Dict[str, Any]) -> str:
    artists = node.get("artists") or []
    names = [
        _spotify_text(value.get("name"))
        for value in artists
        if isinstance(value, dict) and value.get("name")
    ]
    if names:
        return ", ".join(names)
    return _spotify_text(node.get("subtitle"))


def _spotify_duration_ms(node: Dict[str, Any]) -> int:
    for key in ("duration", "duration_ms", "durationMs"):
        value = node.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    return 0


def _spotify_tracks_from_embed_data(data: Dict[str, Any], item_type: str) -> List[Track]:
    """Handle the current Spotify embed payload and its previous playlist shape."""
    try:
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]
    except (KeyError, TypeError):
        entity = {}
    if item_type == "track" and isinstance(entity, dict):
        title = _spotify_text(entity.get("title") or entity.get("name"))
        artist = _spotify_artist_names(entity)
        if title:
            return [Track(
                title=title,
                artist=artist,
                duration_ms=_spotify_duration_ms(entity),
                released_at=release_date_text(entity),
            )]

    track_list = entity.get("trackList", []) if isinstance(entity, dict) else []
    tracks = [
        Track(
            title=_spotify_text(item.get("title")),
            artist=_spotify_artist_names(item),
            duration_ms=_spotify_duration_ms(item),
            released_at=release_date_text(item),
        )
        for item in track_list
        if isinstance(item, dict) and _spotify_text(item.get("title"))
    ]
    if tracks:
        return tracks

    try:
        items = data["props"]["pageProps"]["componentProps"]["tracks"]["items"]
    except (KeyError, TypeError):
        return []
    parsed = []
    for item in items:
        if not isinstance(item, dict):
            continue
        track = item.get("track") or item
        if not isinstance(track, dict):
            continue
        title = _spotify_text(track.get("name") or track.get("title"))
        if not title:
            continue
        parsed.append(
            Track(
                title=title,
                artist=_spotify_artist_names(track),
                duration_ms=_spotify_duration_ms(track),
                released_at=release_date_text(track) or release_date_text(item),
            )
        )
    return parsed


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
    """Collect catalog tracks from Beatport page JSON, ignoring related albums."""
    queries = _beatport_dehydrated_queries(data)
    tracks: List[Track] = []
    if queries:
        for query in queries:
            if _is_beatport_recommendation_query(query.get("queryKey")):
                continue
            tracks.extend(_collect_beatport_tracks(query.get("state", {}).get("data")))
        if tracks:
            return tracks
    return _collect_beatport_tracks(data, skip_recommendations=True)


def _beatport_dehydrated_queries(data: Any) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    queries = (
        data.get("props", {})
        .get("pageProps", {})
        .get("dehydratedState", {})
        .get("queries")
    )
    if not isinstance(queries, list):
        return []
    return [query for query in queries if isinstance(query, dict)]


def _is_beatport_recommendation_query(query_key: Any) -> bool:
    try:
        text = json.dumps(query_key).casefold()
    except (TypeError, ValueError):
        text = str(query_key or "").casefold()
    return "recommend" in text


def _collect_beatport_tracks(node: Any, skip_recommendations: bool = False) -> List[Track]:
    tracks: List[Track] = []

    def walk(value: Any, path: str = "") -> None:
        if skip_recommendations and "recommend" in path.casefold():
            return
        track = _beatport_track_from_node(value)
        if track is not None:
            tracks.append(track)
            return
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for child in value:
                walk(child, path)

    walk(node)
    return tracks


def _beatport_artist_names(node: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    seen = set()
    for key in ("artists", "remixers"):
        artists = node.get(key)
        if not isinstance(artists, list):
            continue
        for artist in artists:
            if isinstance(artist, dict):
                name = str(artist.get("name") or artist.get("artist_name") or "").strip()
            elif isinstance(artist, str):
                name = artist.strip()
            else:
                continue
            folded = name.casefold()
            if name and folded not in seen:
                seen.add(folded)
                names.append(name)
    return names


def _beatport_duration_ms(node: Dict[str, Any]) -> int:
    for key in ("track_length_ms", "length_ms"):
        value = node.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    length = node.get("length")
    if isinstance(length, (int, float)) and length > 1000:
        return int(length)
    if isinstance(length, str) and ":" in length:
        try:
            parts = [int(part) for part in length.split(":")]
        except ValueError:
            return 0
        if len(parts) == 2:
            return (parts[0] * 60 + parts[1]) * 1000
        if len(parts) == 3:
            return (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000
    return 0


def _beatport_track_from_node(node: Any) -> Optional[Track]:
    if not isinstance(node, dict):
        return None
    if "track_count" in node and "mix_name" not in node:
        return None
    artists = _beatport_artist_names(node)
    title = str(node.get("track_name") or node.get("name") or "").strip()
    if not title or not artists:
        return None
    has_mix = "mix_name" in node
    has_duration = any(key in node for key in ("length", "length_ms", "track_length_ms"))
    if not has_mix and not has_duration:
        return None
    mix = str(node.get("mix_name") or "").strip()
    if _should_append_beatport_mix(title, mix):
        title = f"{title} ({mix})"
    musical_key, camelot = _beatport_key_fields(node)
    return Track(
        title=title,
        artist=", ".join(artists),
        duration_ms=_beatport_duration_ms(node),
        bpm=_beatport_bpm(node),
        musical_key=musical_key,
        camelot=camelot,
        genre=_beatport_genre(node),
        mix_name=mix,
        analysis_source="beatport",
        released_at=release_date_text(node),
    )


def _beatport_bpm(node: Dict[str, Any]) -> int:
    value = node.get("bpm")
    try:
        bpm = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return bpm if 50 <= bpm <= 220 else 0


def _beatport_genre(node: Dict[str, Any]) -> str:
    for key in ("genre", "genres", "sub_genre", "subgenre"):
        value = node.get(key)
        if isinstance(value, dict):
            name = str(value.get("name") or "").strip()
            if name:
                return name
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("name"):
                    return str(item["name"]).strip()
                if isinstance(item, str) and item.strip():
                    return item.strip()
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _beatport_key_fields(node: Dict[str, Any]) -> Tuple[str, str]:
    raw = node.get("key") or node.get("key_name") or ""
    if isinstance(raw, dict):
        name = str(raw.get("name") or raw.get("standard") or raw.get("short_name") or "").strip()
    else:
        name = str(raw or "").strip()
    camelot = camelot_from_key(raw) or camelot_from_key(name)
    return name, camelot


def _should_append_beatport_mix(title: str, mix: str) -> bool:
    if not mix or mix.casefold() in title.casefold():
        return False
    generic_mix = mix.casefold() in {"original mix", "original"}
    title_already_versioned = re.search(r"\b(mix|remix|edit|rework)\b", title, re.I)
    return not (generic_mix and title_already_versioned)


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
                tracks.append(Track(
                    title=title,
                    artist=str(artist).strip(),
                    released_at=release_date_text(item) or release_date_text(node),
                ))
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


YOUTUBE_SEARCH_RESULTS = 5
_YOUTUBE_LONG_SET_HINTS = (
    "dj set",
    "full set",
    "live at",
    "live from",
    "hour mix",
    "hours mix",
    "1 hour",
    "continuous mix",
    "megamix",
    "compilation",
    "karaoke",
)


def _normalized_search_tokens(value: str) -> set:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def choose_youtube_result(track: Track, entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pick the YouTube search hit that best matches the requested mix and length."""
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        scored.append((_youtube_match_score(track, entry), entry))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _youtube_match_score(track: Track, entry: Dict[str, Any]) -> float:
    video_title = str(entry.get("title") or "")
    query_tokens = _normalized_search_tokens(track.search_query)
    title_tokens = _normalized_search_tokens(video_title)
    score = (len(query_tokens & title_tokens) / len(query_tokens)) if query_tokens else 0.0
    title_cf = video_title.casefold()
    if any(hint in title_cf for hint in _YOUTUBE_LONG_SET_HINTS):
        score -= 0.6
    duration = entry.get("duration") or 0
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        duration = 0
    expected = track.duration_ms / 1000 if track.duration_ms else 0
    if expected and duration:
        delta = abs(duration - expected)
        if delta <= 15:
            score += 0.5
        elif delta <= 45:
            score += 0.25
        elif duration > expected * 2.5 or (expected < 600 and duration > 900):
            score -= 0.8
    elif duration > 900:
        score -= 0.4
    return score


def _youtube_result_url(entry: Dict[str, Any]) -> str:
    url = str(entry.get("webpage_url") or entry.get("url") or "").strip()
    if entry.get("ie_key") == "Youtube" and url and not url.startswith("http"):
        return f"https://www.youtube.com/watch?v={url}"
    return url


YOUTUBE_MANUAL_SEARCH_RESULTS = 8


def _format_clock_duration(seconds: float) -> str:
    total = int(seconds)
    if total <= 0:
        return ""
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def youtube_search_hits(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize yt-dlp search entries into picker rows for the local UI."""
    hits: List[Dict[str, Any]] = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = _youtube_result_url(entry)
        if not url or url in seen:
            continue
        seen.add(url)
        duration = entry.get("duration") or 0
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            duration = 0
        title = str(entry.get("title") or "YouTube item").strip()
        hits.append({
            "title": title,
            "channel": str(entry.get("uploader") or entry.get("channel") or "").strip(),
            "duration": int(duration) if duration else 0,
            "duration_ms": int(duration * 1000) if duration else 0,
            "duration_label": _format_clock_duration(duration),
            "url": url,
            "released_at": release_date_text(entry),
        })
    return hits


def search_youtube(query: str, browser: str = "") -> List[Dict[str, Any]]:
    """Search YouTube for a free-text artist/title query without downloading."""
    value = " ".join(str(query or "").split()).strip()
    if not value:
        raise InputError("Enter a song title or artist to search.")
    try:
        import yt_dlp
    except ImportError as error:
        raise InputError("Download support is still installing. Restart the app and try again.") from error
    options: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "noplaylist": True,
    }
    if browser:
        options["cookiesfrombrowser"] = (browser,)
    try:
        with yt_dlp.YoutubeDL(options) as searcher:
            info = searcher.extract_info(
                f"ytsearch{YOUTUBE_MANUAL_SEARCH_RESULTS}:{value}",
                download=False,
            )
    except Exception as error:
        raise InputError("YouTube could not search for this song. Check the query or sign-in option.") from error
    entries = [
        entry for entry in (info.get("entries") or [] if isinstance(info, dict) else [])
        if isinstance(entry, dict)
    ]
    hits = youtube_search_hits(entries)
    if not hits:
        raise InputError("YouTube did not return any videos for this search.")
    return hits


def safe_filename(value: str, fallback: str = "audio") -> str:
    """Create a cross-platform filename stem from service metadata."""
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")
    return (normalized[:160].rstrip(" .") or fallback)


def output_filename_stem(track: Track, payload: Dict[str, Any]) -> str:
    """Name search downloads from the YouTube video, not the typed query."""
    if str(payload.get("source", "")).lower() == "search" and track.direct_url:
        return "%(title)s"
    if track.artist:
        return safe_filename(f"{track.artist} - {track.title}")
    if track.direct_url:
        return "%(title)s"
    return safe_filename(track.title)


def year_month_save_directory(
    root: Path,
    enabled: bool,
    when: Optional[datetime] = None,
) -> Path:
    """Return the music folder, or root/YYYY/MM for the given date."""
    if not enabled:
        return root
    stamp = when or datetime.now()
    return root / f"{stamp:%Y}" / f"{stamp:%m}"


_PROVIDER_DATE_KEYS = (
    "publish_date",
    "new_release_date",
    "release_date",
    "releaseDate",
    "released_at",
    "releasedAt",
    "date_published",
    "datePublished",
    "upload_date",
    "uploadDate",
    "release_year",
    "year",
    "timestamp",
    "date",
)


def parse_provider_datetime(value: Any) -> Optional[datetime]:
    """Parse a provider release or upload date into year/month (and day when known)."""
    if value in (None, False, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, dict):
        for key in _PROVIDER_DATE_KEYS + ("isoString", "iso"):
            parsed = parse_provider_datetime(value.get(key))
            if parsed:
                return parsed
        year = _optional_int(value.get("year"))
        if 1900 <= year <= 2100:
            month = _optional_int(value.get("month"))
            return datetime(year, month if 1 <= month <= 12 else 1, 1)
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        if number >= 1_000_000_000_000:
            number = number // 1000
        if number >= 1_000_000_000:
            try:
                return datetime.fromtimestamp(number)
            except (OSError, OverflowError, ValueError):
                return None
        text = str(number)
    else:
        text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d")
        except ValueError:
            return None
    match = re.match(r"^(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?", text)
    if match and (match.group(2) or re.fullmatch(r"\d{4}", text)):
        year = int(match.group(1))
        month = int(match.group(2) or 1)
        day = int(match.group(3) or 1)
        if 1900 <= year <= 2100 and 1 <= month <= 12:
            try:
                return datetime(year, month, day)
            except ValueError:
                return datetime(year, month, 1)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00")[:19])
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None


def provider_datetime_from_node(node: Any) -> Optional[datetime]:
    """Read a release/upload date from a Spotify, Beatport, or YouTube metadata object."""
    if not isinstance(node, dict):
        return parse_provider_datetime(node)
    for key in _PROVIDER_DATE_KEYS:
        parsed = parse_provider_datetime(node.get(key))
        if parsed:
            return parsed
    for nested_key in ("album", "release", "track"):
        nested = node.get(nested_key)
        if isinstance(nested, dict):
            parsed = provider_datetime_from_node(nested)
            if parsed:
                return parsed
    return None


def release_date_text(value: Any) -> str:
    """Normalize provider metadata to YYYY-MM-DD, or empty when unknown."""
    parsed = provider_datetime_from_node(value)
    return parsed.strftime("%Y-%m-%d") if parsed else ""


def crate_datetime(track: Track, fallback: Optional[datetime] = None) -> datetime:
    """Prefer the provider release date; otherwise use the current (or given) date."""
    parsed = parse_provider_datetime(track.released_at)
    if parsed:
        return parsed
    return fallback or datetime.now()


def playlist_crate_directory(
    root: Path,
    enabled: bool,
    saved_paths: List[Path],
    fallback: datetime,
) -> Path:
    """Keep the playlist with the tracks when they share a month; otherwise use today."""
    if not enabled:
        return root
    by_folder: Dict[Path, Path] = {}
    for path in saved_paths:
        if not path:
            continue
        by_folder.setdefault(path.resolve().parent, path.parent)
    if len(by_folder) == 1:
        return next(iter(by_folder.values()))
    return year_month_save_directory(root, True, fallback)


def rekordbox_file_tags(track: Track, payload: Dict[str, Any]) -> Dict[str, str]:
    """Build file tags Rekordbox reads on import (Genre, Grouping, Comments).

    Rekordbox My Tags and colour labels live only in Rekordbox's database and
    cannot be written into audio files or .m3u8 playlists.
    """
    tags: Dict[str, str] = {}
    source = str(payload.get("source", "")).lower()
    if source != "search":
        if track.title and track.title != "YouTube item":
            tags["title"] = track.title
        if track.artist:
            tags["artist"] = track.artist
    if track.genre:
        tags["genre"] = track.genre
    playlist_name = str(payload.get("playlist_name") or "").strip()
    crate = str(payload.get("crate") or "").strip()
    grouping = playlist_name or crate
    if grouping:
        tags["grouping"] = grouping
    comment_parts: List[str] = []
    for part in (playlist_name, crate):
        if part and part not in comment_parts:
            comment_parts.append(part)
    if comment_parts:
        tags["comment"] = " | ".join(comment_parts)
    released = parse_provider_datetime(track.released_at)
    if released:
        tags["date"] = f"{released:%Y}"
    return tags


def ffmpeg_metadata_args(tags: Dict[str, str]) -> List[str]:
    """Turn tag names into ffmpeg -metadata arguments."""
    args: List[str] = []
    for key, value in tags.items():
        if value:
            args.extend(["-metadata", f"{key}={value}"])
    return args


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

    def audio_index(self, directory: Path) -> Dict[str, Path]:
        """Map normalized artist-title keys to audio files under a library root."""
        index: Dict[str, Path] = {}
        if not directory.is_dir():
            return index
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.casefold() in AUDIO_EXTENSIONS:
                index.setdefault(normalized_track_key(path.name), path)
        return index

    def find_existing(
        self,
        directory: Path,
        track: Track,
        index: Optional[Dict[str, Path]] = None,
    ) -> Optional[Path]:
        if track.title == "YouTube item":
            return None
        desired = normalized_track_key(
            f"{track.artist} {track.title}" if track.artist else track.title
        )
        lookup = index if index is not None else self.audio_index(directory)
        return lookup.get(desired)

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
        self._controls: Dict[str, Dict[str, threading.Event]] = {}
        self._lock = threading.Lock()
        self.history = history or LibraryHistory()

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        source = str(payload.get("source", "")).lower()
        if source not in SUPPORTED_SOURCES:
            raise InputError("Choose YouTube, Spotify, Beatport, Search, or a text list.")
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
            self._controls[job_id] = {
                "pause": threading.Event(),
                "stop": threading.Event(),
            }
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
        library_index = (
            self.history.audio_index(output_directory) if output_directory else {}
        )
        return {
            "source": str(payload.get("source", "")).lower(),
            "source_url": str(payload.get("url", "")).strip(),
            "total": len(tracks),
            "tracks": [
                _preview_track_payload(
                    track,
                    existing=bool(
                        output_directory
                        and self.history.find_existing(
                            output_directory, track, library_index
                        )
                    ),
                )
                for track in tracks
            ],
        }

    def search(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return YouTube hits for a typed artist/title query so the user can pick one."""
        artist = str(payload.get("artist", "")).strip()
        title = str(payload.get("title", "")).strip()
        query = f"{artist} - {title}" if artist and title else (artist or title)
        browser = self._youtube_cookie_browser(payload)
        return {"query": query, "results": search_youtube(query, browser)}

    def snapshot(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise InputError("That download session no longer exists.")
            return dict(
                self._jobs[job_id],
                log=list(self._jobs[job_id]["log"]),
                items=[dict(item) for item in self._jobs[job_id]["items"]],
            )

    def pause(self, job_id: str) -> Dict[str, Any]:
        """Hold the job after the current file check; remaining tracks wait until resume."""
        job = self.snapshot(job_id)
        if job["state"] not in ACTIVE_JOB_STATES:
            raise InputError("That download has already finished.")
        if self._is_stopped(job_id):
            raise InputError("That download is already stopping.")
        with self._lock:
            self._controls[job_id]["pause"].set()
            self._jobs[job_id].update(
                state="paused",
                message="Download paused. Resume to continue, or stop to cancel the rest.",
            )
        self._log(job_id, "Paused")
        return self.snapshot(job_id)

    def resume(self, job_id: str) -> Dict[str, Any]:
        job = self.snapshot(job_id)
        if job["state"] != "paused":
            raise InputError("That download is not paused.")
        if self._is_stopped(job_id):
            raise InputError("That download is already stopping.")
        with self._lock:
            self._controls[job_id]["pause"].clear()
            completed = self._jobs[job_id]["completed"]
            existing = self._jobs[job_id]["existing"]
            failed = self._jobs[job_id]["failed"]
            total = self._jobs[job_id]["total"]
            remaining = max(0, total - completed - existing - failed)
            self._jobs[job_id].update(
                state="downloading",
                message=(
                    f"Downloading {remaining} remaining track{'s' if remaining != 1 else ''}…"
                    if total
                    else "Downloading…"
                ),
            )
        self._log(job_id, "Resumed")
        return self.snapshot(job_id)

    def stop(self, job_id: str) -> Dict[str, Any]:
        """Cancel remaining tracks. Files already saved are kept."""
        job = self.snapshot(job_id)
        if job["state"] not in ACTIVE_JOB_STATES:
            raise InputError("That download has already finished.")
        with self._lock:
            self._controls[job_id]["stop"].set()
            self._controls[job_id]["pause"].clear()
            self._jobs[job_id].update(message="Stopping…")
        self._log(job_id, "Stop requested")
        return self.snapshot(job_id)

    def _is_stopped(self, job_id: str) -> bool:
        with self._lock:
            control = self._controls.get(job_id)
            return bool(control and control["stop"].is_set())

    def _is_paused(self, job_id: str) -> bool:
        with self._lock:
            control = self._controls.get(job_id)
            return bool(control and control["pause"].is_set())

    def _checkpoint(self, job_id: str, *, abort_current: bool = False) -> None:
        if self._is_stopped(job_id):
            raise DownloadStopped()
        if self._is_paused(job_id):
            if abort_current:
                raise DownloadPaused()
            while self._is_paused(job_id) and not self._is_stopped(job_id):
                time.sleep(0.05)
            if self._is_stopped(job_id):
                raise DownloadStopped()

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
            library_root = output_directory
            started_at = datetime.now()
            use_year_month = bool(payload.get("year_month_folders"))
            default_directory = year_month_save_directory(library_root, use_year_month, started_at)
            work_payload = dict(payload)
            tracks = self._tracks_for_payload(work_payload)
            self._checkpoint(job_id)
            self._update(
                job_id,
                state="paused" if self._is_paused(job_id) else "downloading",
                total=len(tracks),
                output_dir=str(default_directory),
                message=f"Downloading {len(tracks)} track{'s' if len(tracks) != 1 else ''}…",
            )
            if use_year_month:
                self._log(
                    job_id,
                    "Saving in year/month folders from the provider date, or today if unknown",
                )
            self._log(job_id, f"Saving to {default_directory}")
            saved_paths: List[Path] = []
            stem_paths: List[Path] = []
            stopped_early = False
            library_index = self.history.audio_index(library_root)
            for index, track in enumerate(tracks, start=1):
                try:
                    self._checkpoint(job_id)
                except DownloadStopped:
                    stopped_early = True
                    remaining = len(tracks) - index + 1
                    self._log(job_id, f"Stopped with {remaining} track{'s' if remaining != 1 else ''} remaining")
                    break
                stamp = crate_datetime(track, started_at)
                save_directory = year_month_save_directory(library_root, use_year_month, stamp)
                track_payload = dict(work_payload)
                if use_year_month:
                    track_payload["crate"] = f"{stamp:%Y-%m}"
                    save_directory.mkdir(parents=True, exist_ok=True)
                    if save_directory != default_directory:
                        self._log(job_id, f"Provider date {stamp:%Y-%m}: {save_directory}")
                else:
                    save_directory.mkdir(parents=True, exist_ok=True)
                self._update(job_id, current=track.label, message=f"Downloading {index} of {len(tracks)}")
                self._log(job_id, f"[{index}/{len(tracks)}] {track.label}")
                existing_path = self.history.find_existing(library_root, track, library_index)
                if existing_path:
                    history_entry = self.history.record(
                        existing_path,
                        track,
                        "existing",
                        existing_path.suffix.lstrip("."),
                        job_id,
                        str(work_payload.get("url", "")),
                    )
                    with self._lock:
                        self._jobs[job_id]["existing"] += 1
                        self._jobs[job_id]["items"].append({
                            "label": track.label,
                            "status": "existing",
                            "media_id": history_entry["id"],
                        })
                    saved_paths.append(existing_path)
                    stem_paths.extend(self._write_dj_assets(job_id, existing_path, track, track_payload))
                    self._log(job_id, f"Already in library: {existing_path.name}")
                    continue
                try:
                    saved_path = self._download_until_saved(job_id, track, save_directory, track_payload)
                    library_index.setdefault(normalized_track_key(saved_path.name), saved_path)
                    history_entry = self.history.record(
                        saved_path,
                        track,
                        str(work_payload.get("source")),
                        str(work_payload.get("audio_format", "mp3")),
                        job_id,
                        str(work_payload.get("url", "")),
                    )
                    with self._lock:
                        self._jobs[job_id]["completed"] += 1
                        self._jobs[job_id]["items"].append({
                            "label": track.label,
                            "status": "downloaded",
                            "media_id": history_entry["id"],
                        })
                    saved_paths.append(saved_path)
                    stem_paths.extend(self._write_dj_assets(job_id, saved_path, track, track_payload))
                except DownloadStopped:
                    stopped_early = True
                    remaining = len(tracks) - index + 1
                    self._log(job_id, f"Stopped with {remaining} track{'s' if remaining != 1 else ''} remaining")
                    break
                except Exception as error:  # Keep processing a list after a failed match.
                    if self._is_control_error(error, DownloadStopped):
                        stopped_early = True
                        remaining = len(tracks) - index + 1
                        self._log(job_id, f"Stopped with {remaining} track{'s' if remaining != 1 else ''} remaining")
                        break
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
            playlist_directory = playlist_crate_directory(
                library_root, use_year_month, saved_paths, started_at
            )
            if use_year_month and saved_paths:
                playlist_directory.mkdir(parents=True, exist_ok=True)
                self._update(job_id, output_dir=str(playlist_directory))
            if work_payload.get("rekordbox_playlist") and saved_paths:
                playlist_path = self._write_m3u8(
                    playlist_directory,
                    str(work_payload.get("playlist_name", "")).strip(),
                    saved_paths,
                )
                self._update(job_id, playlist_path=str(playlist_path), output_dir=str(playlist_directory))
                self._log(job_id, f"Rekordbox playlist: {playlist_path.name}")
            if work_payload.get("rekordbox_playlist") and stem_paths:
                stem_playlist = self._write_m3u8(
                    playlist_directory,
                    f"{str(work_payload.get('playlist_name', '')).strip() or 'Rekordbox'} Stems",
                    stem_paths,
                )
                self._log(job_id, f"Rekordbox stem playlist: {stem_playlist.name}")
            result = self.snapshot(job_id)
            remaining = max(
                0,
                result["total"] - result["completed"] - result["existing"] - result["failed"],
            )
            if stopped_early:
                self._update(
                    job_id,
                    state="stopped",
                    current="",
                    message=(
                        f"Stopped: {result['completed']} saved"
                        + (f", {result['existing']} already in library" if result["existing"] else "")
                        + (f", {remaining} cancelled." if remaining else ".")
                    ),
                )
            elif result["completed"] or result["existing"]:
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
        except DownloadStopped:
            result = self.snapshot(job_id)
            remaining = max(
                0,
                result["total"] - result["completed"] - result["existing"] - result["failed"],
            )
            self._update(
                job_id,
                state="stopped",
                current="",
                message=(
                    "Stopped before any tracks were saved."
                    if not result["completed"] and not result["existing"]
                    else f"Stopped: {result['completed']} saved"
                    + (f", {result['existing']} already in library" if result["existing"] else "")
                    + (f", {remaining} cancelled." if remaining else ".")
                ),
            )
            self._log(job_id, "Stopped")
        except InputError as error:
            self._update(job_id, state="failed", message=str(error), current="")
            self._log(job_id, str(error))
        except Exception as error:
            self._update(job_id, state="failed", message="The download stopped unexpectedly.", current="")
            self._log(job_id, f"Unexpected error: {error}")

    def _download_until_saved(
        self,
        job_id: str,
        track: Track,
        output_directory: Path,
        payload: Dict[str, Any],
    ) -> Path:
        while True:
            self._checkpoint(job_id)
            try:
                return self._download_track(job_id, track, output_directory, payload)
            except DownloadPaused:
                self._log(job_id, f"Paused during {track.label}; will retry this track after resume")
                continue
            except Exception as error:
                if self._is_control_error(error, DownloadPaused):
                    self._log(job_id, f"Paused during {track.label}; will retry this track after resume")
                    continue
                if self._is_control_error(error, DownloadStopped):
                    raise DownloadStopped() from error
                raise

    def _is_control_error(self, error: BaseException, control_type: type) -> bool:
        current: Optional[BaseException] = error
        seen: set = set()
        while current is not None and id(current) not in seen:
            if isinstance(current, control_type):
                return True
            seen.add(id(current))
            current = current.__cause__ or current.__context__
        return False

    def _tracks_for_payload(
        self, payload: Dict[str, Any], allow_prepared: bool = True
    ) -> List[Track]:
        if allow_prepared and isinstance(payload.get("prepared_tracks"), list):
            tracks = []
            for item in payload["prepared_tracks"][:5000]:
                if not isinstance(item, dict) or item.get("included") is False:
                    continue
                track = _track_from_prepared_item(item)
                if track is not None:
                    tracks.append(track)
            if not tracks:
                raise InputError("Select at least one track from the preview.")
            return _unique_tracks(tracks)
        source = str(payload.get("source", "")).lower()
        if source == "text":
            return parse_import_tracks(
                str(payload.get("tracks", "")),
                str(payload.get("filename", "")),
            )
        if source == "search":
            raise InputError("Search YouTube and choose a result first.")
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
                tracks.append(Track(
                    title=str(entry.get("title") or "YouTube item"),
                    direct_url=str(entry_url),
                    released_at=release_date_text(entry),
                ))
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
            released_at=release_date_text(info),
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

        filename = output_filename_stem(track, payload)
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
        metadata_args = ffmpeg_metadata_args(rekordbox_file_tags(track, payload))
        if metadata_args:
            options["postprocessor_args"] = {"FFmpegMetadata": metadata_args}
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([self._youtube_source_for_track(track, options)])
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

    def _youtube_source_for_track(self, track: Track, options: Dict[str, Any]) -> str:
        if track.direct_url:
            return track.direct_url
        try:
            import yt_dlp
        except ImportError as error:
            raise InputError("Download support is still installing. Restart the app and try again.") from error
        search_options = dict(options)
        search_options.pop("postprocessors", None)
        search_options.pop("progress_hooks", None)
        search_options["extract_flat"] = "in_playlist"
        try:
            with yt_dlp.YoutubeDL(search_options) as searcher:
                info = searcher.extract_info(
                    f"ytsearch{YOUTUBE_SEARCH_RESULTS}:{track.search_query}",
                    download=False,
                )
        except Exception as error:
            raise InputError("YouTube could not find a matching video for this track.") from error
        entries = [
            entry for entry in (info.get("entries") or [] if isinstance(info, dict) else [])
            if isinstance(entry, dict)
        ]
        chosen = choose_youtube_result(track, entries)
        url = _youtube_result_url(chosen) if chosen else ""
        if not url:
            raise InputError("YouTube could not find a matching video for this track.")
        return url

    def _write_dj_assets(
        self,
        job_id: str,
        audio_path: Path,
        track: Track,
        payload: Dict[str, Any],
    ) -> List[Path]:
        """Write a DJ sidecar and optionally extract Rekordbox-importable stem WAVs."""
        try:
            card = prepare_dj_assets(
                audio_path,
                artist=track.artist,
                title=track.title,
                bpm=track.bpm,
                musical_key=track.musical_key,
                camelot=track.camelot,
                genre=track.genre,
                mix_name=track.mix_name,
                duration_ms=track.duration_ms,
                analysis_source=track.analysis_source,
                extract_stems=bool(payload.get("extract_suggested_stems")),
            )
        except Exception as error:
            self._log(job_id, f"Could not write DJ sidecar for {track.label}: {error}")
            return []
        sidecar = Path(str(card.get("sidecar_path") or ""))
        if sidecar.is_file():
            self._log(job_id, f"DJ sidecar: {sidecar.name}")
        skipped = (card.get("stems") or {}).get("skipped_reason")
        if skipped:
            self._log(job_id, skipped)
        extracted = (card.get("stems") or {}).get("extracted") or {}
        paths: List[Path] = []
        for stem, path_value in extracted.items():
            path = Path(str(path_value))
            if path.is_file():
                paths.append(path)
                self._log(job_id, f"Rekordbox stem WAV ({stem}): {path.name}")
        return paths

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
            self._checkpoint(job_id, abort_current=True)
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
