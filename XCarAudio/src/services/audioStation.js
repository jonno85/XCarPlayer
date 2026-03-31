import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

const STORAGE_KEY = 'synology_session';

// DSM AudioStation REST API wrapper
// Docs: https://global.download.synology.com/download/Document/Software/DeveloperGuide/Package/AudioStation/

let baseURL = null;

export async function configure(quickConnectId) {
  // QuickConnect resolves to a relay/direct URL
  // Store the resolved URL after first successful login
  const stored = await SecureStore.getItemAsync('synology_base_url');
  if (stored) baseURL = stored;
  else if (quickConnectId.startsWith('http://') || quickConnectId.startsWith('https://')) {
    baseURL = quickConnectId.replace(/\/$/, '');
  } else {
    baseURL = `https://${quickConnectId}.quickconnect.to`;
  }
}

async function getSid() {
  return SecureStore.getItemAsync(STORAGE_KEY);
}

export async function login(quickConnectId, username, password) {
  await configure(quickConnectId);
  console.log('[audioStation] baseURL:', baseURL);
  console.log('[audioStation] hitting:', `${baseURL}/webapi/auth.cgi`);
  const res = await axios.get(`${baseURL}/webapi/auth.cgi`, {
    params: {
      api: 'SYNO.API.Auth',
      version: 3,
      method: 'login',
      account: username,
      passwd: password,
      session: 'AudioStation',
      format: 'sid',
    },
  });
  if (!res.data.success) throw new Error('Login failed');
  const sid = res.data.data.sid;
  await SecureStore.setItemAsync(STORAGE_KEY, sid);
  await SecureStore.setItemAsync('synology_base_url', baseURL);
  return sid;
}

export async function logout() {
  const sid = await getSid();
  if (sid) {
    await axios.get(`${baseURL}/webapi/auth.cgi`, {
      params: { api: 'SYNO.API.Auth', version: 1, method: 'logout', session: 'AudioStation', _sid: sid },
    });
    await SecureStore.deleteItemAsync(STORAGE_KEY);
    await SecureStore.deleteItemAsync('synology_base_url');
    baseURL = null;
  }
}

async function get(api, method, params = {}) {
  const sid = await getSid();
  const res = await axios.get(`${baseURL}/webapi/AudioStation/${api}`, {
    params: { api: `SYNO.AudioStation.${api}`, method, version: 2, _sid: sid, ...params },
  });
  if (!res.data.success) throw new Error(`AudioStation error: ${JSON.stringify(res.data.error)}`);
  return res.data.data;
}

export async function getPlaylists() {
  const data = await get('playlist', 'list', { limit: 500, offset: 0 });
  return data.playlists;
}

export async function getPlaylistTracks(playlistId) {
  const data = await get('playlist', 'getinfo', {
    id: playlistId,
    additional: 'songs',
    limit: 500,
    offset: 0,
  });
  return data.playlists[0]?.additional?.songs || [];
}

// Returns a streamable URL for react-native-track-player
export async function getStreamUrl(songId) {
  const sid = await getSid();
  return `${baseURL}/webapi/AudioStation/stream.cgi?api=SYNO.AudioStation.Stream&version=2&method=stream&id=${songId}&_sid=${sid}`;
}

export function trackToPlayerItem(track, streamUrl) {
  return {
    id: track.id,
    url: streamUrl,
    title: track.title,
    artist: track.additional?.song_tag?.artist || '',
    album: track.additional?.song_tag?.album || '',
    artwork: track.additional?.song_audio?.coverart
      ? `${baseURL}/webapi/AudioStation/cover.cgi?id=${track.id}&_sid=__SID__`
      : undefined,
  };
}
