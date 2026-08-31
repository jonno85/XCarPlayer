# Synology AudioStation API Client (QuickConnect + DSM 7.x)

This document describes how to implement a **Synology AudioStation API client** usable from **React‑Native** (or any mobile app) using **QuickConnect**, **DSM 7.3+**, and **2FA**.

This is designed as a **synthetic implementation guide for LLMs**.

---

# Overview

Goal:

Build a React‑Native client that can:

- Authenticate via QuickConnect
- Handle 2FA (OTP)
- Discover NAS endpoint
- Load playlists
- Load songs
- Stream audio
- Download audio
- Sync playlists

---

# Architecture

```
React Native App
        ↓
QuickConnect Resolver
        ↓
Synology Relay / Direct
        ↓
DSM WebAPI (AudioStation)
```

---

# Step 1 — QuickConnect Discovery

QuickConnect is **not a direct API endpoint**.

First resolve using:

POST

```
https://global.quickconnect.to/Serv.php
```

Body:

```json
{
  "version": "1",
  "command": "get_server_info",
  "serverID": "YOUR_QUICKCONNECT_ID",
  "id": "dsm_https"
}
```

Response contains:

- relay endpoint
- ddns
- direct ip
- smartdns host

Example important fields:

```
service.relay_dn
service.relay_port
smartdns.host
server.ddns
```

Preferred endpoint order:

1. smartdns host
2. relay_dn
3. ddns

Example:

```
https://synr-fr3.<ID>.direct.quickconnect.to:54669
```

This becomes:

```
BASE_URL
```

---

# Step 2 — Login (DSM 7.x)

Endpoint:

```
/webapi/auth.cgi
```

Request:

```
GET {BASE_URL}/webapi/auth.cgi
```

Parameters:

```
api=SYNO.API.Auth
version=7
method=login
account=USERNAME
passwd=PASSWORD
session=AudioStation
format=sid
```

Example:

```
GET /webapi/auth.cgi?api=SYNO.API.Auth&version=7&method=login&account=jonathan&passwd=xxx&session=AudioStation&format=sid
```

---

# Step 3 — 2FA Flow

If 2FA enabled, response:

```json
{
  "error": {
    "code": 403,
    "errors": {
      "token": "...",
      "types": [
        {"type": "otp"}
      ]
    }
  }
}
```

Second request:

```
api=SYNO.API.Auth
method=login
version=7
account=USERNAME
passwd=PASSWORD
otp_code=123456
token=TOKEN
session=AudioStation
format=sid
```

Success response:

```json
{
  "success": true,
  "data": {
    "sid": "...",
    "synotoken": "...",
    "device_id": "..."
  }
}
```

Store:

- sid
- synotoken
- device_id

---

# Authentication Usage

All requests require:

Query param:

```
_sid=SID
```

Header:

```
X-SYNO-TOKEN: SYNCTOKEN
```

---

# Step 4 — API Discovery (Recommended)

```
/webapi/query.cgi
```

Example:

```
GET /webapi/query.cgi?api=SYNO.API.Info&version=1&method=query&query=all
```

Returns:

- available APIs
- versions
- paths

Use dynamically.

---

# AudioStation APIs

Base path:

```
/webapi/AudioStation/
```

Main APIs:

| Feature | API |
|--------|-----|
| Playlists | SYNO.AudioStation.Playlist |
| Songs | SYNO.AudioStation.Song |
| Stream | SYNO.AudioStation.Stream |
| Player | SYNO.AudioStation.Player |
| Search | SYNO.AudioStation.Search |

---

# Get Playlists

```
GET /webapi/AudioStation/playlist.cgi
```

Parameters:

```
api=SYNO.AudioStation.Playlist
version=3
method=list
```

---

# Get Songs from Playlist

```
GET /webapi/AudioStation/song.cgi
```

Parameters:

```
api=SYNO.AudioStation.Song
method=list
library=playlist
id=playlist_id
```

---

# Stream Song

```
/webapi/AudioStation/stream.cgi
```

Parameters:

```
api=SYNO.AudioStation.Stream
version=2
method=stream
id=song_id
```

Return:

```
audio stream
```

React Native usable directly.

---

# Download Song

Same endpoint:

```
method=download
```

---

# Create Playlist

```
POST /webapi/AudioStation/playlist.cgi
```

Parameters:

```
method=create
name=Playlist
```

---

# Add Songs to Playlist

```
method=add_song
```

Parameters:

```
id=playlist_id
songs=song1,song2
```

---

# React Native Implementation Structure

Recommended client:

```
src/
  synology/
    quickconnect.ts
    auth.ts
    audiostation.ts
    types.ts
```

---

# quickconnect.ts

Responsibilities:

- resolve Serv.php
- select best endpoint
- cache base url

---

# auth.ts

Responsibilities:

- login
- handle OTP
- store sid
- refresh session

---

# audiostation.ts

Functions:

```
getPlaylists()
getPlaylistSongs()
streamSong()
downloadSong()
createPlaylist()
addSongs()
```

---

# Session Strategy

