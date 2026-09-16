import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from dj_styling import (
    build_dj_card,
    camelot_from_key,
    camelot_neighbors,
    extract_suggested_stems,
    prepare_dj_assets,
    preview_line,
    sidecar_path,
)


class DjStylingTests(unittest.TestCase):
    def test_camelot_maps_classic_keys_and_codes(self) -> None:
        self.assertEqual(camelot_from_key("A min"), "8A")
        self.assertEqual(camelot_from_key("Am"), "8A")
        self.assertEqual(camelot_from_key("C"), "8B")
        self.assertEqual(camelot_from_key("8a"), "8A")
        self.assertEqual(
            camelot_from_key({"name": "F# min", "camelot_number": 11, "camelot_letter": "A"}),
            "11A",
        )
        self.assertEqual(camelot_neighbors("8A"), ["7A", "9A", "8B"])

    def test_vocal_house_marks_vocal_and_drums_useful(self) -> None:
        card = build_dj_card(
            artist="Happy Clappers",
            title="I Believe (feat. The Choir)",
            bpm=126,
            musical_key="A min",
            genre="House",
            mix_name="Original Mix",
            duration_ms=435000,
            analysis_source="beatport",
        )
        self.assertEqual(card["camelot"], "8A")
        self.assertIn("vocal", card["stems"]["useful"])
        self.assertIn("drums", card["stems"]["useful"])
        self.assertIn("echo-out at 16-bar phrase ends", card["fx"]["use"])
        self.assertIn("high-pass through the vocal", card["fx"]["avoid"])
        self.assertIn("8A", preview_line(card))

    def test_techno_original_mix_prefers_drums_and_dry_kick(self) -> None:
        card = build_dj_card(
            title="Warehouse Tool",
            genre="Peak Time Techno",
            mix_name="Original Mix",
            duration_ms=360000,
        )
        self.assertNotIn("vocal", card["stems"]["useful"])
        self.assertIn("drums", card["stems"]["useful"])
        self.assertIn("long reverb on the kick", card["fx"]["avoid"])

    def test_sidecar_and_suggested_stem_wavs_are_written(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            audio = root / "Artist - Song.mp3"
            audio.write_bytes(b"audio")

            def runner(args):
                output = Path(args[args.index("-o") + 1]) / "htdemucs" / "Song"
                output.mkdir(parents=True)
                (output / "vocals.wav").write_bytes(b"vocal")
                (output / "drums.wav").write_bytes(b"drums")
                (output / "bass.wav").write_bytes(b"bass")
                return SimpleNamespace(returncode=0)

            card = prepare_dj_assets(
                audio,
                artist="Happy Clappers",
                title="I Believe (feat. Choir)",
                bpm=126,
                musical_key="A min",
                genre="House",
                mix_name="Original Mix",
                extract_stems=True,
                analyzer=lambda _path: {},
                stem_runner=runner,
                stem_command=["demucs"],
            )
            sidecar = sidecar_path(audio)
            self.assertTrue(sidecar.is_file())
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(payload["camelot"], "8A")
            self.assertEqual(set(card["stems"]["extracted"]), {"vocal", "drums"})
            self.assertTrue((root / "Artist - Song.stems" / "vocal.wav").is_file())
            self.assertTrue((root / "Artist - Song.stems" / "drums.wav").is_file())
            self.assertFalse((root / "Artist - Song.stems" / "bass.wav").is_file())

    def test_extract_skips_stems_not_marked_useful(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            audio = Path(temporary_directory) / "track.mp3"
            audio.write_bytes(b"audio")

            def runner(args):
                output = Path(args[args.index("-o") + 1]) / "htdemucs" / "track"
                output.mkdir(parents=True)
                (output / "vocals.wav").write_bytes(b"vocal")
                (output / "drums.wav").write_bytes(b"drums")
                return SimpleNamespace(returncode=0)

            extracted = extract_suggested_stems(
                audio,
                ["vocal"],
                runner=runner,
                command=["demucs"],
            )
            self.assertEqual(set(extracted), {"vocal"})
            self.assertTrue((audio.parent / "track.stems" / "vocal.wav").is_file())
            self.assertFalse((audio.parent / "track.stems" / "drums.wav").is_file())


if __name__ == "__main__":
    unittest.main()
