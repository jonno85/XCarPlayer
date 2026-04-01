import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

const SESSION_KEY = 'synology_session';
const BASE_URL_KEY = 'synology_base_url';
const DEVICE_ID_KEY = 'synology_device_id';

const AUTH_PATH = '/webapi/auth.cgi';
const QUERY_PATH = '/webapi/query.cgi';
const QUICKCONNECT_URL = 'https://global.quickconnect.to/Serv.php';

const AUDIO_STATION_DEFAULTS = {
  'SYNO.AudioStation.Playlist': { path: 'AudioStation/playlist.cgi', version: 3 },
  'SYNO.AudioStation.Song': { path: 'AudioStation/song.cgi', version: 3 },
  'SYNO.AudioStation.Stream': { path: 'AudioStation/stream.cgi', version: 2 },
};

const AUTH_ERROR_CODES = new Set([105, 106, 119]);

let sessionCache = null;
let apiInfoCache = null;
let authContext = null;

function normalizeBaseUrl(value) {
  return value?.replace(/\/+$/, '') ?? null;
}

function makeError(message, details = {}) {
  const error = new Error(message);
  Object.assign(error, details);
  return error;
}

async function loadSession() {
  if (sessionCache) return sessionCache;

  const stored = await SecureStore.getItemAsync(SESSION_KEY);
  if (!stored) return null;

  try {
    sessionCache = JSON.parse(stored);
    return sessionCache;
  } catch {
    await SecureStore.deleteItemAsync(SESSION_KEY);
    return null;
  }
}

async function persistSession(session) {
  sessionCache = session;
  apiInfoCache = null;
  await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(session));
  await SecureStore.setItemAsync(BASE_URL_KEY, session.baseUrl);
}

async function clearSession() {
  sessionCache = null;
  apiInfoCache = null;
  await SecureStore.deleteItemAsync(SESSION_KEY);
  await SecureStore.deleteItemAsync(BASE_URL_KEY);
}

async function getDeviceId() {
  let deviceId = await SecureStore.getItemAsync(DEVICE_ID_KEY);
  if (!deviceId) {
    deviceId = `xcaraudio-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    await SecureStore.setItemAsync(DEVICE_ID_KEY, deviceId);
  }
  return deviceId;
}

function appendCandidate(candidates, host, port) {
  if (!host) return;

  const normalizedHost = String(host).trim();
  if (!normalizedHost) return;

  if (normalizedHost.startsWith('http://') || normalizedHost.startsWith('https://')) {
    candidates.push(normalizeBaseUrl(normalizedHost));
    return;
  }

  const suffix = port ? `:${port}` : '';
  candidates.push(`https://${normalizedHost}${suffix}`);
}

function describeAxiosError(error) {
  if (!error) return 'Unknown error';

  const status = error?.response?.status;
  const code = error?.code;
  const message = error?.message;
  const payload = error?.response?.data;

  return JSON.stringify({
    message,
    code,
    status,
    payload,
  });
}

async function resolveQuickConnect(quickConnectId) {
  if (!quickConnectId) throw new Error('QuickConnect ID is required');

  if (/^https?:\/\//i.test(quickConnectId)) {
    return normalizeBaseUrl(quickConnectId);
  }

  const storedSession = await loadSession();
  if (storedSession?.baseUrl && storedSession?.quickConnectId === quickConnectId) {
    return normalizeBaseUrl(storedSession.baseUrl);
  }

  try {
    const response = await axios.post(
      QUICKCONNECT_URL,
      {
        version: '1',
        command: 'get_server_info',
        serverID: quickConnectId,
        id: 'dsm_https',
      },
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: 15000,
      }
    );
    console.log('[audioStation] QuickConnect response', response?.data);
    const payload = response.data ?? {};
    const service = payload.service ?? {};
    const smartdns = payload.smartdns ?? {};
    const server = payload.server ?? {};
    const env = payload.env ?? {};
    
    const candidates = [];
    appendCandidate(candidates, smartdns.host, smartdns.port || service.smartdns_port || payload.port);
    appendCandidate(candidates, service.relay_dn, service.relay_port);
    appendCandidate(candidates, server.ddns, smartdns.port || service.smartdns_port || payload.port);
    appendCandidate(candidates, env.control_host, env.control_port);
    console.log('[audioStation] QuickConnect candidates', candidates);

    const uniqueCandidates = [...new Set(candidates.filter(Boolean))];
    for (const candidate of uniqueCandidates) {
      try {
        console.log('[audioStation] Testing QuickConnect trying candidate', candidate);
        const response = await rawRequest({
          baseUrl: candidate,
          path: AUTH_PATH,
          method: 'get',
          params: {
            api: 'SYNO.API.Auth',
            version: 7,
            method: 'login',
            session: 'AudioStation',
            format: 'cookie',
          },
          timeout: 20000,
          validateStatus: () => true,
        });
        console.log('[audioStation] QuickConnect response from candidate', candidate, response?.status, response?.data);

        if ((response?.status ?? 0) < 500) {
          return candidate;
        }

        console.warn('[audioStation] Candidate returned server error, trying next', candidate, response?.status);
      } catch (error) {
        console.warn('[audioStation] Candidate unreachable, trying next', candidate, describeAxiosError(error));
      }
    }
  } catch (error) {
    console.warn('[audioStation] QuickConnect resolution failed', describeAxiosError(error));
  }

  return `https://${quickConnectId}.quickconnect.to`;
}

