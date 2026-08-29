#!/usr/bin/env python3
"""Create a private virtual environment, then launch the local music UI."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIRECTORY = ROOT / ".music-library-venv"
REQUIREMENTS = ROOT / "requirements.txt"


def virtual_environment_python() -> Path:
    return VENV_DIRECTORY / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    if sys.version_info < (3, 9):
        print("Music Library Downloader needs Python 3.9 or newer.")
        return 1
    if not REQUIREMENTS.exists():
        print("requirements.txt is missing. Please download the complete application.")
        return 1

    python = virtual_environment_python()
    if not python.exists():
        print("First run: creating this app's private Python environment…")
        try:
            venv.EnvBuilder(with_pip=True).create(VENV_DIRECTORY)
        except (OSError, ValueError) as error:
            print(f"Could not create the private environment: {error}")
            return 1

    stamp = VENV_DIRECTORY / ".requirements.sha256"
    requirements_version = file_hash(REQUIREMENTS)
    installed_version = stamp.read_text(encoding="utf-8").strip() if stamp.exists() else ""
    if installed_version != requirements_version:
        print("First run or update: installing the app's libraries…")
        try:
            run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
            run([str(python), "-m", "pip", "install", "--upgrade", "-r", str(REQUIREMENTS)])
            stamp.write_text(requirements_version, encoding="utf-8")
        except subprocess.CalledProcessError:
            print("The app libraries could not be installed. Check your internet connection and try again.")
            return 1

    return subprocess.call([str(python), str(ROOT / "music_downloader_ui.py")], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
