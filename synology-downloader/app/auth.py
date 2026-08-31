import secrets

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import API_KEY

_header = APIKeyHeader(name="X-API-Key")


def require_api_key(key: str = Security(_header)) -> None:
    if not secrets.compare_digest(key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
