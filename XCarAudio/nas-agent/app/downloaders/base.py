from pathlib import Path

import yt_dlp

# Shared yt-dlp postprocessor config used by all downloaders
YDL_AUDIO_POSTPROCESSORS = [
    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
    {"key": "FFmpegMetadata", "add_metadata": True},
]


def detect_source(url: str) -> str:
    if "spotify.com" in url or url.startswith("spotify:"):
        return "spotify"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "beatport.com" in url:
        return "beatport"
    return "unknown"


def safe_name(name: str) -> str:
    """Sanitise a string for use as a filename or directory name."""
    return "".join(c if c.isalnum() or c in " -_." else "_" for c in name).strip()


def ydl_download(query: str, opts: dict) -> None:
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([query])


def ydl_extract_info(url: str, flat: bool = False) -> dict:
    opts = {"quiet": True, "no_warnings": True}
    if flat:
        opts["extract_flat"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def ydl_opts_for_search(output_path: Path) -> dict:
    """Base yt-dlp options for a YouTube search + download."""
    return {
        "format": "bestaudio/best",
        "outtmpl": str(output_path),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": YDL_AUDIO_POSTPROCESSORS,
        "default_search": "ytsearch1",
    }
