FROM python:3.13-slim

# ffmpeg is required by yt-dlp for audio extraction
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# App dependencies (fastapi 0.135+)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# spotDL in an isolated venv — it pins fastapi<0.104 which conflicts with ours
RUN python -m venv /opt/spotdl-venv && \
    /opt/spotdl-venv/bin/pip install --no-cache-dir "spotdl>=4.4.3"

COPY main.py .
COPY app/ app/

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
