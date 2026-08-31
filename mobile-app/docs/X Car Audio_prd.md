# X Car Audio — PRD

## Overview

Mobile application (Expo bare workflow, iOS-first) that aggregates playlists from multiple music services, migrates them into a user-owned Synology NAS via DS Audio / AudioStation, and plays them on mobile + CarPlay / Android Auto.

---

## Target Platform

- **Primary**: iOS (CarPlay)
- **Secondary**: Android (Android Auto) — later
- **Distribution**: Sideloaded initially → App Store

---

## Source Integrations

| Service | Read Playlists | Read Metadata | Download Audio |
|---------|---------------|---------------|----------------|
| DS Audio (Synology) | Yes | Yes | Stream via QuickConnect |
| Spotify | Yes | Yes (OAuth) | No — metadata only |
| Beatport | Yes | Yes (OAuth, purchased tracks) | No — metadata only |
| YouTube Audio | No | Via search match | Via NAS agent (yt-dlp) |

---

## Architecture

```
[iOS App]
   │
   ├── Reads metadata from: Spotify API, Beatport API
   ├── Sends download jobs to: Synology NAS agent (via QuickConnect)
   ├── AudioStation API: manage playlists, track status
   └── CarPlay: browse playlists, playback controls

[Synology NAS — Docker container]
   ├── Receives job queue from app
   ├── Runs yt-dlp → downloads MP3 to AudioStation folder
   └── Reports job status back to app
```

**Key decision**: Downloads happen on the NAS, not on-device. The app is a remote controller. This avoids YouTube ToS issues in App Store review and eliminates the QuickConnect upload bottleneck.

---

## Synology / DS Audio Details

- Access via **QuickConnect** (remote, relayed — expect 300-800ms latency)
- API: DSM AudioStation REST API (DSM 7+)
- NAS must support Docker (DSM 7+ required)
- Audio files stored in AudioStation-managed folder
- Output format: **MP3** (primary)

---

## Migration Pipeline

1. User selects a Spotify or Beatport playlist in the app
2. App reads track metadata (title, artist, album) via service OAuth
3. App sends a job list to the NAS agent (Docker container)
4. NAS agent matches each track on YouTube via search, downloads MP3 with yt-dlp
5. NAS agent saves file to AudioStation folder and updates job status
6. App polls job status via QuickConnect and shows progress
7. On completion, app creates/updates the playlist in AudioStation

**Conflict handling**: If a track cannot be matched on YouTube → mark as failed, notify user, allow manual override.

---

## Audio Player

- Library: `react-native-track-player` (handles CarPlay + lock screen controls natively)
- Streams tracks from DS Audio via QuickConnect
- Supports: play, pause, skip, queue, shuffle
- CarPlay: browse playlists → tracks, playback controls
- Android Auto: same (Phase 2)

---

## Tech Stack

| Need | Library |
|------|---------|
| Framework | Expo (bare workflow) |
| CarPlay | `react-native-carplay` |
| Audio player | `react-native-track-player` |
| Spotify metadata | Spotify Web API (OAuth) |
| Beatport metadata | Beatport API (OAuth, paid) |
| Synology API | Axios + DSM AudioStation REST |
| Job polling | React Query |
| Secure auth storage | `expo-secure-store` |
| NAS agent | Docker + Python + yt-dlp |

---

## Phased Roadmap

### Phase 1 — Core Player ✅ `phase/1-core-player`
- Expo bare workflow scaffolded
- DS Audio / AudioStation service: login, playlist list, track list, stream URL
- `react-native-track-player` setup with background audio + lock screen controls
- CarPlay: playlist list → track list → NowPlaying template
- Screens: Library, Playlist, Player (now playing), Settings (NAS login)
- React Query for data fetching, SecureStore for credentials

### Phase 2 — Migration Pipeline ✅ `phase/2-migration-pipeline`
- NAS Docker agent (`../../synology-downloader/`): FastAPI + yt-dlp, POST /jobs, GET /jobs/{id}, MP3 to AudioStation folder
- Spotify OAuth (PKCE) via `expo-auth-session` → playlist + track metadata read
- Spotify public metadata fallback via Client Credentials (`SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`)
- Migration orchestrator: queues each track as NAS agent job with progress callback
- MigrationScreen: paste playlist URL → detect source → live job status
- MigrationJobsScreen: per-track status (pending / downloading / done / failed) with 3s polling
- Settings: NAS agent URL field + connectivity test + Spotify auth mode (`WebView login` or manual token / cookie)
- Deploy: `docker-compose up` on NAS, mounts `/volume1/music`, accessible via QuickConnect port 8765

### Phase 3 — Beatport + App Store
- Beatport OAuth + playlist read (purchased tracks)
- App Store prep: apply for CarPlay audio entitlement (apply early — takes weeks)
- Ensure no YouTube ToS violations surface in submission (NAS agent is user-owned server)

---

## Open Questions

- [ ] Does the Synology NAS support Docker? (DSM 7+ required)
- [ ] Beatport: purchased tracks or streaming subscription?
- [ ] Android Auto — target timeline?
- [ ] Multi-user Synology account support needed?
- [ ] Minimum iOS version to support?
