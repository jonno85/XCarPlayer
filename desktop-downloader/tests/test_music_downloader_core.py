import tempfile
import threading
import time
import unittest
from pathlib import Path

from music_downloader_core import (
    ConfigStore,
    DownloadManager,
    InputError,
    LibraryHistory,
    Track,
    _spotify_tracks_from_embed_data,
    normalized_track_key,
    parse_import_tracks,
    parse_spotify_url,
    parse_text_tracks,
    safe_filename,
    validate_source_url,
)


class MusicDownloaderCoreTests(unittest.TestCase):
    def test_song_list_parses_artist_title_and_ignores_duplicates(self) -> None:
        tracks = parse_text_tracks(
            "# My playlist\n\nArtist One - First Song\nSolo Song\nartist one - first song\n"
        )

        self.assertEqual([(track.artist, track.title) for track in tracks], [
            ("Artist One", "First Song"),
            ("", "Solo Song"),
        ])

    def test_empty_song_list_explains_how_to_fix_it(self) -> None:
        with self.assertRaisesRegex(InputError, "one song per line"):
            parse_text_tracks("# Only a comment\n")

    def test_spotify_urls_and_uris_are_parsed(self) -> None:
        self.assertEqual(
            parse_spotify_url("https://open.spotify.com/playlist/3BIeoPTMw0FkSezCDxGNIj?si=x"),
            ("playlist", "3BIeoPTMw0FkSezCDxGNIj"),
        )
        self.assertEqual(parse_spotify_url("spotify:track:abc123"), ("track", "abc123"))

    def test_spotify_public_embed_playlist_is_parsed_without_credentials(self) -> None:
        data = {
            "props": {"pageProps": {"state": {"data": {"entity": {
                "trackList": [
                    {"title": "Canzone", "subtitle": "Artista"},
                    {"title": "Second Song", "subtitle": "Other Artist"},
                ]
            }}}}}
        }
        tracks = _spotify_tracks_from_embed_data(data, "playlist")
        self.assertEqual(
            [(track.artist, track.title) for track in tracks],
            [("Artista", "Canzone"), ("Other Artist", "Second Song")],
        )

    def test_spotify_public_embed_track_is_parsed_without_credentials(self) -> None:
        data = {
            "props": {"pageProps": {"state": {"data": {"entity": {
                "type": "track",
                "title": "Canzone",
                "artists": [{"name": "Artista"}],
            }}}}}
        }
        self.assertEqual(
            _spotify_tracks_from_embed_data(data, "track")[0].label,
            "Artista — Canzone",
        )

    def test_exporter_csv_artist_and_title_columns_are_detected(self) -> None:
        tracks = parse_import_tracks(
            'Track Name,Artist Name(s),Album\n"Canzone","Artista","Album A"\n',
            "playlist.csv",
        )
        self.assertEqual([(track.artist, track.title) for track in tracks], [("Artista", "Canzone")])

    def test_source_validation_rejects_a_link_from_another_provider(self) -> None:
        with self.assertRaisesRegex(InputError, "valid YouTube"):
            validate_source_url("youtube", "https://open.spotify.com/track/abc123")

    def test_filename_is_safe_for_windows_and_macos(self) -> None:
        self.assertEqual(safe_filename('  A/B: "Song"?  '), "A_B_ _Song__")

    def test_preferences_round_trip_outside_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = ConfigStore(Path(temporary_directory) / "settings.json")
            saved = store.save({
                "download_dir": "~/Music/Test library",
                "github_repository": "example/project",
            })
            self.assertTrue(saved["download_dir"].endswith("Music/Test library"))
            self.assertEqual(saved["language"], "en")
            self.assertEqual(saved["audio_format"], "mp3")
            self.assertEqual(store.load(), saved)

    def test_preferences_save_italian_and_audio_format(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = ConfigStore(Path(temporary_directory) / "settings.json")
            saved = store.save({
                "download_dir": temporary_directory,
                "github_repository": "example/project",
                "language": "it",
                "audio_format": "flac",
            })
            self.assertEqual((saved["language"], saved["audio_format"]), ("it", "flac"))

    def test_download_requires_rights_confirmation_before_starting_worker(self) -> None:
        with self.assertRaisesRegex(InputError, "rights or permission"):
            DownloadManager().create({
                "source": "text",
                "tracks": "Artist - Title",
                "output_dir": "/tmp/library",
                "rights_confirmed": False,
            })

    def test_youtube_cookie_browser_is_limited_to_supported_browser_names(self) -> None:
        manager = DownloadManager()
        self.assertEqual(manager._youtube_cookie_browser({"youtube_browser": "firefox"}), "firefox")
        with self.assertRaisesRegex(InputError, "supported browser"):
            manager._youtube_cookie_browser({"youtube_browser": "not-a-browser"})

    def test_audio_format_is_validated_before_worker_starts(self) -> None:
        with self.assertRaisesRegex(InputError, "M4A"):
            DownloadManager().create({
                "source": "text",
                "tracks": "Artist - Title",
                "output_dir": "/tmp/library",
                "rights_confirmed": True,
                "audio_format": "mp4",
            })

    def test_history_records_scans_and_resolves_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            audio = root / "Artist - Song.mp3"
            audio.write_bytes(b"test audio")
            history = LibraryHistory(root / "history.json")
            entry = history.record(audio, Track(title="Song", artist="Artist"), "text", "mp3", "job")

            self.assertEqual(history.resolve_media(entry["id"]), audio.resolve())
            self.assertEqual(history.scan(root)["tracked"], 1)
            self.assertEqual(history.find_existing(root, Track(title="Song", artist="Artist")), audio)

    def test_rekordbox_playlist_uses_relative_utf8_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            audio = root / "Artista - Canzone.mp3"
            audio.write_bytes(b"test")
            playlist = DownloadManager()._write_m3u8(root, "Serata", [audio])
            contents = playlist.read_text(encoding="utf-8-sig")
            self.assertEqual(contents, "#EXTM3U\nArtista - Canzone.mp3\n")

    def test_track_key_ignores_filename_punctuation(self) -> None:
        self.assertEqual(normalized_track_key("Artist - Song.mp3"), "artist song")

    def test_download_job_records_history_playlist_and_existing_track(self) -> None:
        class FakeDownloadManager(DownloadManager):
            def _tracks_for_payload(self, payload):
                return [Track(title="Song", artist="Artist")]

            def _download_track(self, job_id, track, output_directory, payload):
                path = output_directory / f"Artist - Song.{payload['audio_format']}"
                path.write_bytes(b"audio")
                return path

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            history = LibraryHistory(root / "history.json")
            manager = FakeDownloadManager(history)
            payload = {
                "source": "text",
                "tracks": "Artist - Song",
                "output_dir": str(root / "music"),
                "rights_confirmed": True,
                "audio_format": "flac",
                "rekordbox_playlist": True,
                "playlist_name": "DJ Set",
            }
            first = manager.create(payload)
            first = self._wait_for_job(manager, first["id"])
            self.assertEqual((first["completed"], first["existing"]), (1, 0))
            self.assertTrue(Path(first["playlist_path"]).is_file())
            self.assertEqual(first["items"][0]["status"], "downloaded")

            second = manager.create(payload)
            second = self._wait_for_job(manager, second["id"])
            self.assertEqual((second["completed"], second["existing"]), (0, 1))
            self.assertEqual(second["items"][0]["status"], "existing")

    def _wait_for_job(self, manager: DownloadManager, job_id: str) -> dict:
        for _ in range(400):
            job = manager.snapshot(job_id)
            if job["state"] in {"complete", "failed", "stopped"}:
                return job
            time.sleep(0.02)
        self.fail("Download worker did not finish")

    def _wait_until(self, predicate, message: str, timeout: float = 2.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        self.fail(message)

    def test_preview_highlights_existing_files_and_prepared_edits_are_used(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "Artist - Song.mp3").write_bytes(b"audio")
            manager = DownloadManager(LibraryHistory(root / "history.json"))
            preview = manager.preview({
                "source": "text",
                "tracks": "Artist - Song\nOther - New",
                "output_dir": str(root),
            })
            self.assertEqual(
                [track["existing"] for track in preview["tracks"]],
                [True, False],
            )
            prepared = manager._tracks_for_payload({
                "source": "spotify",
                "prepared_tracks": [
                    {"artist": "Edited", "title": "Title", "included": True},
                    {"artist": "Skip", "title": "Me", "included": False},
                ],
            })
            self.assertEqual([track.label for track in prepared], ["Edited — Title"])

    def test_download_job_can_be_paused_then_resumed(self) -> None:
        release = threading.Event()
        started = []
        downloaded = []

        class GatedDownloadManager(DownloadManager):
            def _tracks_for_payload(self, payload, allow_prepared=True):
                return [Track(title="One", artist="A"), Track(title="Two", artist="B")]

            def _download_track(self, job_id, track, output_directory, payload):
                self._checkpoint(job_id)
                started.append(track.title)
                while not release.is_set():
                    self._checkpoint(job_id)
                    time.sleep(0.02)
                if track.title == "One":
                    release.clear()
                self._checkpoint(job_id)
                path = output_directory / f"{track.artist} - {track.title}.{payload.get('audio_format', 'mp3')}"
                path.write_bytes(b"audio")
                downloaded.append(track.title)
                return path

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manager = GatedDownloadManager(LibraryHistory(root / "history.json"))
            job = manager.create({
                "source": "text",
                "tracks": "A - One\nB - Two",
                "output_dir": str(root / "music"),
                "rights_confirmed": True,
            })
            self._wait_until(lambda: started == ["One"], "First track did not start")
            paused = manager.pause(job["id"])
            self.assertEqual(paused["state"], "paused")
            time.sleep(0.15)
            self.assertEqual(downloaded, [])
            self.assertEqual(manager.snapshot(job["id"])["state"], "paused")
            manager.resume(job["id"])
            release.set()
            self._wait_until(lambda: started == ["One", "Two"], "Second track did not start after resume")
            release.set()
            finished = self._wait_for_job(manager, job["id"])
            self.assertEqual(finished["state"], "complete")
            self.assertEqual(downloaded, ["One", "Two"])
            self.assertEqual(finished["completed"], 2)

    def test_download_job_stop_cancels_remaining_tracks(self) -> None:
        release = threading.Event()
        started = []
        downloaded = []

        class GatedDownloadManager(DownloadManager):
            def _tracks_for_payload(self, payload, allow_prepared=True):
                return [Track(title="One", artist="A"), Track(title="Two", artist="B")]

            def _download_track(self, job_id, track, output_directory, payload):
                self._checkpoint(job_id)
                started.append(track.title)
                while not release.is_set():
                    self._checkpoint(job_id)
                    time.sleep(0.02)
                if track.title == "One":
                    release.clear()
                self._checkpoint(job_id)
                path = output_directory / f"{track.artist} - {track.title}.{payload.get('audio_format', 'mp3')}"
                path.write_bytes(b"audio")
                downloaded.append(track.title)
                return path

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manager = GatedDownloadManager(LibraryHistory(root / "history.json"))
            job = manager.create({
                "source": "text",
                "tracks": "A - One\nB - Two",
                "output_dir": str(root / "music"),
                "rights_confirmed": True,
            })
            self._wait_until(lambda: started == ["One"], "First track did not start")
            release.set()
            self._wait_until(lambda: started == ["One", "Two"], "Second track did not start")
            stopped = manager.stop(job["id"])
            self.assertEqual(stopped["message"], "Stopping…")
            finished = self._wait_for_job(manager, job["id"])
            self.assertEqual(finished["state"], "stopped")
            self.assertEqual(downloaded, ["One"])
            self.assertEqual(finished["completed"], 1)
            self.assertIn("cancelled", finished["message"])

    def test_pause_is_rejected_after_the_job_finishes(self) -> None:
        class InstantManager(DownloadManager):
            def _tracks_for_payload(self, payload, allow_prepared=True):
                return [Track(title="Song", artist="Artist")]

            def _download_track(self, job_id, track, output_directory, payload):
                path = output_directory / "Artist - Song.mp3"
                path.write_bytes(b"audio")
                return path

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manager = InstantManager(LibraryHistory(root / "history.json"))
            job = manager.create({
                "source": "text",
                "tracks": "Artist - Song",
                "output_dir": str(root / "music"),
                "rights_confirmed": True,
            })
            self._wait_for_job(manager, job["id"])
            with self.assertRaisesRegex(InputError, "already finished"):
                manager.pause(job["id"])
            with self.assertRaisesRegex(InputError, "already finished"):
                manager.stop(job["id"])


if __name__ == "__main__":
    unittest.main()
