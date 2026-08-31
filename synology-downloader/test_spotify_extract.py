#!/usr/bin/env python3
"""
Test script: compare two approaches to fetch a Spotify playlist track list
without using the official Web API client credentials.

Usage:
    python test_spotify_extract.py [playlist_url]

Default playlist: the one hardcoded below.
"""

import sys
import json
import re
import urllib.request

PLAYLIST_URL = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "https://open.spotify.com/playlist/5jkcDwuWgkdxndfSZcVOAu"
)

# ---------------------------------------------------------------------------
# Option 1: yt-dlp built-in Spotify extractor
# ---------------------------------------------------------------------------

def test_ytdlp(playlist_url: str):
    print("\n=== Option 1: yt-dlp Spotify extractor ===")
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)

        entries = info.get("entries") or []
        tracks = []
        for e in entries:
            title = e.get("title") or ""
            artist = e.get("artist") or e.get("creator") or e.get("uploader") or ""
            if title:
                tracks.append({"id": e.get("id"), "title": title, "artist": artist})

        print(f"  Found {len(tracks)} tracks")
        for t in tracks[:5]:
            print(f"  - {t['artist']} — {t['title']}  (id: {t['id']})")
        if len(tracks) > 5:
            print(f"  ... and {len(tracks) - 5} more")
        return tracks

    except Exception as e:
        print(f"  FAILED: {e}")
        return None


# ---------------------------------------------------------------------------
# Option 2: spotdl
# ---------------------------------------------------------------------------

def test_spotdl(playlist_url: str):
    print("\n=== Option 2: spotdl ===")
    try:
        from spotdl import Spotdl
    except ImportError:
        print("  spotdl not installed — run: pip install spotdl")
        return None

    try:
        # spotdl needs Spotify credentials only to look up metadata.
        # Leave them empty to see if it falls back to its own bundled creds.
        spot = Spotdl(client_id="351ea4286b3a45bf9523644c36cc91ec", client_secret="bdf1a86778954b5eb7c624634278d28a", headless=True)
        songs = spot.search([playlist_url])

        print(f"  Found {len(songs)} tracks")
        for s in songs[:5]:
            print(f"  - {s.artist} — {s.name}")
        if len(songs) > 5:
            print(f"  ... and {len(songs) - 5} more")
        return songs

    except Exception as e:
        print(f"  FAILED: {e}")
        return None


# ---------------------------------------------------------------------------
# Option 3: scrape open.spotify.com (no credentials)
# ---------------------------------------------------------------------------

def test_scrape(playlist_url: str):
    print("\n=== Option 3: scrape open.spotify.com ===")
    try:
        playlist_id = playlist_url.split("playlist/")[1].split("?")[0]

        # Try the embed page first — lighter, more likely to include track data
        for url in [
            f"https://open.spotify.com/embed/playlist/{playlist_id}",
            f"https://open.spotify.com/playlist/{playlist_id}",
        ]:
            print(f"  Fetching {url} ...")
            req = urllib.request.Request(url, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
                html, re.DOTALL
            )
            if not match:
                print("  No __NEXT_DATA__ found")
                continue

            data = json.loads(match.group(1))
            # Dump structure so we can navigate it
            print(f"  __NEXT_DATA__ top-level keys: {list(data.keys())}")

            # Try common paths where Spotify puts track lists
            tracks = _dig_tracks(data)
            if tracks:
                print(f"  Found {len(tracks)} tracks")
                for t in tracks[:5]:
                    print(f"  - {t.get('artist', '?')} — {t.get('title', '?')}")
                if len(tracks) > 5:
                    print(f"  ... and {len(tracks) - 5} more")
                return tracks
            else:
                print("  Could not locate tracks in JSON — dumping first 2000 chars:")
                print("  " + json.dumps(data)[:2000])

    except Exception as e:
        print(f"  FAILED: {e}")
    return None


def _dig_tracks(data: dict) -> list[dict]:
    """Walk known Spotify Next.js data shapes to find track items."""
    # Shape 1: props.pageProps.state.data.entity.trackList
    try:
        track_list = (
            data["props"]["pageProps"]["state"]["data"]["entity"]["trackList"]
        )
        return [
            {"title": t["title"], "artist": t["subtitle"]}
            for t in track_list
            if t.get("title")
        ]
    except (KeyError, TypeError):
        pass

    # Shape 2: props.pageProps.componentProps.tracks.items
    try:
        items = (
            data["props"]["pageProps"]["componentProps"]["tracks"]["items"]
        )
        return [
            {
                "title": i["track"]["name"],
                "artist": ", ".join(a["name"] for a in i["track"]["artists"]),
            }
            for i in items
            if i.get("track")
        ]
    except (KeyError, TypeError):
        pass

    return []


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Playlist: {PLAYLIST_URL}")

    r1 = test_ytdlp(PLAYLIST_URL)
    r2 = test_spotdl(PLAYLIST_URL)
    r3 = test_scrape(PLAYLIST_URL)

    print("\n=== Summary ===")
    print(f"  yt-dlp:  {'OK — ' + str(len(r1)) + ' tracks' if r1 is not None else 'FAILED'}")
    print(f"  spotdl:  {'OK — ' + str(len(r2)) + ' tracks' if r2 is not None else 'FAILED'}")
    print(f"  scrape:  {'OK — ' + str(len(r3)) + ' tracks' if r3 is not None else 'FAILED'}")
