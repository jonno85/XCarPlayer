"""
X Car Audio — NAS Agent
Runs inside Docker on the Synology NAS.
Receives download jobs from the iOS app, downloads via yt-dlp,
and saves MP3s to the AudioStation music folder.
"""

import os
import uuid
import asyncio
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nas-agent")

app = FastAPI(title="X Car Audio NAS Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict to your NAS IP in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Music output directory — map this volume in docker-compose to your AudioStation folder
MUSIC_DIR = Path(os.getenv("MUSIC_DIR", "/music"))

# In-memory job store (survives restarts only if you add a DB — fine for personal use)
jobs: dict[str, dict] = {}


class JobStatus(str, Enum):
    pending = "pending"
    downloading = "downloading"
    done = "done"
    failed = "failed"


class JobRequest(BaseModel):
    playlist_name: str
    title: str
    artist: str
    # Optional: if provided, used as the search query directly
    search_query: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    playlist_name: str
    title: str
    artist: str
    file_path: Optional[str] = None
    error: Optional[str] = None


@app.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(req: JobRequest):
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
    jobs[job_id] = job
    # Run download in background so the response returns immediately
    asyncio.create_task(run_download(job_id))
    return job


@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs():
    return list(jobs.values())


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    del jobs[job_id]


async def run_download(job_id: str):
    job = jobs[job_id]
    job["status"] = JobStatus.downloading
    log.info(f"[{job_id}] Downloading: {job['artist']} - {job['title']}")

    playlist_dir = MUSIC_DIR / _safe_name(job["playlist_name"])
    playlist_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(playlist_dir / f"{_safe_name(job['artist'])} - {_safe_name(job['title'])}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            },
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
        ],
        # Search YouTube — takes the first result
        "default_search": "ytsearch1",
    }

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _download, job["search_query"], ydl_opts)
        # Locate the written file (ext may vary before post-processing)
        mp3_path = output_template.replace(".%(ext)s", ".mp3")
        job["file_path"] = mp3_path
        job["status"] = JobStatus.done
        log.info(f"[{job_id}] Done: {mp3_path}")
    except Exception as e:
        job["status"] = JobStatus.failed
        job["error"] = str(e)
        log.error(f"[{job_id}] Failed: {e}")


def _download(query: str, opts: dict):
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([query])


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in " -_." else "_" for c in name).strip()
