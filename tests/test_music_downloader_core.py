import tempfile
import time
import unittest
from pathlib import Path

from music_downloader_core import (
    ConfigStore,
    DownloadManager,
    InputError,
    LibraryHistory,
    Track,
    normalized_track_key,
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
        for _ in range(100):
            job = manager.snapshot(job_id)
            if job["state"] in {"complete", "failed"}:
                return job
            time.sleep(0.01)
        self.fail("Download worker did not finish")


if __name__ == "__main__":
    unittest.main()
