# XCarPlayer projects

This repository contains four related but independently runnable projects:

| Project | Directory | Purpose |
| --- | --- | --- |
| Mobile app | [`mobile-app/`](mobile-app/) | React Native/Expo player and controller for X Car Audio |
| Synology downloader | [`synology-downloader/`](synology-downloader/) | Dockerized FastAPI download service for a Synology NAS |
| CLI downloader | [`cli-downloader/`](cli-downloader/) | Legacy interactive Python download scripts |
| Desktop downloader | [`desktop-downloader/`](desktop-downloader/) | Self-contained local browser UI for Windows, macOS, and Linux |

Each directory has its own launcher, dependencies, and documentation. Run commands from the relevant project directory rather than the repository root.

## Desktop releases and updates

The desktop project is the only project packaged by `.github/workflows/build-desktop.yml`.

- A source checkout finds this repository’s `.git` directory even though the application now lives in `desktop-downloader/`. Its **Check for updates** action fetches and fast-forwards the current Git branch.
- A packaged copy checks the repository’s GitHub Releases page and directs the user to the newest platform bundle.
- Moving the desktop code into its own directory therefore does not disable either update path.

See [`desktop-downloader/README.md`](desktop-downloader/README.md) for usage and Rekordbox guidance.
