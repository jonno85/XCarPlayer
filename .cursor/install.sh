#!/usr/bin/env bash
# Idempotent bootstrap for every project in the XCarPlayer repository.
# Safe to run repeatedly: each step recreates only what is missing or stale.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Installing system packages (python venv/pip, native folder pickers)"
# Debian/Ubuntu slim images ship a Python without ensurepip/venv. Install it so
# every project can build an isolated virtual environment. zenity is the native
# folder picker the desktop app uses on Linux (optional but recommended).
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip ffmpeg zenity

# Create or refresh a Python virtual environment, then install requirements.
# $1 = project directory, $2 = venv directory name, $3 = requirements file.
setup_python_project() {
  local project_dir="$1" venv_name="$2" requirements="$3"
  echo "==> Python setup: ${project_dir} (${venv_name})"
  (
    cd "$ROOT/$project_dir"
    if [ ! -x "${venv_name}/bin/python" ]; then
      python3 -m venv "$venv_name"
    fi
    "${venv_name}/bin/python" -m pip install --upgrade pip --quiet
    "${venv_name}/bin/python" -m pip install --quiet -r "$requirements"
  )
}

setup_python_project "desktop-downloader" ".music-library-venv" "requirements.txt"
setup_python_project "synology-downloader" ".venv" "requirements.txt"
# Root-level legacy copy of the desktop app (kept runnable for its tests).
setup_python_project "." ".music-library-venv" "requirements.txt"

echo "==> Python setup: cli-downloader (env)"
(
  cd "$ROOT/cli-downloader"
  if [ ! -x "env/bin/python" ]; then
    python3 -m venv env
  fi
  env/bin/python -m pip install --upgrade pip --quiet
  env/bin/python -m pip install --quiet spotdl spotipy yt-dlp requests beautifulsoup4
)

echo "==> Synology downloader runtime config (.env, music dir)"
# The FastAPI service refuses to start without API_KEY and needs a writable
# MUSIC_DIR. .env is gitignored, so generate a local development copy if absent.
if [ ! -f "$ROOT/synology-downloader/.env" ]; then
  cat > "$ROOT/synology-downloader/.env" <<'ENV'
API_KEY=dev-local-key
MUSIC_DIR=/tmp/xcar-music
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
ENV
fi
mkdir -p /tmp/xcar-music

echo "==> Mobile app setup (Yarn 4 via corepack, immutable install)"
(
  cd "$ROOT/mobile-app"
  corepack enable
  corepack prepare yarn@4.9.2 --activate
  COREPACK_ENABLE_DOWNLOAD_PROMPT=0 yarn install --immutable
)

echo "==> Bootstrap complete."
