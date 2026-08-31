#!/usr/bin/env sh
# Start Music Library Downloader on macOS or Linux.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  printf '%s\n' "Python 3.9+ is needed once to start this app: https://www.python.org/downloads/"
  exit 1
fi

exec "$PYTHON" "$ROOT/launch.py"
