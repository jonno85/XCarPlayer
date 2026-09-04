# Music Library Downloader

A simple local browser UI for collecting permitted music into a consistent audio library.

It accepts:

- a YouTube song or playlist link;
- a public Spotify track or playlist link;
- a public Beatport track or playlist link; or
- a `.txt` file (or pasted list), with one song per line.

Spotify and Beatport links are used to read public track metadata only. Each listed track is then matched against YouTube and saved in the selected format with embedded title and artist metadata. This creates a consistent local library without attempting to access streaming-service audio.

The interface is available in English and Italian. It also includes a native destination-folder picker, download history, pause and stop for in-progress jobs, in-app play/pause controls, duplicate highlighting, and selectable MP3, M4A, FLAC, WAV, or Opus output.

## Start it

### No-install release

GitHub Releases can contain self-contained Windows, macOS, and Linux bundles built by the included workflow. Download the bundle for the operating system, unpack it, and run `MusicLibraryDownloader` (or `MusicLibraryDownloader.exe` on Windows). Python and app libraries are bundled.

### Run from the repository

This path needs Python 3.9+ installed once. The launcher automatically creates a private `.music-library-venv` and installs or updates all app libraries; nothing is installed into the system Python.

From the repository root, first enter this project:

```sh
cd desktop-downloader
```

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
4. Confirm you have the right or permission to download the tracks, then start. Pause or stop from the download status panel if you need to wait or cancel remaining tracks.

Spotify public tracks and playlists are read from their public embed pages. No Spotify login, Premium subscription, Client ID, or Client Secret is required. Preview the extracted tracks before downloading so titles can be corrected or excluded. Private playlists are not available through this method.

If Spotify changes or blocks its public page, export the playlist as TXT or CSV and choose **Or import exporter TXT/CSV**. Artist/title columns are detected automatically; plain text should contain one `Artist - Title` entry per line.

If YouTube asks you to sign in or confirms that you are not a bot, expand **Only if YouTube asks you to sign in** and choose the browser where you are already signed in. The downloader reads that browser’s local cookies only for the requested download; it never uploads or saves them.

The default folder and update preference are stored in the operating system’s per-user configuration location, not in this repository.

On Linux the native folder button uses `zenity` (GNOME and related desktops) or `kdialog` (KDE). Install either utility if the desktop image does not already include one. Windows and macOS use their built-in folder dialogs.

## Rekordbox workflow

Use the local music folder as the source of truth and let Rekordbox reference it:

1. Choose a stable folder that will not be renamed or moved.
2. In **Audio format & Rekordbox options**, use MP3 320 kbps for the widest Pioneer/CDJ compatibility. M4A and FLAC are suitable only after checking the target player model.
3. Enable **Create a Rekordbox-compatible .m3u8 playlist** and import that playlist into Rekordbox.
4. Let Rekordbox analyze BPM, waveform, key, beatgrid, and cues, then use Rekordbox’s own Device Library export for USB media.
5. Use **Compare folder** to identify files that are in the folder but not in this app’s history. It is deliberately a read-only diff: it never moves or deletes music.

Do not perform an automatic two-way file sync against Rekordbox’s database. Rekordbox owns cue points, beatgrids, analysis, and device-export state; moving or deleting files behind it creates missing-track references. If the library must live on two computers, sync the stable audio folder one way and relocate missing files from inside Rekordbox.

FLAC and WAV output are lossless containers, but transcoding a lossy YouTube source cannot restore information already removed from that source.

## Updates

When run from a clean Git checkout, **Check for updates** compares the current branch with `origin` and can apply a fast-forward update. Restart the app afterward so its isolated environment can install any new libraries.

Packaged or ZIP copies cannot safely rewrite themselves. The same button checks GitHub Releases and links to the latest release when one is available.

## Publish no-install bundles

The repository workflow at `../.github/workflows/build-desktop.yml` creates Windows, macOS, and Linux artifacts with PyInstaller. Publishing a GitHub Release attaches the matching bundles automatically; tag that release with the same version as `APP_VERSION` in `music_downloader_core.py`. A manually dispatched workflow keeps bundles as downloadable workflow artifacts.

## Important use note

Only download audio you own, are licensed to download, or otherwise have permission to save. Service availability and matching quality depend on the source pages and YouTube results; review output files before relying on them for a curated library.

## Development checks

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile launch.py music_downloader_core.py music_downloader_ui.py
```
