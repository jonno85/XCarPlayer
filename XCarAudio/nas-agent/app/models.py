from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    pending = "pending"
    downloading = "downloading"
    done = "done"
    failed = "failed"


# ---------------------------------------------------------------------------
# Legacy per-track models
# ---------------------------------------------------------------------------

class TrackJobRequest(BaseModel):
    playlist_name: str
    title: str
    artist: str
    search_query: Optional[str] = None


class TrackJobResponse(BaseModel):
    id: str
    status: JobStatus
    playlist_name: str
    title: str
    artist: str
    file_path: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Playlist models
# ---------------------------------------------------------------------------

class PlaylistJobRequest(BaseModel):
    playlist_url: str
    playlist_name: str
    spotify_token: Optional[str] = None
    spotify_credential: Optional[str] = None


class FailedTrack(BaseModel):
    title: str
    error: str


class SpotifyChangeSummary(BaseModel):
    had_previous_snapshot: bool
    added_count: int
    removed_count: int
    unchanged_count: int


class PlaylistJobResponse(BaseModel):
    id: str
    status: JobStatus
    playlist_url: str
    playlist_name: str
    source: str
    tracks_total: int
    tracks_done: int
    tracks_failed: int
    current_track: Optional[str]
    failed_tracks: list[FailedTrack]
    spotify_changes: Optional[SpotifyChangeSummary] = None
    error: Optional[str]
