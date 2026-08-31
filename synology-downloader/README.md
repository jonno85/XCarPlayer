# Synology downloader

Dockerized FastAPI service used by the X Car Audio mobile app. It accepts download jobs, resolves supported source metadata, downloads permitted audio with `yt-dlp`, and writes it into the NAS music volume.

## Configure

```sh
cp .env.example .env
```

Edit `.env`, then update the host side of the music volume in `docker-compose.yml` if the Synology music directory is not `/volume1/music`.

## Run

```sh
docker compose up -d --build
docker compose logs -f
```

The default host endpoint is `http://NAS_ADDRESS:8899`. Configure that URL in the mobile app under [`../mobile-app/`](../mobile-app/).

## Spotify extraction diagnostic

```sh
python test_spotify_extract.py
```

This diagnostic contacts Spotify and compares extraction approaches; it is not an offline unit-test suite.
