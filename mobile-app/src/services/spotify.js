/**
 * Spotify Web API — read-only playlist access.
 * Audio is never downloaded from Spotify; only metadata (title, artist) is used.
 *
 * Setup: create an app at https://developer.spotify.com/dashboard
 * Set redirect URI to: xcaraudio://spotify-callback
 */

import axios from 'axios';
import * as SecureStore from 'expo-secure-store';
import { makeRedirectUri, useAuthRequest, exchangeCodeAsync } from 'expo-auth-session';

const SPOTIFY_KEY = 'spotify_token';
const CLIENT_ID = process.env.EXPO_PUBLIC_SPOTIFY_CLIENT_ID || '';

const discovery = {
  authorizationEndpoint: 'https://accounts.spotify.com/authorize',
  tokenEndpoint: 'https://accounts.spotify.com/api/token',
};

export function useSpotifyAuth() {
  const redirectUri = makeRedirectUri({ scheme: 'xcaraudio', path: 'spotify-callback' });

  const [request, response, promptAsync] = useAuthRequest(
    {
      clientId: CLIENT_ID,
      scopes: ['playlist-read-private', 'playlist-read-collaborative'],
      redirectUri,
      usePKCE: true,
    },
    discovery
  );

  return { request, response, promptAsync, redirectUri };
}

export async function exchangeSpotifyCode(code, codeVerifier, redirectUri) {
  const result = await exchangeCodeAsync(
    { clientId: CLIENT_ID, code, redirectUri, extraParams: { code_verifier: codeVerifier } },
    discovery
  );
  await SecureStore.setItemAsync(SPOTIFY_KEY, result.accessToken);
  return result.accessToken;
}

async function spotifyGet(path, params = {}) {
  const token = await SecureStore.getItemAsync(SPOTIFY_KEY);
  if (!token) throw new Error('Not authenticated with Spotify');
  const res = await axios.get(`https://api.spotify.com/v1${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    params,
  });
  return res.data;
}

export async function getSpotifyPlaylists() {
  const data = await spotifyGet('/me/playlists', { limit: 50 });
  return data.items;
}

export async function getSpotifyPlaylistTracks(playlistId) {
  const tracks = [];
  let url = `/playlists/${playlistId}/tracks`;
  let params = { limit: 100, fields: 'items(track(name,artists)),next' };

  while (url) {
    const data = await spotifyGet(url, params);
    for (const item of data.items) {
      if (item.track) {
        tracks.push({
          title: item.track.name,
          artist: item.track.artists.map((a) => a.name).join(', '),
        });
      }
    }
    // Spotify returns a full next URL, not a path
    url = data.next ? data.next.replace('https://api.spotify.com/v1', '') : null;
    params = {};
  }
  return tracks;
}

export async function disconnectSpotify() {
  await SecureStore.deleteItemAsync(SPOTIFY_KEY);
}
