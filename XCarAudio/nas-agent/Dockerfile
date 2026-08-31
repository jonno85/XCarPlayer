FROM python:3.13-alpine AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-alpine

# ffmpeg is required by yt-dlp for audio extraction
RUN apk add --no-cache ffmpeg

WORKDIR /app
COPY --from=builder /install /usr/local
COPY main.py .
COPY app/ app/

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
