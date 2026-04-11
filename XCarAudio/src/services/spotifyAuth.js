import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'spotify_access_token';
const TOKEN_EXPIRY_KEY = 'spotify_token_expiry_ms';
const AUTH_MODE_KEY = 'spotify_auth_mode';
const MANUAL_CREDENTIAL_KEY = 'spotify_manual_credential';
const DEFAULT_PLAYLIST_KEY = 'spotify_default_playlist';

export async function getSpotifyToken() {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

/** Returns the token only if it's still valid (with a 5-minute buffer).
 *  Tokens saved without expiry info are treated as expired. */
export async function getValidSpotifyToken() {
  const [token, expiryStr] = await Promise.all([
    SecureStore.getItemAsync(TOKEN_KEY),
    SecureStore.getItemAsync(TOKEN_EXPIRY_KEY),
  ]);
  if (!token) return null;
  if (!expiryStr) return null; // no expiry stored → saved before fix, assume stale
  const expiryMs = parseInt(expiryStr, 10);
  if (Number.isNaN(expiryMs) || Date.now() > expiryMs - 5 * 60 * 1000) return null;
  return token;
}

export async function saveSpotifyToken(token, expiryMs = null) {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
  if (expiryMs) {
    await SecureStore.setItemAsync(TOKEN_EXPIRY_KEY, String(expiryMs));
  }
}

export async function clearSpotifyToken() {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export async function getSpotifyAuthMode() {
  const v = await SecureStore.getItemAsync(AUTH_MODE_KEY);
  return v === 'manual' ? 'manual' : 'webview';
}

export async function setSpotifyAuthMode(mode) {
  await SecureStore.setItemAsync(AUTH_MODE_KEY, mode === 'manual' ? 'manual' : 'webview');
}

export async function getSpotifyManualCredential() {
  return SecureStore.getItemAsync(MANUAL_CREDENTIAL_KEY);
}

export async function saveSpotifyManualCredential(value) {
  await SecureStore.setItemAsync(MANUAL_CREDENTIAL_KEY, value);
}

export async function clearSpotifyManualCredential() {
  await SecureStore.deleteItemAsync(MANUAL_CREDENTIAL_KEY);
}

// Backward compatibility for older callers that treated this as a boolean toggle.
export async function getSpotifyWebViewEnabled() {
  return (await getSpotifyAuthMode()) !== 'manual';
}

export async function setSpotifyWebViewEnabled(enabled) {
  await setSpotifyAuthMode(enabled ? 'webview' : 'manual');
}

export async function getDefaultPlaylistUrl() {
  return SecureStore.getItemAsync(DEFAULT_PLAYLIST_KEY);
}

export async function saveDefaultPlaylistUrl(url) {
  await SecureStore.setItemAsync(DEFAULT_PLAYLIST_KEY, url);
}
