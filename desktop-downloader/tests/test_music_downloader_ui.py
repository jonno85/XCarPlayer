import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from music_downloader_core import ConfigStore, DownloadManager, LibraryHistory, Track
from music_downloader_ui import repository_root, request_handler


class MusicDownloaderUiApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.library = root / "Music"
        self.library.mkdir()
        self.audio = self.library / "Artista - Canzone.mp3"
        self.audio.write_bytes(b"ID3-test-audio-content")
        self.config = ConfigStore(root / "settings.json")
        self.config.save({
            "download_dir": str(self.library),
            "github_repository": "example/project",
            "language": "it",
            "audio_format": "flac",
        })
        self.history = LibraryHistory(root / "history.json")
        self.entry = self.history.record(
            self.audio, Track(title="Canzone", artist="Artista"), "text", "mp3", "playlist"
        )
        self.manager = DownloadManager(self.history)
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            request_handler(self.config, self.manager, self.history),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary_directory.cleanup()

    def get_json(self, path: str) -> dict:
        with urlopen(self.base_url + path, timeout=3) as response:
            return json.load(response)

    def post_json(self, path: str, payload: dict) -> dict:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            return json.load(response)

    def test_config_history_and_scan_endpoints(self) -> None:
        self.assertEqual(self.get_json("/api/config")["settings"]["language"], "it")
        self.assertEqual(self.get_json("/api/history")["entries"][0]["label"], "Artista — Canzone")
        scan = self.post_json("/api/scan-library", {"directory": str(self.library)})["library"]
        self.assertEqual((scan["total"], scan["tracked"]), (1, 1))

    def test_preview_endpoint_parses_exporter_csv_and_marks_existing(self) -> None:
        preview = self.post_json("/api/preview", {
            "source": "text",
            "filename": "export.csv",
            "tracks": "Artist Name(s),Track Name\nArtista,Canzone\n",
            "output_dir": str(self.library),
        })["preview"]
        self.assertEqual(preview["total"], 1)
        self.assertEqual(preview["tracks"][0]["title"], "Canzone")
        self.assertTrue(preview["tracks"][0]["existing"])

    def test_media_endpoint_supports_byte_ranges_for_seeking(self) -> None:
        request = Request(
            f"{self.base_url}/api/media?id={self.entry['id']}",
            headers={"Range": "bytes=4-7"},
        )
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.headers["Content-Range"], "bytes 4-7/22")
            self.assertEqual(response.read(), b"test")

    def test_media_endpoint_rejects_unknown_history_item(self) -> None:
        with self.assertRaises(HTTPError) as error:
            urlopen(f"{self.base_url}/api/media?id=unknown", timeout=3)
        self.assertEqual(error.exception.code, 404)

    def test_folder_picker_endpoint_returns_native_selection(self) -> None:
        with patch("music_downloader_ui.choose_destination_folder", return_value=str(self.library)):
            selected = self.post_json("/api/pick-folder", {"current": "/tmp"})
        self.assertEqual(selected["path"], str(self.library))

    def test_repository_root_is_found_from_nested_desktop_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / ".git").mkdir()
            nested = root / "desktop-downloader" / "web"
            nested.mkdir(parents=True)
            self.assertEqual(repository_root(nested), root)

    def test_job_control_endpoints_pause_resume_and_stop_an_active_job(self) -> None:
        ready = threading.Event()
        release = threading.Event()

        def gated_download(job_id, track, output_directory, payload):
            self.manager._checkpoint(job_id)
            ready.set()
            while not release.is_set():
                self.manager._checkpoint(job_id)
                time.sleep(0.02)
            path = Path(output_directory) / f"{track.artist} - {track.title}.mp3"
            path.write_bytes(b"audio")
            return path

        self.manager._tracks_for_payload = lambda payload, allow_prepared=True: [  # type: ignore[method-assign]
            Track(title="One", artist="A"),
            Track(title="Two", artist="B"),
        ]
        self.manager._download_track = gated_download  # type: ignore[method-assign]
        job = self.post_json("/api/download", {
            "source": "text",
            "tracks": "A - One\nB - Two",
            "output_dir": str(self.library),
            "rights_confirmed": True,
        })["job"]
        self.assertTrue(ready.wait(timeout=2))
        paused = self.post_json("/api/job/pause", {"id": job["id"]})["job"]
        self.assertEqual(paused["state"], "paused")
        resumed = self.post_json("/api/job/resume", {"id": job["id"]})["job"]
        self.assertEqual(resumed["state"], "downloading")
        stopped = self.post_json("/api/job/stop", {"id": job["id"]})["job"]
        self.assertEqual(stopped["message"], "Stopping…")
        for _ in range(100):
            snapshot = self.get_json(f"/api/job?id={job['id']}")["job"]
            if snapshot["state"] == "stopped":
                break
            time.sleep(0.02)
        else:
            self.fail("Stopped job did not settle")
        self.assertEqual(snapshot["state"], "stopped")

    def test_job_control_endpoints_reject_unknown_jobs(self) -> None:
        with self.assertRaises(HTTPError) as error:
            self.post_json("/api/job/pause", {"id": "missing"})
        self.assertEqual(error.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
