"""Playlist-level download jobs — one job covers an entire playlist URL."""

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Security

from app.auth import require_api_key
from app.config import MUSIC_DIR
from app.downloaders import beatport, spotify, youtube
from app.downloaders.base import detect_source, safe_name
from app.models import JobStatus, PlaylistJobRequest, PlaylistJobResponse
from app.store import playlist_jobs

log = logging.getLogger("nas-agent.playlist_jobs")
router = APIRouter(prefix="/playlist-jobs", tags=["playlist-jobs"])

_DOWNLOADERS = {
    "spotify": spotify.download,
    "youtube": youtube.download,
    "beatport": beatport.download,
}


@router.post("", response_model=PlaylistJobResponse, status_code=201, dependencies=[Security(require_api_key)])
async def create_playlist_job(req: PlaylistJobRequest):
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "status": JobStatus.pending,
        "playlist_url": req.playlist_url,
        "playlist_name": req.playlist_name,
        "source": detect_source(req.playlist_url),
        "tracks_total": 0,
        "tracks_done": 0,
        "tracks_failed": 0,
        "current_track": None,
        "failed_tracks": [],
        "error": None,
    }
    playlist_jobs[job_id] = job
    asyncio.create_task(_run_playlist_download(job_id))
    return job


@router.get("", response_model=list[PlaylistJobResponse], dependencies=[Security(require_api_key)])
async def list_playlist_jobs():
    return list(playlist_jobs.values())


@router.get("/{job_id}", response_model=PlaylistJobResponse, dependencies=[Security(require_api_key)])
async def get_playlist_job(job_id: str):
    job = playlist_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Playlist job not found")
    return job


@router.delete("/{job_id}", status_code=204, dependencies=[Security(require_api_key)])
async def delete_playlist_job(job_id: str):
    if job_id not in playlist_jobs:
        raise HTTPException(status_code=404, detail="Playlist job not found")
    del playlist_jobs[job_id]


async def _run_playlist_download(job_id: str) -> None:
    job = playlist_jobs[job_id]
    source = job["source"]
    job["status"] = JobStatus.downloading
    log.info("[%s] Starting — source=%s url=%s", job_id, source, job["playlist_url"])

    downloader = _DOWNLOADERS.get(source)
    if downloader is None:
        job["status"] = JobStatus.failed
        job["error"] = f"Unsupported playlist source: {source}"
        log.error("[%s] %s", job_id, job["error"])
        return

    playlist_dir = MUSIC_DIR / safe_name(job["playlist_name"])
    playlist_dir.mkdir(parents=True, exist_ok=True)

    try:
        await asyncio.get_event_loop().run_in_executor(None, downloader, job, playlist_dir)
        job["status"] = JobStatus.done
        log.info("[%s] Done — %d succeeded, %d failed", job_id, job["tracks_done"], job["tracks_failed"])
    except Exception as exc:
        job["status"] = JobStatus.failed
        job["error"] = str(exc)
        log.error("[%s] Failed: %s", job_id, exc)
