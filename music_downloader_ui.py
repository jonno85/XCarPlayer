#!/usr/bin/env python3
"""Local browser UI for Music Library Downloader.

The server deliberately binds only to 127.0.0.1. It never exposes the
downloader, its configuration, or Spotify credentials to the local network.
"""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Type
from urllib.parse import parse_qs, urlparse

from music_downloader_core import (
    APP_NAME,
    ConfigStore,
    DownloadManager,
    InputError,
    LibraryHistory,
    get_update_status,
    install_update,
)


SOURCE_ROOT = Path(__file__).resolve().parent
IS_FROZEN = bool(getattr(sys, "frozen", False))
PROJECT_ROOT = Path(sys.executable).resolve().parent if IS_FROZEN else SOURCE_ROOT
WEB_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT)) / "web"
MAX_REQUEST_BYTES = 1_500_000


def request_handler(
    config_store: ConfigStore,
    download_manager: DownloadManager,
    history: LibraryHistory,
) -> Type[BaseHTTPRequestHandler]:
    """Create a request handler with this process's state attached."""

    class MusicLibraryRequestHandler(BaseHTTPRequestHandler):
        server_version = "MusicLibraryDownloader/1.0"

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            request = urlparse(self.path)
            if request.path == "/":
                self._serve_index()
            elif request.path == "/app.js":
                self._serve_asset("app.js", "text/javascript; charset=utf-8")
            elif request.path == "/api/config":
                self._send_json({"settings": config_store.load()})
            elif request.path == "/api/job":
                job_id = parse_qs(request.query).get("id", [""])[0]
                try:
                    self._send_json({"job": download_manager.snapshot(job_id)})
                except InputError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
            elif request.path == "/api/history":
                self._send_json({"entries": history.entries()})
            elif request.path == "/api/media":
                media_id = parse_qs(request.query).get("id", [""])[0]
                try:
                    self._serve_media(history.resolve_media(media_id))
                except InputError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
            elif request.path == "/api/update-status":
                self._send_json(
                    get_update_status(PROJECT_ROOT, config_store.load()["github_repository"])
                )
            else:
                self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            try:
                payload = self._read_json()
                if self.path == "/api/config":
                    self._send_json({"settings": config_store.save(payload)})
                elif self.path == "/api/download":
                    self._send_json({"job": download_manager.create(payload)}, HTTPStatus.ACCEPTED)
                elif self.path == "/api/pick-folder":
                    selected = choose_destination_folder(
                        str(payload.get("current", config_store.load()["download_dir"]))
                    )
                    self._send_json({"path": selected})
                elif self.path == "/api/scan-library":
                    directory = Path(str(payload.get("directory", "")))
                    self._send_json({"library": history.scan(directory)})
                elif self.path == "/api/install-update":
                    self._send_json(
                        install_update(PROJECT_ROOT, config_store.load()["github_repository"])
                    )
                elif self.path == "/api/quit":
                    self._send_json({"message": "Music Library Downloader is closing."})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                else:
                    self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            except InputError as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            except json.JSONDecodeError:
                self._send_json({"error": "The request was not valid JSON."}, HTTPStatus.BAD_REQUEST)

        def _read_json(self) -> Dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                raise InputError("That request is empty or too large.")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise InputError("The request must contain an object.")
            return payload

        def _serve_index(self) -> None:
            self._serve_asset("index.html", "text/html; charset=utf-8")

        def _serve_asset(self, filename: str, content_type: str) -> None:
            try:
                page = (WEB_ROOT / filename).read_bytes()
            except OSError:
                self._send_json({"error": "The UI files are missing."}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self' 'unsafe-inline'; media-src 'self'",
            )
            self.end_headers()
            self.wfile.write(page)

        def _serve_media(self, path: Path) -> None:
            file_size = path.stat().st_size
            start, end = 0, file_size - 1
            range_header = self.headers.get("Range", "")
            if range_header.startswith("bytes="):
                try:
                    start_text, end_text = range_header[6:].split("-", 1)
                    start = int(start_text) if start_text else 0
                    end = int(end_text) if end_text else file_size - 1
                    end = min(end, file_size - 1)
                except (ValueError, IndexError):
                    self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    return
            length = max(0, end - start + 1)
            self.send_response(
                HTTPStatus.PARTIAL_CONTENT if range_header else HTTPStatus.OK
            )
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "audio/mpeg")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if range_header:
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.end_headers()
            with path.open("rb") as media_file:
                media_file.seek(start)
                remaining = length
                while remaining:
                    chunk = media_file.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

        def _send_json(self, body: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, _format: str, *_args: Any) -> None:
            """Keep routine browser polling out of the terminal."""

    return MusicLibraryRequestHandler


def choose_destination_folder(current: str = "") -> str:
    """Open the operating system's native folder chooser."""
    initial = str(Path(current).expanduser())
    try:
        if os.name == "nt":
            script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$d=New-Object System.Windows.Forms.FolderBrowserDialog; "
                f"$d.SelectedPath='{initial.replace(chr(39), chr(39) * 2)}'; "
                "if($d.ShowDialog() -eq 'OK'){$d.SelectedPath}"
            )
            return subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", script],
                text=True,
                timeout=120,
            ).strip()
        if sys.platform == "darwin":
            script = 'POSIX path of (choose folder with prompt "Choose your music library")'
            return subprocess.check_output(
                ["osascript", "-e", script], text=True, timeout=120
            ).strip()
        if shutil.which("zenity"):
            return subprocess.check_output(
                ["zenity", "--file-selection", "--directory", f"--filename={initial}/"],
                text=True,
                timeout=120,
            ).strip()
        if shutil.which("kdialog"):
            return subprocess.check_output(
                ["kdialog", "--getexistingdirectory", initial],
                text=True,
                timeout=120,
            ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""
    raise InputError(
        "No native folder picker is available on this Linux desktop. "
        "Install zenity or kdialog, then restart the app."
    )


def main() -> int:
    config_store = ConfigStore()
    history = LibraryHistory()
    download_manager = DownloadManager(history)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        request_handler(config_store, download_manager, history),
    )
    server.daemon_threads = True
    address = f"http://127.0.0.1:{server.server_port}"
    print(f"{APP_NAME} is ready at {address}")
    if not IS_FROZEN:
        print("Keep this terminal open while downloading. Press Ctrl+C to stop.")
    webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Music Library Downloader.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
