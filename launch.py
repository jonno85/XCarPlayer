#!/usr/bin/env python3
"""Create a private virtual environment, then launch the local music UI."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parent
VENV_DIRECTORY = ROOT / ".music-library-venv"
BOOTSTRAP_DIRECTORY = ROOT / ".music-library-bootstrap"
REQUIREMENTS = ROOT / "requirements.txt"


def virtual_environment_python() -> Path:
    return VENV_DIRECTORY / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], environment: Optional[Dict[str, str]] = None) -> None:
    subprocess.run(command, cwd=ROOT, check=True, env=environment)


def has_pip(python: Path) -> bool:
    try:
        subprocess.run(
            [str(python), "-m", "pip", "--version"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def create_environment() -> bool:
    """Create the private environment, with a local fallback for minimal Linux Python."""
    print("First run: creating this app's private Python environment…")
    try:
        venv.EnvBuilder(with_pip=True).create(VENV_DIRECTORY)
        return True
    except (OSError, ValueError, subprocess.CalledProcessError, SystemExit):
        # Debian's slim Python omits ensurepip. Bootstrap virtualenv locally so no
        # system package or administrator access is needed.
        print("Using a local environment bootstrapper…")
        try:
            run([
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--target",
                str(BOOTSTRAP_DIRECTORY),
                "virtualenv",
            ])
            environment = os.environ.copy()
            existing_path = environment.get("PYTHONPATH", "")
            environment["PYTHONPATH"] = str(BOOTSTRAP_DIRECTORY) + (
                os.pathsep + existing_path if existing_path else ""
            )
            run(
                [sys.executable, "-m", "virtualenv", "--clear", str(VENV_DIRECTORY)],
                environment,
            )
            return True
        except (OSError, subprocess.CalledProcessError):
            print("The private environment could not be created. Check your internet connection and try again.")
            return False


def main() -> int:
    if sys.version_info < (3, 9):
        print("Music Library Downloader needs Python 3.9 or newer.")
        return 1
    if not REQUIREMENTS.exists():
        print("requirements.txt is missing. Please download the complete application.")
        return 1

    python = virtual_environment_python()
    if python.exists() and not has_pip(python):
        shutil.rmtree(VENV_DIRECTORY, ignore_errors=True)
    if not python.exists() and not create_environment():
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

    process = subprocess.Popen([str(python), str(ROOT / "music_downloader_ui.py")], cwd=ROOT)
    try:
        return process.wait()
    except KeyboardInterrupt:
        # Ctrl+C reaches the server too; suppress the parent-process traceback.
        if process.poll() is None:
            process.terminate()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