export async function configure(quickConnectId) {
  const baseUrl = await resolveQuickConnect(quickConnectId);
  const session = await loadSession();

  if (session?.baseUrl && session.baseUrl !== baseUrl) {
    sessionCache = { ...session, baseUrl };
  }

  return baseUrl;
}

async function rawRequest({
  baseUrl,
  path,
  method = 'get',
  params,
  data,
  headers,
  timeout = 20000,
  validateStatus,
}) {
  return axios({
    baseURL: baseUrl,
    url: path,
    method,
    params,
    data,
    timeout,
    headers,
    validateStatus,
  });
}

function extractOtpToken(payload) {
  return payload?.error?.errors?.token;
}

async function performLoginRequest({
  baseUrl,
  username,
  password,
  otpCode,
  token,
  deviceId,
}) {
  const params = {
    api: 'SYNO.API.Auth',
    version: 7,
    method: 'login',
    account: username,
    passwd: password,
    session: 'AudioStation',
    format: 'sid',
    device_id: deviceId,
    device_name: 'x-car-audio',
  };

  if (otpCode) params.otp_code = otpCode;
  if (token) params.token = token;

  const response = await rawRequest({
    baseUrl,
    path: AUTH_PATH,
    method: 'get',
    params,
    validateStatus: () => true,
  });

  const payload = response.data ?? {};
  console.log('[audioStation] Login response', JSON.stringify(payload));
  if (payload.success) return payload.data;

  const errorCode = payload?.error?.code;
  if (errorCode === 403) {
    throw makeError('Two-factor authentication required', {
      code: 'OTP_REQUIRED',
      otpToken: extractOtpToken(payload),
      details: payload.error,
    });
  }

  throw makeError(`Synology login failed${errorCode ? ` (${errorCode})` : ''}`, {
    code: errorCode,
    httpStatus: response.status,
    details: payload.error,
  });
}

async function hydrateApiInfo(baseUrl, sid, synotoken) {
  try {
    const response = await rawRequest({
      baseUrl,
      path: QUERY_PATH,
      method: 'get',
      params: {
        api: 'SYNO.API.Info',
        version: 1,
        method: 'query',
        query: 'all',
        _sid: sid,
      },
      headers: synotoken ? { 'X-SYNO-TOKEN': synotoken } : undefined,
    });

    if (response.data?.success) {
      apiInfoCache = response.data.data ?? {};
    }
  } catch (error) {
    console.warn('[audioStation] Failed to query API info', error?.message);
  }
}

