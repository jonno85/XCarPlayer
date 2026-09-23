"""DJ sidecar hints for Rekordbox.

Direction: write a .dj.json sidecar and show the same hints in preview.
Optionally export WAV stems only for parts marked useful (vocal and/or drums).
Rekordbox loads those WAVs as normal tracks, not as native STEMS. Native STEMS
still run in Rekordbox Performance mode on the mixed file.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence


SIDECAR_VERSION = 1
USEFUL_STEMS = ("vocal", "drums")
REKORDBOX_STEM_NOTE = (
    "Import extracted WAVs as normal tracks (third deck, sampler, or USB). "
    "Rekordbox native STEMS still separate the mixed file in Performance mode "
    "and do not ingest these WAVs."
)

_CAMELOT_RE = re.compile(r"^(1[0-2]|[1-9])\s*([AB])$", re.I)

# Camelot wheel, Open Key / harmonic mixing.
_MAJOR_TO_CAMELOT = {
    "b": "1B",
    "f#": "2B",
    "gb": "2B",
    "c#": "3B",
    "db": "3B",
    "g#": "4B",
    "ab": "4B",
    "d#": "5B",
    "eb": "5B",
    "a#": "6B",
    "bb": "6B",
    "f": "7B",
    "c": "8B",
    "g": "9B",
    "d": "10B",
    "a": "11B",
    "e": "12B",
}
_MINOR_TO_CAMELOT = {
    "g#": "1A",
    "ab": "1A",
    "d#": "2A",
    "eb": "2A",
    "a#": "3A",
    "bb": "3A",
    "f": "4A",
    "c": "5A",
    "g": "6A",
    "d": "7A",
    "a": "8A",
    "e": "9A",
    "b": "10A",
    "f#": "11A",
    "gb": "11A",
    "c#": "12A",
    "db": "12A",
}

_VOCAL_TITLE = re.compile(
    r"\b(vocal|vocals|a\s*c+a+p+ellas?|feat\.?|ft\.|featuring)\b",
    re.I,
)
_ACAPELLA_TITLE = re.compile(r"\b(?:a\s*c+a+p+ellas?|house-apella)\b", re.I)
_INSTRUMENTAL_TITLE = re.compile(r"\b(instrumental|inst\.? mix|karaoke)\b", re.I)
_EXTENDED_TITLE = re.compile(
    r"\b(extended|original mix|club mix|dj mix|dub mix)\b",
    re.I,
)
_RADIO_TITLE = re.compile(r"\b(radio edit|radio mix|short edit|cut edit)\b", re.I)
_SET_TITLE = re.compile(
    r"\b(dj set|full set|live at|live from|hour mix|continuous mix|megamix|compilation)\b",
    re.I,
)

_VOCAL_GENRES = (
    "vocal",
    "pop",
    "open format",
    "r&b",
    "rnb",
    "soul",
    "disco",
    "funky house",
    "nu disco",
    "afro house",
    "mainstage",
    "dance",
)
_GROOVE_GENRES = (
    "house",
    "techno",
    "tech house",
    "trance",
    "drum",
    "bass",
    "garage",
    "breaks",
    "breakbeat",
    "jungle",
    "hard dance",
    "hardstyle",
    "progressive",
)
_DRY_KICK_GENRES = ("techno", "tech house", "drum", "jungle", "hardstyle", "hard dance")
_FILTER_GENRES = ("techno", "tech house", "progressive", "trance", "melodic")


Runner = Callable[[List[str]], subprocess.CompletedProcess]


class StemExtractError(RuntimeError):
    """Demucs or FFmpeg could not produce the requested stem WAV."""


def camelot_from_key(value: Any) -> str:
    """Map a catalog key string such as 'A min' or '8A' to Camelot notation."""
    if isinstance(value, dict):
        number = value.get("camelot_number") or value.get("number")
        letter = value.get("camelot_letter") or value.get("letter")
        if number and letter:
            compact = f"{number}{letter}"
            parsed = camelot_from_key(compact)
            if parsed:
                return parsed
        for key in ("camelot", "name", "standard", "short_name"):
            parsed = camelot_from_key(value.get(key))
            if parsed:
                return parsed
        return ""
    text = str(value or "").strip()
    if not text:
        return ""
    compact = re.sub(r"\s+", "", text)
    match = _CAMELOT_RE.match(compact)
    if match:
        return f"{int(match.group(1))}{match.group(2).upper()}"
    folded = text.casefold().replace("major", "maj").replace("minor", "min")
    folded = folded.replace("moll", "min").replace("dur", "maj")
    folded = folded.replace(":", " ").replace("-", " ")
    folded = re.sub(r"\s+", " ", folded).strip()
    tokens = folded.split()
    if not tokens:
        return ""
    note = tokens[0].replace("♯", "#").replace("♭", "b")
    note = note.replace("sharp", "#").replace("flat", "b")
    is_minor = False
    remainder = " ".join(tokens[1:])
    if note.endswith("min") and len(note) > 3:
        is_minor = True
        note = note[:-3]
    elif note.endswith("m") and not note.endswith("maj") and len(note) <= 3:
        is_minor = True
        note = note[:-1]
    elif "min" in remainder or remainder == "m":
        is_minor = True
    elif "maj" in remainder:
        is_minor = False
    table = _MINOR_TO_CAMELOT if is_minor else _MAJOR_TO_CAMELOT
    return table.get(note, "")


# Classic notation Rekordbox stores in TKEY and can display as Camelot.
_REKORDBOX_KEY = {
    "1A": "G#m",
    "2A": "D#m",
    "3A": "A#m",
    "4A": "Fm",
    "5A": "Cm",
    "6A": "Gm",
    "7A": "Dm",
    "8A": "Am",
    "9A": "Em",
    "10A": "Bm",
    "11A": "F#m",
    "12A": "C#m",
    "1B": "B",
    "2B": "F#",
    "3B": "C#",
    "4B": "G#",
    "5B": "D#",
    "6B": "A#",
    "7B": "F",
    "8B": "C",
    "9B": "G",
    "10B": "D",
    "11B": "A",
    "12B": "E",
}


def rekordbox_key(value: Any = "", camelot: str = "") -> str:
    """Return the classic key Rekordbox reads from TKEY, such as 'Am' or 'F#'."""
    code = camelot_from_key(camelot) or camelot_from_key(value)
    return _REKORDBOX_KEY.get(code, "")


def camelot_neighbors(code: str) -> List[str]:
    """Harmonic mixing neighbours: ±1 same mode, and relative major/minor."""
    parsed = camelot_from_key(code)
    if not parsed:
        return []
    number = int(parsed[:-1])
    letter = parsed[-1]
    other = "B" if letter == "A" else "A"
    previous_number = 12 if number == 1 else number - 1
    next_number = 1 if number == 12 else number + 1
    return [f"{previous_number}{letter}", f"{next_number}{letter}", f"{number}{other}"]


def sidecar_path(audio_path: Path) -> Path:
    return audio_path.with_name(f"{audio_path.stem}.dj.json")


def stems_directory(audio_path: Path) -> Path:
    return audio_path.with_name(f"{audio_path.stem}.stems")


def build_dj_card(
    *,
    artist: str = "",
    title: str = "",
    bpm: int = 0,
    musical_key: str = "",
    camelot: str = "",
    genre: str = "",
    mix_name: str = "",
    duration_ms: int = 0,
    analysis_source: str = "",
) -> Dict[str, Any]:
    """Rule-based FX / STEM hints from catalog fields and the track title."""
    camelot_code = camelot_from_key(camelot) or camelot_from_key(musical_key)
    blob = " ".join(part for part in (title, mix_name, genre) if part)
    vocal_likely = bool(_VOCAL_TITLE.search(blob) or _genre_match(genre, _VOCAL_GENRES))
    instrumental = bool(_INSTRUMENTAL_TITLE.search(blob))
    acapella = _is_acapella(title, mix_name, genre)
    extended = bool(_EXTENDED_TITLE.search(blob)) and not acapella
    radio = bool(_RADIO_TITLE.search(blob))
    live_set = bool(_SET_TITLE.search(blob) or duration_ms >= 15 * 60 * 1000)
    groove = bool(_genre_match(genre, _GROOVE_GENRES) or extended)

    useful: List[str] = []
    skip: List[str] = ["bass"]
    if live_set:
        skip.extend(["vocal", "drums"])
        stem_reason = "Long sets are a poor source for isolated stems."
    elif acapella:
        useful.append("vocal")
        skip.append("drums")
        stem_reason = "This file is already a vocal/acapella; the WAV is a copy for Rekordbox."
    else:
        if vocal_likely and not instrumental:
            useful.append("vocal")
        else:
            skip.append("vocal")
        if groove and not radio:
            useful.append("drums")
        else:
            skip.append("drums")
        if "vocal" in useful and "drums" in useful:
            stem_reason = "Vocal and drums are the parts worth loading as extra Rekordbox tracks."
        elif "vocal" in useful:
            stem_reason = "A separate vocal WAV is useful for acapella swaps and echo-outs."
        elif "drums" in useful:
            stem_reason = "A separate drums WAV is useful for loops, Groove Circuit, or a third deck."
        else:
            stem_reason = "No extra stem file is likely to help this mix."

    fx_use, fx_avoid = _fx_playbook(genre, vocal_likely and not instrumental, radio, extended)
    hints = _extra_hints(extended, radio, live_set, duration_ms, camelot_code)

    return {
        "version": SIDECAR_VERSION,
        "artist": artist,
        "title": title,
        "bpm": bpm or None,
        "key": musical_key or None,
        "camelot": camelot_code or None,
        "camelot_neighbors": camelot_neighbors(camelot_code),
        "genre": genre or None,
        "mix_name": mix_name or None,
        "duration_ms": duration_ms or None,
        "analysis_source": analysis_source or None,
        "fx": {"use": fx_use, "avoid": fx_avoid},
        "stems": {
            "useful": useful,
            "skip": _unique_keep_order(skip),
            "reason": stem_reason,
            "rekordbox_note": REKORDBOX_STEM_NOTE,
            "extracted": {},
        },
        "hints": hints,
    }


def preview_line(card: Dict[str, Any]) -> str:
    """One-line preview for the desktop UI."""
    parts: List[str] = []
    if card.get("camelot"):
        parts.append(str(card["camelot"]))
    if card.get("bpm"):
        parts.append(f"{card['bpm']} BPM")
    if card.get("genre"):
        parts.append(str(card["genre"]))
    useful = card.get("stems", {}).get("useful") or []
    if useful:
        parts.append("stems: " + ", ".join(useful))
    fx_use = (card.get("fx") or {}).get("use") or []
    fx_avoid = (card.get("fx") or {}).get("avoid") or []
    if fx_use:
        parts.append("use " + fx_use[0])
    if fx_avoid:
        parts.append("avoid " + fx_avoid[0])
    if not parts:
        parts.extend(card.get("hints") or ["DJ hints will be written next to the file"])
    return " · ".join(parts)


def write_sidecar(audio_path: Path, card: Dict[str, Any]) -> Path:
    path = sidecar_path(audio_path)
    path.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def demucs_command() -> Optional[List[str]]:
    """Return a Demucs invocation if the optional stem tool is installed."""
    located = shutil.which("demucs")
    if located:
        return [located]
    try:
        import demucs  # noqa: F401
    except ImportError:
        return None
    return [sys.executable, "-m", "demucs"]


def extract_suggested_stems(
    audio_path: Path,
    useful: Sequence[str],
    *,
    runner: Optional[Runner] = None,
    command: Optional[Sequence[str]] = None,
) -> Dict[str, str]:
    """Export only vocal and/or drums WAVs that the hint marked useful."""
    wanted = [stem for stem in useful if stem in USEFUL_STEMS]
    if not wanted or not audio_path.is_file():
        return {}
    invocation = list(command or demucs_command() or [])
    if not invocation:
        return {}
    run = runner or (
        lambda args: subprocess.run(args, check=False, capture_output=True, text=True)
    )
    destination = stems_directory(audio_path)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dj-stems-") as temporary:
        work = Path(temporary)
        command_args = [*invocation, "-n", "htdemucs", "-o", str(work)]
        if wanted == ["vocal"]:
            command_args.extend(["--two-stems", "vocals"])
        command_args.append(str(audio_path))
        result = run(command_args)
        if getattr(result, "returncode", 1):
            detail = _one_line_error(getattr(result, "stderr", "") or getattr(result, "stdout", ""))
            raise StemExtractError(detail or "Demucs exited with an error.")
        extracted: Dict[str, str] = {}
        mapping = {"vocal": "vocals.wav", "drums": "drums.wav"}
        for stem in wanted:
            found = _find_named_wav(work, mapping[stem])
            if found is None:
                found = _find_named_wav(work, mapping[stem].replace(".wav", ".mp3"))
            if found is None:
                continue
            target = destination / f"{stem}.wav"
            shutil.copy2(found, target)
            extracted[stem] = str(target)
        if not extracted:
            raise StemExtractError("Demucs finished but did not write vocals.wav or drums.wav.")
        return extracted


def prepare_dj_assets(
    audio_path: Path,
    *,
    artist: str = "",
    title: str = "",
    bpm: int = 0,
    musical_key: str = "",
    camelot: str = "",
    genre: str = "",
    mix_name: str = "",
    duration_ms: int = 0,
    analysis_source: str = "",
    extract_stems: bool = False,
    analyzer: Optional[Callable[[Path], Dict[str, Any]]] = None,
    stem_runner: Optional[Runner] = None,
    stem_command: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Write the sidecar, optionally fill missing BPM/key, optionally extract WAVs."""
    source = analysis_source
    if (not bpm or not (camelot or musical_key)) and audio_path.is_file():
        estimate = (analyzer or estimate_bpm_and_key)(audio_path)
        bpm = bpm or int(estimate.get("bpm") or 0)
        musical_key = musical_key or str(estimate.get("key") or "")
        if estimate.get("bpm") or estimate.get("key"):
            source = source or str(estimate.get("analysis_source") or "audio")
    source = source or ("catalog" if bpm or musical_key or genre else "heuristics")
    card = build_dj_card(
        artist=artist,
        title=title,
        bpm=bpm,
        musical_key=musical_key,
        camelot=camelot,
        genre=genre,
        mix_name=mix_name,
        duration_ms=duration_ms,
        analysis_source=source,
    )
    extracted: Dict[str, str] = {}
    skipped = ""
    if extract_stems:
        useful = card["stems"]["useful"]
        try:
            if not useful:
                skipped = "No vocal or drums stem was marked useful."
            elif _is_acapella(title, mix_name, genre):
                extracted = export_existing_vocal(audio_path)
            elif not (stem_command or demucs_command()):
                skipped = "Demucs is not installed; sidecar hints were still written."
            else:
                extracted = extract_suggested_stems(
                    audio_path,
                    useful,
                    runner=stem_runner,
                    command=stem_command,
                )
        except StemExtractError as error:
            skipped = str(error)
    card["stems"]["extracted"] = extracted
    if skipped:
        card["stems"]["skipped_reason"] = skipped
    sidecar = write_sidecar(audio_path, card)
    card["sidecar_path"] = str(sidecar)
    return card


