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
        f"--workpath={ROOT / 'build' / 'work'}",
        f"--distpath={ROOT / 'dist'}",
        f"--add-data={ROOT / 'web'}{separator}web",
        str(ROOT / "music_downloader_ui.py"),
    ]
)

bundle_name = "MusicLibraryDownloader.app" if platform.system() == "Darwin" else "MusicLibraryDownloader"
archive_stem = ROOT / "dist" / f"MusicLibraryDownloader-{platform.system().lower()}"
if platform.system() == "Darwin":
    staging = ROOT / "dist" / "macos-zip"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copytree(ROOT / "dist" / bundle_name, staging / bundle_name, symlinks=True)
    helper = staging / "Open If Blocked.command"
    helper.write_text(
        "#!/bin/bash\n"
        'cd "$(dirname "$0")"\n'
        'xattr -cr "MusicLibraryDownloader.app"\n'
        'open "MusicLibraryDownloader.app"\n',
        encoding="utf-8",
    )
    helper.chmod(0o755)
    shutil.make_archive(str(archive_stem), "zip", staging)
else:
    shutil.make_archive(str(archive_stem), "zip", ROOT / "dist", bundle_name)
