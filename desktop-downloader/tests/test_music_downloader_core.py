import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path

from music_downloader_core import (
    ConfigStore,
    DownloadManager,
    InputError,
    LibraryHistory,
    Track,
    _beatport_tracks_from_data,
    _spotify_tracks_from_embed_data,
    _unique_tracks,
    choose_youtube_result,
    crate_datetime,
    ffmpeg_metadata_args,
    normalized_track_key,
    output_filename_stem,
    parse_import_tracks,
    parse_provider_datetime,
    parse_spotify_url,
    parse_text_tracks,
    playlist_crate_directory,
    rekordbox_file_tags,
    release_date_text,
    safe_filename,
    validate_source_url,
    year_month_save_directory,
    youtube_search_hits,
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
                    {"title": "Canzone", "subtitle": "Artista", "album": {"release_date": "2025-03-09"}},
                    {"title": "Second Song", "subtitle": "Other Artist"},
                ]
            }}}}}
        }
        tracks = _spotify_tracks_from_embed_data(data, "playlist")
        self.assertEqual(
            [(track.artist, track.title, track.released_at) for track in tracks],
            [("Artista", "Canzone", "2025-03-09"), ("Other Artist", "Second Song", "")],
        )

    def test_spotify_public_embed_track_is_parsed_without_credentials(self) -> None:
        data = {
            "props": {"pageProps": {"state": {"data": {"entity": {
                "type": "track",
                "title": "Canzone",
                "artists": [{"name": "Artista"}],
                "releaseDate": "2024-11-22",
            }}}}}
        }
        self.assertEqual(
            _spotify_tracks_from_embed_data(data, "track")[0].label,
            "Artista — Canzone",
        )
        self.assertEqual(_spotify_tracks_from_embed_data(data, "track")[0].released_at, "2024-11-22")

    def test_spotify_embed_keeps_mix_titles_duration_and_cleans_artists(self) -> None:
        data = {
            "props": {"pageProps": {"state": {"data": {"entity": {
                "trackList": [
                    {
                        "title": "Ghetto Boy - Extended Mix",
                        "subtitle": "Sebb Junior",
                        "duration": 346890,
                    },
                    {
                        "title": "It's a House Thing - Full Intention Remix",
                        "subtitle": "Funkatomic,\xa0Full Intention",
                        "duration": 405245,
                    },
                ]
            }}}}}
        }
        tracks = _spotify_tracks_from_embed_data(data, "playlist")
        self.assertEqual(
            [(track.artist, track.title, track.duration_ms) for track in tracks],
            [
                ("Sebb Junior", "Ghetto Boy - Extended Mix", 346890),
                ("Funkatomic, Full Intention", "It's a House Thing - Full Intention Remix", 405245),
            ],
        )
        chosen = choose_youtube_result(tracks[0], [
            {
                "title": "Sebb Junior - Ghetto Boy (Radio Edit)",
                "duration": 180,
                "webpage_url": "https://www.youtube.com/watch?v=radio",
            },
            {
                "title": "Sebb Junior - Ghetto Boy (Extended Mix)",
                "duration": 347,
                "webpage_url": "https://www.youtube.com/watch?v=extended",
            },
            {
                "title": "Sebb Junior Ghetto Boy 1 Hour Mix",
                "duration": 3600,
                "webpage_url": "https://www.youtube.com/watch?v=hour",
            },
        ])
        self.assertEqual(chosen["webpage_url"], "https://www.youtube.com/watch?v=extended")

    def test_spotify_public_embed_track_keeps_duration(self) -> None:
        data = {
            "props": {"pageProps": {"state": {"data": {"entity": {
                "type": "track",
                "title": "Blinding Lights",
                "duration": 200040,
                "artists": [{"name": "The Weeknd"}],
            }}}}}
        }
        track = _spotify_tracks_from_embed_data(data, "track")[0]
        self.assertEqual((track.artist, track.title, track.duration_ms), ("The Weeknd", "Blinding Lights", 200040))

    def test_exporter_csv_artist_and_title_columns_are_detected(self) -> None:
        tracks = parse_import_tracks(
            'Track Name,Artist Name(s),Album,Release Date\n"Canzone","Artista","Album A","2025-03-09"\n',
            "playlist.csv",
        )
        self.assertEqual(
            [(track.artist, track.title, track.released_at) for track in tracks],
            [("Artista", "Canzone", "2025-03-09")],
        )

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

    def test_history_finds_existing_audio_in_year_month_subfolders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested = root / "2025" / "03"
            nested.mkdir(parents=True)
            audio = nested / "Artist - Song.mp3"
            audio.write_bytes(b"test audio")
            history = LibraryHistory(root / "history.json")
            self.assertEqual(
                history.find_existing(root, Track(title="Song", artist="Artist")),
                audio,
            )

    def test_year_month_save_directory_uses_fixed_local_date(self) -> None:
        root = Path("/library")
        self.assertEqual(year_month_save_directory(root, False), root)
        self.assertEqual(
            year_month_save_directory(root, True, datetime(2025, 3, 9, 12, 0, 0)),
            root / "2025" / "03",
        )

    def test_provider_dates_parse_common_spotify_beatport_and_youtube_shapes(self) -> None:
        self.assertEqual(parse_provider_datetime("2025-03-09").month, 3)
        self.assertEqual(parse_provider_datetime("2025-03").month, 3)
        self.assertEqual(parse_provider_datetime("20250309").day, 9)
        self.assertEqual(parse_provider_datetime("2025").month, 1)
        self.assertEqual(release_date_text({"album": {"release_date": "2024-11-22"}}), "2024-11-22")
        self.assertEqual(release_date_text({"publish_date": "2016-05-20"}), "2016-05-20")
        self.assertEqual(release_date_text({"upload_date": "20260518"}), "2026-05-18")
        fallback = datetime(2026, 9, 19)
        self.assertEqual(crate_datetime(Track(title="A", released_at="2025-03-09"), fallback).month, 3)
        self.assertEqual(crate_datetime(Track(title="B"), fallback), fallback)
        music = Path("/library")
        shared = [
            music / "2025" / "03" / "A.mp3",
            music / "2025" / "03" / "B.mp3",
        ]
        mixed = [music / "2025" / "03" / "A.mp3", music / "2026" / "05" / "B.mp3"]
        self.assertEqual(playlist_crate_directory(music, True, shared, fallback), music / "2025" / "03")
        self.assertEqual(playlist_crate_directory(music, True, mixed, fallback), music / "2026" / "09")

    def test_rekordbox_file_tags_use_playlist_genre_and_crate(self) -> None:
        tags = rekordbox_file_tags(
            Track(title="Song", artist="Artist", genre="House", released_at="2025-03-09"),
            {"playlist_name": "Peak Time", "crate": "2026-05", "source": "beatport"},
        )
        self.assertEqual(tags["title"], "Song")
        self.assertEqual(tags["artist"], "Artist")
        self.assertEqual(tags["genre"], "House")
        self.assertEqual(tags["grouping"], "Peak Time")
        self.assertEqual(tags["comment"], "Peak Time | 2026-05")
        self.assertEqual(tags["date"], "2025")
        self.assertEqual(
            ffmpeg_metadata_args({"genre": "House", "grouping": "Peak Time"}),
            ["-metadata", "genre=House", "-metadata", "grouping=Peak Time"],
        )

    def test_rekordbox_file_tags_skip_title_override_for_search(self) -> None:
        tags = rekordbox_file_tags(
            Track(title="Typed", artist="Query", genre="Techno"),
            {"source": "search", "playlist_name": "Crate"},
        )
        self.assertNotIn("title", tags)
        self.assertNotIn("artist", tags)
        self.assertEqual(tags["genre"], "Techno")
        self.assertEqual(tags["grouping"], "Crate")

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
            sidecar = Path(first["output_dir"]) / "Artist - Song.dj.json"
            self.assertTrue(sidecar.is_file())
            self.assertIn('"title": "Song"', sidecar.read_text(encoding="utf-8"))

            second = manager.create(payload)
            second = self._wait_for_job(manager, second["id"])
            self.assertEqual((second["completed"], second["existing"]), (0, 1))
            self.assertEqual(second["items"][0]["status"], "existing")

    def test_year_month_folders_save_playlist_under_dated_path(self) -> None:
        class FakeDownloadManager(DownloadManager):
            def _tracks_for_payload(self, payload, allow_prepared=True):
                return [Track(title="Song", artist="Artist")]

            def _download_track(self, job_id, track, output_directory, payload):
                path = output_directory / f"Artist - Song.{payload['audio_format']}"
                path.write_bytes(b"audio")
                return path

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            music = root / "music"
            manager = FakeDownloadManager(LibraryHistory(root / "history.json"))
            job = manager.create({
                "source": "text",
                "tracks": "Artist - Song",
                "output_dir": str(music),
                "rights_confirmed": True,
                "audio_format": "mp3",
                "rekordbox_playlist": True,
                "year_month_folders": True,
                "playlist_name": "March Crate",
            })
            job = self._wait_for_job(manager, job["id"])
            self.assertEqual(job["state"], "complete")
            save_directory = Path(job["output_dir"])
            self.assertRegex(save_directory.resolve().relative_to(music.resolve()).as_posix(), r"^\d{4}/\d{2}$")
            self.assertTrue((save_directory / "Artist - Song.mp3").is_file())
            playlist = save_directory / "March Crate.m3u8"
            self.assertTrue(playlist.is_file())
            self.assertIn("Artist - Song.mp3", playlist.read_text(encoding="utf-8-sig"))

    def test_year_month_folders_reuse_track_already_saved_in_another_month(self) -> None:
        class FakeDownloadManager(DownloadManager):
            def _tracks_for_payload(self, payload, allow_prepared=True):
                return [Track(title="Song", artist="Artist")]

            def _download_track(self, job_id, track, output_directory, payload):
                raise AssertionError("Should not download a track already in the library")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            music = root / "music"
            existing_dir = music / "2025" / "03"
            existing_dir.mkdir(parents=True)
            (existing_dir / "Artist - Song.mp3").write_bytes(b"audio")
            manager = FakeDownloadManager(LibraryHistory(root / "history.json"))
            job = manager.create({
                "source": "text",
                "tracks": "Artist - Song",
                "output_dir": str(music),
                "rights_confirmed": True,
                "audio_format": "mp3",
                "rekordbox_playlist": True,
                "year_month_folders": True,
                "playlist_name": "New Month",
            })
            job = self._wait_for_job(manager, job["id"])
            self.assertEqual((job["completed"], job["existing"]), (0, 1))
            self.assertEqual(Path(job["output_dir"]).resolve(), existing_dir.resolve())
            playlist = existing_dir / "New Month.m3u8"
            self.assertTrue(playlist.is_file())
            self.assertEqual(playlist.read_text(encoding="utf-8-sig"), "#EXTM3U\nArtist - Song.mp3\n")

    def test_year_month_folders_use_provider_release_date(self) -> None:
        class FakeDownloadManager(DownloadManager):
            def _tracks_for_payload(self, payload, allow_prepared=True):
                return [Track(title="Song", artist="Artist", released_at="2025-03-14")]

            def _download_track(self, job_id, track, output_directory, payload):
                path = output_directory / "Artist - Song.mp3"
                path.write_bytes(b"audio")
                return path

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            music = root / "music"
            manager = FakeDownloadManager(LibraryHistory(root / "history.json"))
            job = manager.create({
                "source": "text",
                "tracks": "Artist - Song",
                "output_dir": str(music),
                "rights_confirmed": True,
                "audio_format": "mp3",
                "rekordbox_playlist": True,
                "year_month_folders": True,
                "playlist_name": "March Crate",
            })
            job = self._wait_for_job(manager, job["id"])
            expected = music / "2025" / "03"
            self.assertEqual(Path(job["output_dir"]).resolve(), expected.resolve())
            self.assertTrue((expected / "Artist - Song.mp3").is_file())
            self.assertTrue((expected / "March Crate.m3u8").is_file())

    def test_year_month_folders_split_tracks_and_keep_playlist_in_today(self) -> None:
        class FakeDownloadManager(DownloadManager):
            def _tracks_for_payload(self, payload, allow_prepared=True):
                return [
                    Track(title="One", artist="A", released_at="2025-03-01"),
                    Track(title="Two", artist="B", released_at="2026-05-20"),
                ]

            def _download_track(self, job_id, track, output_directory, payload):
                path = output_directory / f"{track.artist} - {track.title}.mp3"
                path.write_bytes(b"audio")
                return path

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            music = root / "music"
            manager = FakeDownloadManager(LibraryHistory(root / "history.json"))
            job = manager.create({
                "source": "text",
                "tracks": "A - One\nB - Two",
                "output_dir": str(music),
                "rights_confirmed": True,
                "audio_format": "mp3",
                "rekordbox_playlist": True,
                "year_month_folders": True,
                "playlist_name": "Mixed",
            })
            job = self._wait_for_job(manager, job["id"])
            self.assertTrue((music / "2025" / "03" / "A - One.mp3").is_file())
            self.assertTrue((music / "2026" / "05" / "B - Two.mp3").is_file())
            today = datetime.now()
            playlist_dir = Path(job["output_dir"])
            self.assertEqual(playlist_dir, music / f"{today:%Y}" / f"{today:%m}")
            contents = (playlist_dir / "Mixed.m3u8").read_text(encoding="utf-8-sig")
            self.assertIn("2025/03/A - One.mp3", contents)
            self.assertIn("2026/05/B - Two.mp3", contents)

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
            nested = root / "2026" / "05"
            nested.mkdir(parents=True)
            (nested / "Other - New.mp3").write_bytes(b"audio")
            nested_preview = manager.preview({
                "source": "text",
                "tracks": "Artist - Song\nOther - New",
                "output_dir": str(root),
            })
            self.assertEqual(
                [track["existing"] for track in nested_preview["tracks"]],
                [True, True],
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

    def test_beatport_track_page_keeps_the_requested_mix_and_skips_recommendations(self) -> None:
        data = {
            "props": {"pageProps": {"dehydratedState": {"queries": [
                {
                    "queryKey": ["track-details-16156266"],
                    "state": {"data": {
                        "track_id": 16156266,
                        "track_name": "I Believe",
                        "mix_name": "Original Mix",
                        "track_length_ms": 435253,
                        "bpm": 126,
                        "key": {"name": "A min", "camelot": "8A"},
                        "genre": {"name": "House"},
                        "publish_date": "2016-05-20",
                        "artists": [{"name": "Happy Clappers"}],
                    }},
                },
                {
                    "queryKey": ["track-16156266-recommendations"],
                    "state": {"data": [{
                        "track_id": 999,
                        "track_name": "Unrelated Club Hit",
                        "mix_name": "Extended Mix",
                        "track_length_ms": 320000,
                        "artists": [{"name": "Someone Else"}],
                    }]},
                },
            ]}}}
        }
        tracks = _unique_tracks(_beatport_tracks_from_data(data))
        self.assertEqual(
            [(track.artist, track.title, track.duration_ms) for track in tracks],
            [("Happy Clappers", "I Believe (Original Mix)", 435253)],
        )
        self.assertEqual(
            (tracks[0].bpm, tracks[0].camelot, tracks[0].genre, tracks[0].mix_name, tracks[0].released_at),
            (126, "8A", "House", "Original Mix", "2016-05-20"),
        )

    def test_beatport_release_keeps_each_mix_and_ignores_recommended_albums(self) -> None:
        data = {
            "props": {"pageProps": {"dehydratedState": {"queries": [
                {
                    "queryKey": ["release-3629654"],
                    "state": {"data": {
                        "id": 3629654,
                        "name": "I Believe",
                        "track_count": 6,
                        "artists": [{"name": "Happy Clappers"}],
                    }},
                },
                {
                    "queryKey": ["tracks", {"release_id": 3629654, "per_page": 100, "page": 1}],
                    "state": {"data": {"results": [
                        {
                            "id": 16156270,
                            "name": "I Believe",
                            "mix_name": "The Cube Guys Edit 2016",
                            "length_ms": 322559,
                            "artists": [{"name": "Happy Clappers"}],
                        },
                        {
                            "id": 16156266,
                            "name": "I Believe",
                            "mix_name": "Original Mix",
                            "length_ms": 435253,
                            "artists": [{"name": "Happy Clappers"}],
                        },
                    ]}},
                },
                {
                    "queryKey": ["release-3629654-recommendations"],
                    "state": {"data": {"results": [{
                        "id": 1,
                        "name": "Patchwork - Extended Mix",
                        "track_count": 1,
                        "artists": [{"name": "Carlita"}],
                    }]}},
                },
            ]}}}
        }
        tracks = _unique_tracks(_beatport_tracks_from_data(data))
        self.assertEqual(
            [(track.artist, track.title) for track in tracks],
            [
                ("Happy Clappers", "I Believe (The Cube Guys Edit 2016)"),
                ("Happy Clappers", "I Believe (Original Mix)"),
            ],
        )

    def test_beatport_does_not_append_original_mix_when_title_already_names_the_remix(self) -> None:
        data = {
            "id": 19164216,
            "name": "It's That Time (FISHER Remix - Extended Mix)",
            "mix_name": "Original Mix",
            "length_ms": 238179,
            "artists": [{"name": "Marlon Hoffstadt"}],
        }
        tracks = _beatport_tracks_from_data(data)
        self.assertEqual(tracks[0].title, "It's That Time (FISHER Remix - Extended Mix)")

    def test_youtube_search_prefers_the_matching_mix_over_a_long_set(self) -> None:
        track = Track(title="I Believe (Original Mix)", artist="Happy Clappers", duration_ms=435000)
        chosen = choose_youtube_result(track, [
            {
                "title": "Happy Clappers I Believe 1 Hour Mix",
                "duration": 3600,
                "webpage_url": "https://www.youtube.com/watch?v=hour",
            },
            {
                "title": "Happy Clappers - I Believe (Radio Edit)",
                "duration": 180,
                "webpage_url": "https://www.youtube.com/watch?v=radio",
            },
            {
                "title": "Happy Clappers - I Believe (Original Mix)",
                "duration": 435,
                "webpage_url": "https://www.youtube.com/watch?v=original",
            },
        ])
        self.assertEqual(chosen["webpage_url"], "https://www.youtube.com/watch?v=original")
        self.assertEqual(track.search_query, "Happy Clappers - I Believe (Original Mix)")

    def test_youtube_search_hits_keep_watch_urls_and_duration_labels(self) -> None:
        hits = youtube_search_hits([
            {
                "title": "Happy Clappers - I Believe (Original Mix)",
                "uploader": "Ministry Vaults",
                "duration": 435,
                "webpage_url": "https://www.youtube.com/watch?v=original",
            },
            {"title": "Duplicate", "ie_key": "Youtube", "url": "original", "duration": 12},
            {"title": "Missing url"},
            {
                "title": "Radio Edit",
                "channel": "Official",
                "duration": 180,
                "url": "https://www.youtube.com/watch?v=radio",
            },
        ])
        self.assertEqual(
            [(hit["title"], hit["channel"], hit["duration_label"], hit["url"]) for hit in hits],
            [
                (
                    "Happy Clappers - I Believe (Original Mix)",
                    "Ministry Vaults",
                    "7:15",
                    "https://www.youtube.com/watch?v=original",
                ),
                ("Radio Edit", "Official", "3:00", "https://www.youtube.com/watch?v=radio"),
            ],
        )

    def test_search_requires_a_song_or_artist(self) -> None:
        with self.assertRaisesRegex(InputError, "song title or artist"):
            DownloadManager().search({"artist": "  ", "title": ""})

    def test_search_download_uses_the_chosen_video_url(self) -> None:
        seen = []

        class FakeDownloadManager(DownloadManager):
            def _download_track(self, job_id, track, output_directory, payload):
                seen.append((track.artist, track.title, track.direct_url))
                path = output_directory / f"{track.title}.{payload.get('audio_format', 'mp3')}"
                path.write_bytes(b"audio")
                return path

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manager = FakeDownloadManager(LibraryHistory(root / "history.json"))
            job = manager.create({
                "source": "search",
                "output_dir": str(root / "music"),
                "rights_confirmed": True,
                "audio_format": "mp3",
                "prepared_tracks": [{
                    "title": "Happy Clappers - I Believe (Original Mix)",
                    "direct_url": "https://www.youtube.com/watch?v=original",
                    "included": True,
                }],
            })
            job = self._wait_for_job(manager, job["id"])
            self.assertEqual(job["state"], "complete")
            self.assertEqual(
                seen,
                [("", "Happy Clappers - I Believe (Original Mix)", "https://www.youtube.com/watch?v=original")],
            )

    def test_search_saves_use_the_youtube_title_not_the_typed_query(self) -> None:
        track = Track(
            title="Happy Clappers - I Believe (Original Mix)",
            artist="typed query artist",
            direct_url="https://www.youtube.com/watch?v=original",
        )
        self.assertEqual(
            output_filename_stem(track, {"source": "search"}),
            "%(title)s",
        )
        self.assertEqual(
            output_filename_stem(
                Track(title="I Believe", artist="Happy Clappers"),
                {"source": "beatport"},
            ),
            "Happy Clappers - I Believe",
        )


if __name__ == "__main__":
    unittest.main()
