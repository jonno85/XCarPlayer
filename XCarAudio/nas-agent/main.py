"""X Car Audio — NAS Agent entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import health, jobs, playlist_jobs

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="X Car Audio NAS Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(playlist_jobs.router)
