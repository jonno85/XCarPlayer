"""Legacy per-track download jobs — kept for backwards compatibility."""

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Security

from app.auth import require_api_key
from app.config import MUSIC_DIR
from app.downloaders.base import safe_name, ydl_download, ydl_opts_for_search
from app.models import JobStatus, TrackJobRequest, TrackJobResponse
from app.store import track_jobs

log = logging.getLogger("nas-agent.jobs")
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=TrackJobResponse, status_code=201, dependencies=[Security(require_api_key)])
async def create_job(req: TrackJobRequest):
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "status": JobStatus.pending,
        "playlist_name": req.playlist_name,
        "title": req.title,
        "artist": req.artist,
        "search_query": req.search_query or f"{req.artist} {req.title} audio",
        "file_path": None,
        "error": None,
    }
    track_jobs[job_id] = job
    asyncio.create_task(_run_download(job_id))
    return job


@router.get("", response_model=list[TrackJobResponse], dependencies=[Security(require_api_key)])
async def list_jobs():
    return list(track_jobs.values())


@router.get("/{job_id}", response_model=TrackJobResponse, dependencies=[Security(require_api_key)])
async def get_job(job_id: str):
    job = track_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204, dependencies=[Security(require_api_key)])
async def delete_job(job_id: str):
    if job_id not in track_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    del track_jobs[job_id]


async def _run_download(job_id: str) -> None:
    job = track_jobs[job_id]
    job["status"] = JobStatus.downloading
    log.info("[%s] Downloading: %s - %s", job_id, job["artist"], job["title"])

    playlist_dir = MUSIC_DIR / safe_name(job["playlist_name"])
    playlist_dir.mkdir(parents=True, exist_ok=True)

    output_path = playlist_dir / f"{safe_name(job['artist'])} - {safe_name(job['title'])}.%(ext)s"

    try:
        await asyncio.get_event_loop().run_in_executor(
            None, ydl_download, job["search_query"], ydl_opts_for_search(output_path)
        )
        job["file_path"] = str(output_path).replace(".%(ext)s", ".mp3")
        job["status"] = JobStatus.done
        log.info("[%s] Done: %s", job_id, job["file_path"])
    except Exception as exc:
        job["status"] = JobStatus.failed
        job["error"] = str(exc)
        log.error("[%s] Failed: %s", job_id, exc)