async function refreshSession() {
  if (!authContext?.quickConnectId || !authContext?.username || !authContext?.password) {
    throw new Error('Session expired. Please sign in again.');
  }

  await login(authContext.quickConnectId, authContext.username, authContext.password);
  return loadSession();
}

function isAuthFailure(payload) {
  const code = payload?.error?.code;
  return AUTH_ERROR_CODES.has(code);
}

function getApiConfig(apiName) {
  const discovered = apiInfoCache?.[apiName];
  const fallback = AUDIO_STATION_DEFAULTS[apiName];

  return {
    path: discovered?.path || fallback?.path,
    version: discovered?.maxVersion || fallback?.version,
  };
}

async function authedRequest({
  path,
  method = 'get',
  params,
  data,
  retry = true,
}) {
  const session = await loadSession();
  if (!session?.sid || !session?.baseUrl) {
    throw new Error('Not connected to Synology');
  }

  const headers = { ...(session.synotoken ? { 'X-SYNO-TOKEN': session.synotoken } : {}) };
  if (method.toLowerCase() === 'post') {
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
  }

  const response = await rawRequest({
    baseUrl: session.baseUrl,
    path,
    method,
    params: { ...params, _sid: session.sid },
    data,
    headers: Object.keys(headers).length > 0 ? headers : undefined,
  });

  const payload = response.data ?? {};
  if (payload.success) return payload.data;

  if (retry && isAuthFailure(payload)) {
    await refreshSession();
    return authedRequest({ path, method, params, data, retry: false });
  }

  throw makeError(`Synology request failed${payload?.error?.code ? ` (${payload.error.code})` : ''}`, {
    code: payload?.error?.code,
    details: payload?.error,
  });
}

async function audioStationRequest({
  apiName,
  method,
  params = {},
  httpMethod = 'get',
}) {
  const config = getApiConfig(apiName);
  if (!config?.path || !config?.version) {
    throw new Error(`Unsupported AudioStation API: ${apiName}`);
  }

  let data;
  let requestParams = {
    api: apiName,
    version: config.version,
    method,
    ...params,
  };

  if (httpMethod === 'post') {
    data = new URLSearchParams(requestParams).toString();
    requestParams = undefined;
  }

  return authedRequest({
    path: `/webapi/${config.path}`,
    method: httpMethod,
    params: requestParams,
    data,
  });
}

function getCurrentBaseUrl() {
  return sessionCache?.baseUrl ?? null;
}

function getCurrentSessionId() {
  return sessionCache?.sid ?? null;
}

function getCurrentToken() {
  return sessionCache?.synotoken ?? null;
}

function normalizePlaylist(playlist) {
  return {
    ...playlist,
    id: String(playlist.id),
    name: playlist.name,
    song_count: playlist.song_count ?? playlist.additional?.songs?.length ?? 0,
  };
}

function normalizeSong(song) {
  const artist = song.additional?.song_tag?.artist || song.artist || '';
  const album = song.additional?.song_tag?.album || song.album || '';

  return {
    ...song,
    id: String(song.id),
    title: song.title,
    artist,
    album,
    duration: song.additional?.song_audio?.duration ?? song.duration,
    cover: song.cover ?? getCoverUrl(song.id),
  };
}

function getCoverUrl(songId) {
  const baseUrl = getCurrentBaseUrl();
  const sid = getCurrentSessionId();
  if (!baseUrl || !sid) return undefined;

  return `${baseUrl}/webapi/AudioStation/cover.cgi?id=${encodeURIComponent(songId)}&_sid=${encodeURIComponent(sid)}`;
}

