# Music Library Downloader

A simple local browser UI for collecting permitted music into a consistent MP3 library.

It accepts:

- a YouTube song or playlist link;
- a public Spotify track or playlist link;
- a public Beatport track or playlist link; or
- a `.txt` file (or pasted list), with one song per line.

Spotify and Beatport links are used to read public track metadata only. Each listed track is then matched against YouTube and saved as an MP3 with embedded title and artist metadata. This keeps the local library in one format rather than attempting to access streaming-service audio.

## Start it

### No-install release

GitHub Releases can contain self-contained Windows, macOS, and Linux bundles built by the included workflow. Download the bundle for the operating system, unpack it, and run `MusicLibraryDownloader` (or `MusicLibraryDownloader.exe` on Windows). Python and app libraries are bundled.

### Run from the repository

This path needs Python 3.9+ installed once. The launcher automatically creates a private `.music-library-venv` and installs or updates all app libraries; nothing is installed into the system Python.

| Operating system | Start command |
| --- | --- |
| Windows | Double-click `launch.bat` |
| macOS / Linux | `./launch.sh` |
| Any | `python3 launch.py` |

On macOS/Linux, make the launcher executable once if needed:

```sh
chmod +x launch.sh
./launch.sh
```

The app opens at a random `127.0.0.1` address in the default browser. It only listens on the local computer. Keep the launcher terminal open while a download is running.

## First use

1. Pick YouTube, Spotify, Beatport, or **Song list**.
2. Paste the URL, choose a `.txt` file, or paste one song per line.
3. Choose a music folder and optionally save it as the default.
4. Confirm you have the right or permission to download the tracks, then start.

For Spotify, create a free application at [Spotify for Developers](https://developer.spotify.com/dashboard) and paste its Client ID and Client Secret into the UI. They are used only for that download and are not stored.

If YouTube asks you to sign in or confirms that you are not a bot, expand **Only if YouTube asks you to sign in** and choose the browser where you are already signed in. The downloader reads that browser’s local cookies only for the requested download; it never uploads or saves them.

The default folder and update preference are stored in the operating system’s per-user configuration location, not in this repository.

## Updates

When run from a clean Git checkout, **Check for updates** compares the current branch with `origin` and can apply a fast-forward update. Restart the app afterward so its isolated environment can install any new libraries.

Packaged or ZIP copies cannot safely rewrite themselves. The same button checks GitHub Releases and links to the latest release when one is available.

## Publish no-install bundles

The GitHub Actions workflow at `.github/workflows/build-desktop.yml` creates Windows, macOS, and Linux artifacts with PyInstaller. Publishing a GitHub Release attaches the matching bundles automatically; tag that release with the same version as `APP_VERSION` in `music_downloader_core.py`. A manually dispatched workflow keeps bundles as downloadable workflow artifacts.

## Important use note

Only download audio you own, are licensed to download, or otherwise have permission to save. Service availability and matching quality depend on the source pages and YouTube results; review output files before relying on them for a curated library.

## Development checks

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile launch.py music_downloader_core.py music_downloader_ui.py
```
