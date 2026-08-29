import tempfile
import unittest
from pathlib import Path

from music_downloader_core import (
    ConfigStore,
    DownloadManager,
    InputError,
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
            self.assertEqual(store.load(), saved)

    def test_download_requires_rights_confirmation_before_starting_worker(self) -> None:
        with self.assertRaisesRegex(InputError, "rights or permission"):
            DownloadManager().create({
                "source": "text",
                "tracks": "Artist - Title",
                "output_dir": "/tmp/library",
                "rights_confirmed": False,
            })


if __name__ == "__main__":
    unittest.main()