export async function login(quickConnectId, username, password, options = {}) {
  if (!quickConnectId || !username || !password) {
    throw new Error('QuickConnect ID, username, and password are required');
  }

  let baseUrl;
  if (authContext?.quickConnectId === quickConnectId && authContext?.baseUrl) {
    baseUrl = authContext.baseUrl;
  } else {
    baseUrl = await configure(quickConnectId);
  }

  const deviceId = await getDeviceId();

  authContext = {
    quickConnectId,
    username,
    password,
    baseUrl,
  };

  const loginData = await performLoginRequest({
    baseUrl,
    username,
    password,
    otpCode: typeof options === 'string' ? options : options.otpCode,
    token: typeof options === 'object' ? options.token : undefined,
    deviceId,
  });

  const session = {
    sid: loginData.sid,
    synotoken: loginData.synotoken,
    deviceId: loginData.device_id || deviceId,
    baseUrl,
    quickConnectId,
    lastLoginAt: new Date().toISOString(),
  };

  await persistSession(session);
  await hydrateApiInfo(baseUrl, session.sid, session.synotoken);
  return session;
}

export async function logout() {
  const session = await loadSession();
  if (session?.sid && session?.baseUrl) {
    try {
      await rawRequest({
        baseUrl: session.baseUrl,
        path: AUTH_PATH,
        method: 'get',
        params: {
          api: 'SYNO.API.Auth',
          version: 1,
          method: 'logout',
          session: 'AudioStation',
          _sid: session.sid,
        },
        headers: session.synotoken ? { 'X-SYNO-TOKEN': session.synotoken } : undefined,
      });
    } catch (error) {
      console.warn('[audioStation] Logout failed', error?.message);
    }
  }

  authContext = null;
  await clearSession();
}

export async function getPlaylists() {
  const data = await audioStationRequest({
    apiName: 'SYNO.AudioStation.Playlist',
    method: 'list',
    params: { limit: 500, offset: 0 },
  });

  return (data.playlists ?? []).map(normalizePlaylist);
}

export async function getPlaylistTracks(playlistId) {
  const data = await audioStationRequest({
    apiName: 'SYNO.AudioStation.Song',
    method: 'list',
    params: {
      library: 'playlist',
      id: playlistId,
      additional: 'song_tag,song_audio',
      limit: 500,
      offset: 0,
    },
  });

  return (data.songs ?? []).map(normalizeSong);
}

export async function getStreamUrl(songId) {
  const session = await loadSession();
  if (!session?.sid || !session?.baseUrl) {
    throw new Error('Not connected to Synology');
  }

  return `${session.baseUrl}/webapi/AudioStation/stream.cgi?api=SYNO.AudioStation.Stream&version=2&method=stream&id=${encodeURIComponent(songId)}&_sid=${encodeURIComponent(session.sid)}`;
}

export async function getDownloadUrl(songId) {
  const session = await loadSession();
  if (!session?.sid || !session?.baseUrl) {
    throw new Error('Not connected to Synology');
  }

  return `${session.baseUrl}/webapi/AudioStation/stream.cgi?api=SYNO.AudioStation.Stream&version=2&method=download&id=${encodeURIComponent(songId)}&_sid=${encodeURIComponent(session.sid)}`;
}

export async function createPlaylist(name) {
  const data = await audioStationRequest({
    apiName: 'SYNO.AudioStation.Playlist',
    method: 'create',
    params: { name },
    httpMethod: 'post',
  });

  return normalizePlaylist(data.playlist ?? { id: data.id, name });
}

export async function addSongs(playlistId, songIds) {
  const songs = Array.isArray(songIds) ? songIds.join(',') : String(songIds);

  return audioStationRequest({
    apiName: 'SYNO.AudioStation.Playlist',
    method: 'add_song',
    params: {
      id: playlistId,
      songs,
    },
    httpMethod: 'post',
  });
}

export async function getSession() {
  return loadSession();
}

export function trackToPlayerItem(track, streamUrl) {
  return {
    id: track.id,
    url: streamUrl,
    title: track.title,
    artist: track.artist || track.additional?.song_tag?.artist || '',
    album: track.album || track.additional?.song_tag?.album || '',
    artwork: track.cover,
    headers: getCurrentToken() ? { 'X-SYNO-TOKEN': getCurrentToken() } : undefined,
  };
}