def estimate_bpm_and_key(audio_path: Path) -> Dict[str, Any]:
    """Best-effort BPM/key from the saved file when catalog metadata is missing."""
    try:
        import librosa
        import numpy as np
    except ImportError:
        return {}
    try:
        samples, sample_rate = librosa.load(str(audio_path), sr=22050, mono=True, duration=90)
        tempo = float(librosa.feature.tempo(y=samples, sr=sample_rate)[0])
        chroma = np.mean(librosa.feature.chroma_cqt(y=samples, sr=sample_rate), axis=1)
    except Exception:
        return {}
    key_name = _key_from_chroma(chroma)
    bpm = int(round(tempo))
    if bpm < 60 or bpm > 220:
        return {"key": key_name, "analysis_source": "audio"} if key_name else {}
    return {"bpm": bpm, "key": key_name, "analysis_source": "audio"}


def _key_from_chroma(chroma: Any) -> str:
    try:
        import numpy as np
    except ImportError:
        return ""
    major = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
    minor = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    vector = np.asarray(chroma, dtype=float)
    if vector.shape[0] != 12 or not np.any(vector):
        return ""
    best_score = float("-inf")
    best = ""
    for shift in range(12):
        rolled = np.roll(vector, -shift)
        major_score = float(np.dot(rolled, major))
        minor_score = float(np.dot(rolled, minor))
        if major_score > best_score:
            best_score = major_score
            best = f"{names[shift]} maj"
        if minor_score > best_score:
            best_score = minor_score
            best = f"{names[shift]} min"
    return best