Recommended:

- cache sid
- refresh every 30 min
- retry on 403

---

# Streaming Strategy

Return URL directly:

```
{BASE_URL}/webapi/AudioStation/stream.cgi?...&_sid=SID
```

Use React Native:

- react-native-track-player
- expo-av

---

# Example Client Interface

```
interface SynologyClient {
  login(): Promise<void>
  getPlaylists(): Promise<Playlist[]>
  getPlaylistSongs(id: string): Promise<Song[]>
  getStreamUrl(id: string): string
}
```

---

# Error Handling

Common errors:

| Code | Meaning |
|------|---------|
| 105 | Session expired |
| 403 | 2FA required |
| 119 | Invalid session |

Retry strategy:

```
retry → refresh login → retry request
```

---

# Recommended Enhancements

- cache playlists
- background sync
- offline downloads
- waveform metadata
- album art caching

---

# Security Notes

- never store password
- store sid securely
- use secure storage (Keychain / Keystore)

---

# Testing

Test endpoints:

```
/webapi/query.cgi
/webapi/auth.cgi
/webapi/AudioStation/playlist.cgi
```

---

# Minimal Flow

1. Resolve QuickConnect
2. Login
3. Handle 2FA
4. Store SID
5. Load playlists
6. Stream songs

---

# Production Ready

This design supports:

- remote access
- relay fallback
- DSM 7.3
- 2FA
- mobile streaming

---

# Cookie Login Alternative

DSM supports cookie based authentication which avoids passing `_sid` in URLs.

Login:

```
format=cookie
```

Example:

```
GET /webapi/auth.cgi
api=SYNO.API.Auth
version=7
method=login
account=USERNAME
passwd=PASSWORD
session=AudioStation
format=cookie
```

Store cookies:

- id
- synotoken

React‑Native:

Use:

- react-native-cookies
- expo-cookie-manager

All subsequent requests automatically authenticated.

Recommended over `_sid` for:

- streaming
- background playback
- fewer auth errors

---

# Session Token Refresh Strategy

Goal: Avoid re-login for up to 1 month

Strategies:

## Use device_id

Include during login:

```
device_id

device_name
```

DSM remembers trusted device.

Example:

```
device_name=react-native

device_id=uuid
```

---

## Session Keep Alive

Ping periodically:

```
/webapi/entry.cgi
```

Example:

```
SYNO.Core.System
method=info
```

Run:

- every 12 hours
- background task

This extends session lifetime.

---

## Refresh On Expiry

When response codes:

- 105
- 106
- 119

Then:

1. refresh login
2. retry request

---

# TypeScript Interfaces

```
export interface SynologySession {
  sid?: string
  synotoken?: string
  deviceId?: string
  baseUrl: string
}

export interface Playlist {
  id: string
  name: string
  song_count?: number
}

export interface Song {
  id: string
  title: string
  album?: string
  artist?: string
  duration?: number
  cover?: string
}

export interface SynologyClient {
  login(): Promise<void>
  getPlaylists(): Promise<Playlist[]>
  getPlaylistSongs(id: string): Promise<Song[]>
  getStreamUrl(id: string): string
}
```

---

# React Native Hook

```
export function useSynology() {
  const [client, setClient] = useState<SynologyClient>()

  useEffect(() => {
    init()
  }, [])

  async function init() {
    const client = await createSynologyClient()
    await client.login()
    setClient(client)
  }

  return {
    client
  }
}
```

---

# Expo Audio Player Integration

Recommended:

- expo-av
- react-native-track-player

Example expo-av:

```
import { Audio } from 'expo-av'

const sound = new Audio.Sound()

await sound.loadAsync({
  uri: streamUrl
})

await sound.playAsync()
```

Stream URL:

```
/webapi/AudioStation/stream.cgi
```

Include:

- cookie
- sid

---

# Playlist Sync Algorithm

Goal:

Sync remote playlist locally

Strategy:

1. fetch playlists
2. store locally
3. fetch songs per playlist
4. compute hash
5. compare local
6. update diff

Pseudo:

```
for playlist in remote:

  local = db.get(playlist.id)

  if hash(remote) != hash(local):
     update()
```

---

# Background Sync

Recommended:

- sync every app open
- sync every 6 hours

Use:

- expo-background-fetch

---

# Album Art

Endpoint:

```
/webapi/AudioStation/cover.cgi
```

Use caching.

---

# Offline Download Strategy

1. download file
2. store local path
3. update playlist metadata

---

# Recommended Libraries

React Native:

- expo-av
- react-native-track-player
- react-query
- zustand

---

# Suggested Folder Structure

```
src/
  synology/
    client.ts
    auth.ts
    quickconnect.ts
    audiostation.ts
    sync.ts
    types.ts
```

---

# Production Notes

Recommended:

- cache session
- background keep alive
- cookie login
- retry strategy

---

# Final Minimal Flow

1. Resolve QuickConnect
2. Login (cookie)
3. Store device id
4. Keep alive
5. Load playlists
6. Stream songs

---

End of File


