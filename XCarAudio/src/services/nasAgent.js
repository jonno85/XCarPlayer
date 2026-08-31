/**
 * NAS Agent client — talks to the Docker container running on the Synology NAS.
 * The agent URL is stored after first successful connection.
 */

import axios from 'axios';
import * as SecureStore from 'expo-secure-store';
import { getSpotifyAuthMode, getSpotifyManualCredential, getValidSpotifyToken } from './spotifyAuth';

const AGENT_URL_KEY = 'nas_agent_url';
const AGENT_KEY_KEY = 'nas_agent_key';
const AGENT_PORT = 8899;

export function deriveAgentUrl(nasBaseUrl) {
  try {
    const parsed = new URL(nasBaseUrl);
    return `http://${parsed.hostname}:${AGENT_PORT}`;
  } catch {
    return null;
  }
}

const DEFAULT_AGENT_URL =
  process.env.EXPO_PUBLIC_AGENT_URL || 'http://jfilippininas.synology.me:8899';

async function getBaseUrl() {
  return (await SecureStore.getItemAsync(AGENT_URL_KEY)) ?? DEFAULT_AGENT_URL;
}

async function getApiKey() {
  return (await SecureStore.getItemAsync(AGENT_KEY_KEY)) ?? '';
}

export async function getAgentUrl() {
  return SecureStore.getItemAsync(AGENT_URL_KEY);
}

export async function getAgentKey() {
  return SecureStore.getItemAsync(AGENT_KEY_KEY);
}

function authHeaders(key) {
  return key ? { 'X-API-Key': key } : {};
}

export async function saveAgentUrl(url) {
  await SecureStore.setItemAsync(AGENT_URL_KEY, url.replace(/\/$/, ''));
}

export async function saveAgentKey(key) {
  await SecureStore.setItemAsync(AGENT_KEY_KEY, key);
}

export async function testAgentConnection(url, key) {
  console.log('Testing NAS agent connection to', url);
  const res = await axios.get(`${url.replace(/\/$/, '')}/jobs`, {
    timeout: 15000,
    headers: authHeaders(key),
  });
  return res.status === 200;
}

export async function checkAgentHealth() {
  try {
    const [base, key] = await Promise.all([getBaseUrl(), getApiKey()]);
    const res = await axios.get(`${base}/health`, {
      timeout: 5000,
      headers: authHeaders(key),
    });
    return res.status === 200;
  } catch {
    return false;
  }
}

export async function createDownloadJob({ playlistName, title, artist, searchQuery }) {
  const [base, key] = await Promise.all([getBaseUrl(), getApiKey()]);
  const res = await axios.post(
    `${base}/jobs`,
    { playlist_name: playlistName, title, artist, search_query: searchQuery },
    { headers: authHeaders(key) }
  );
  return res.data;
}

export async function getJob(jobId) {
  const [base, key] = await Promise.all([getBaseUrl(), getApiKey()]);
  const res = await axios.get(`${base}/jobs/${jobId}`, { headers: authHeaders(key) });
  return res.data;
}

export async function listJobs() {
  const [base, key] = await Promise.all([getBaseUrl(), getApiKey()]);
  const res = await axios.get(`${base}/jobs`, { headers: authHeaders(key) });
  return res.data;
}

export async function createPlaylistJob({ playlistUrl, playlistName }) {
  const [base, key, spotifyToken, spotifyAuthMode, spotifyManualCredential] = await Promise.all([
    getBaseUrl(),
    getApiKey(),
    getValidSpotifyToken(),
    getSpotifyAuthMode(),
    getSpotifyManualCredential(),
  ]);

  const body = { playlist_url: playlistUrl, playlist_name: playlistName };
  const credential = spotifyManualCredential?.trim() ?? '';

  if (spotifyAuthMode === 'manual' && credential) {
    body.spotify_credential = credential;
  } else if (spotifyToken) {
    body.spotify_token = spotifyToken;
  }

  const res = await axios.post(`${base}/playlist-jobs`, body, { headers: authHeaders(key) });
  return res.data;
}

export async function getPlaylistJob(jobId) {
  const [base, key] = await Promise.all([getBaseUrl(), getApiKey()]);
  const res = await axios.get(`${base}/playlist-jobs/${jobId}`, { headers: authHeaders(key) });
  return res.data;
}