def _fx_playbook(genre: str, has_vocal: bool, radio: bool, extended: bool) -> tuple:
    use: List[str] = []
    avoid: List[str] = []
    if has_vocal:
        use.append("echo-out at 16-bar phrase ends")
        avoid.append("high-pass through the vocal")
    if _genre_match(genre, _FILTER_GENRES) or extended:
        use.append("filter / EQ for mix-in and mix-out")
    if _genre_match(genre, _DRY_KICK_GENRES):
        avoid.append("long reverb on the kick")
        use.append("short delay on hats or percussion")
    if _genre_match(genre, ("trance", "progressive", "melodic")):
        use.append("uplifters or gated reverb into the drop")
        avoid.append("bitcrush or heavy distortion on the lead")
    if radio:
        avoid.append("long filter-in — the intro is too short")
        use.append("enter after the first chorus or drop")
    if not use:
        use.append("phrase-aligned echo or filter, then return dry")
    if not avoid:
        avoid.append("stacking several send FX at once")
    return use[:3], avoid[:3]


def _extra_hints(
    extended: bool,
    radio: bool,
    live_set: bool,
    duration_ms: int,
    camelot: str,
) -> List[str]:
    hints: List[str] = []
    if camelot:
        neighbors = ", ".join(camelot_neighbors(camelot))
        hints.append(f"Harmonic neighbours: {neighbors}")
    if extended and not radio:
        hints.append("Extended/original mix: longer intro and outro for EQ blends")
    if radio:
        hints.append("Radio edit: mix later in the track; hot-cue the drop")
    if live_set:
        hints.append("This looks like a set or long mix, not a single to stem")
    elif duration_ms and duration_ms < 3 * 60 * 1000:
        hints.append("Short runtime: expect a tight intro")
    return hints


