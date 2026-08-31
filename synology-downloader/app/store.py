# In-memory job stores.
# Both dicts map job_id -> job dict and survive only for the lifetime of the process.
# Replace with a persistent store (e.g. SQLite via aiosqlite) if restarts matter.

track_jobs: dict[str, dict] = {}
playlist_jobs: dict[str, dict] = {}
