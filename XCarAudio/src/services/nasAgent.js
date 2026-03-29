/**
 * NAS Agent client — talks to the Docker container running on the Synology NAS.
 * The agent URL is stored after first successful connection.
 */

import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

const AGENT_URL_KEY = 'nas_agent_url';

async function getBaseUrl() {
  const url = await SecureStore.getItemAsync(AGENT_URL_KEY);
  if (!url) throw new Error('NAS agent URL not configured. Set it in Settings.');
  return url;
}

export async function saveAgentUrl(url) {
  // Normalise: strip trailing slash
  await SecureStore.setItemAsync(AGENT_URL_KEY, url.replace(/\/$/, ''));
}

export async function testAgentConnection(url) {
  const res = await axios.get(`${url.replace(/\/$/, '')}/jobs`, { timeout: 5000 });
  return res.status === 200;
}

export async function createDownloadJob({ playlistName, title, artist, searchQuery }) {
  const base = await getBaseUrl();
  const res = await axios.post(`${base}/jobs`, {
    playlist_name: playlistName,
    title,
    artist,
    search_query: searchQuery,
  });
  return res.data;
}

export async function getJob(jobId) {
  const base = await getBaseUrl();
  const res = await axios.get(`${base}/jobs/${jobId}`);
  return res.data;
}

export async function listJobs() {
  const base = await getBaseUrl();
  const res = await axios.get(`${base}/jobs`);
  return res.data;
}