def _is_acapella(title: str, mix_name: str, genre: str) -> bool:
    blob = " ".join(part for part in (title, mix_name) if part)
    return bool(_ACAPELLA_TITLE.search(blob))


def export_existing_vocal(audio_path: Path) -> Dict[str, str]:
    """Copy or convert an acapella to a Rekordbox-importable vocal WAV."""
    destination = stems_directory(audio_path)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "vocal.wav"
    if audio_path.suffix.casefold() == ".wav":
        shutil.copy2(audio_path, target)
        return {"vocal": str(target)}
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        raise StemExtractError("FFmpeg is needed to write a WAV copy of this acapella.")
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(audio_path), "-vn", "-acodec", "pcm_s16le", str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or not target.is_file():
        raise StemExtractError(
            _one_line_error(result.stderr or result.stdout) or "Could not convert the acapella to WAV."
        )
    return {"vocal": str(target)}


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
    except ImportError:
        return shutil.which("ffmpeg") or ""
    try:
        return str(imageio_ffmpeg.get_ffmpeg_exe() or "")
    except Exception:
        return shutil.which("ffmpeg") or ""


def _one_line_error(text: str) -> str:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    for line in reversed(lines):
        folded = line.casefold()
        if "error" in folded or "modulenotfound" in folded:
            return line[:300]
    return (lines[-1] if lines else "")[:300]


def _genre_match(genre: str, needles: Iterable[str]) -> bool:
    folded = genre.casefold()
    return any(needle in folded for needle in needles)


def _unique_keep_order(values: Iterable[str]) -> List[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _find_named_wav(root: Path, filename: str) -> Optional[Path]:
    matches = list(root.rglob(filename))
    return matches[0] if matches else None
