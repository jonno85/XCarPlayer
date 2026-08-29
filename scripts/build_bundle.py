"""Build a self-contained desktop bundle for the current operating system."""

from __future__ import annotations

import platform
import shutil
from pathlib import Path

import PyInstaller.__main__


ROOT = Path(__file__).resolve().parents[1]
separator = ";" if platform.system() == "Windows" else ":"

PyInstaller.__main__.run(
    [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "MusicLibraryDownloader",
        f"--specpath={ROOT / 'build'}",
        f"--add-data={ROOT / 'web'}{separator}web",
        str(ROOT / "music_downloader_ui.py"),
    ]
)

bundle_name = "MusicLibraryDownloader.app" if platform.system() == "Darwin" else "MusicLibraryDownloader"
archive_stem = ROOT / "dist" / f"MusicLibraryDownloader-{platform.system().lower()}"
shutil.make_archive(str(archive_stem), "zip", ROOT / "dist", bundle_name)
