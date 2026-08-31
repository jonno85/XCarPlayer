/**
 * Full-screen modal WebView for Spotify login.
 * On Done: tries to extract sp_dc from the WKWebView cookie store first,
 * then falls back to probing the get_access_token endpoint.
 */

import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Modal, StyleSheet,
  Pressable, Text, View,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import CookieManager from '@react-native-cookies/cookies';

const LOGIN_SOURCE = { uri: 'https://accounts.spotify.com/login' };
const OPEN_SPOTIFY_SOURCE = { uri: 'https://open.spotify.com' };
const BLANK_SOURCE = { html: '<html><body style="background:#111"></body></html>' };

// Intercepts Spotify's own get_access_token fetch on page load.
const INTERCEPT_TOKEN = `
  (function() {
    const _fetch = window.fetch;
    window.fetch = function(input, init) {
      const url = typeof input === 'string' ? input : (input?.url ?? '');
      const p = _fetch.apply(this, arguments);
      if (url.includes('get_access_token')) {
        p.then(r => r.clone().json())
          .then(data => {
            window.ReactNativeWebView.postMessage(JSON.stringify({
              type: 'token_probe',
              accessToken: data.accessToken ?? null,
              isAnonymous: data.isAnonymous ?? true,
              expirationTimestampMs: data.expirationTimestampMs ?? null,
            }));
          })
          .catch(() => {});
      }
      return p;
    };
  })();
  true;
`;

const PROBE_TOKEN = `
  (function() {
    fetch('https://open.spotify.com/get_access_token?reason=transport&productType=web_player', {
      credentials: 'include'
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        window.ReactNativeWebView.postMessage(JSON.stringify({
          type: 'token_probe',
          accessToken: data.accessToken ?? null,
          isAnonymous: data.isAnonymous ?? true,
          expirationTimestampMs: data.expirationTimestampMs ?? null,
        }));
      })
      .catch(function(err) {
        window.ReactNativeWebView.postMessage(JSON.stringify({
          type: 'token_probe_failed',
          error: String(err),
        }));
      });
  })();
  true;
`;

export default function SpotifyLoginScreen({ visible, onSuccess, onCancel }) {
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState(LOGIN_SOURCE);
  const webViewRef = useRef(null);
  const fallbackTimerRef = useRef(null);
  const dismissedRef = useRef(false);
  const insets = useSafeAreaInsets();
  const sourceUri = source?.uri ?? '';

  useEffect(() => {
    dismissedRef.current = false;
    setSource(visible ? LOGIN_SOURCE : BLANK_SOURCE);
    setLoading(visible);
  }, [visible]);

  function clearFallback() {
    if (fallbackTimerRef.current) {
      clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
  }

  function dismiss(callback) {
    if (dismissedRef.current) return;
    dismissedRef.current = true;
    clearFallback();
    setSource(BLANK_SOURCE);
    setLoading(false);
    setTimeout(callback, 100);
  }

  async function tryFinishWithCookies() {
    try {
      const cookies = await CookieManager.getAll(true);
      console.log('[SpotifyLogin] cookies:', Object.keys(cookies));
      const spDc = cookies?.sp_dc?.value ?? null;
      console.log('[SpotifyLogin] sp_dc found:', !!spDc);
      if (spDc) {
        dismiss(() => onSuccess(null, null, spDc));
        return true;
      }
    } catch (e) {
      console.log('[SpotifyLogin] cookie read error:', e);
    }
    return false;
  }

  function probeSpotifyToken() {
    webViewRef.current?.injectJavaScript(PROBE_TOKEN);
  }

  function handleDone() {
    if (!sourceUri.includes('open.spotify.com')) {
      // Navigate to open.spotify.com first, then finish after load
      setSource(OPEN_SPOTIFY_SOURCE);
      // Fallback: if page doesn't load or probe fails within 5s, try cookies then cancel
      fallbackTimerRef.current = setTimeout(async () => {
        const found = await tryFinishWithCookies();
        if (!found) dismiss(onCancel);
      }, 5000);
      return;
    }

    // Already on open.spotify.com — try cookies immediately, then probe
    fallbackTimerRef.current = setTimeout(() => dismiss(onCancel), 4000);
    tryFinishWithCookies().then((found) => {
      if (!found) probeSpotifyToken();
    });
  }

  function handleMessage(event) {
    try {
      const msg = JSON.parse(event.nativeEvent.data);
      if (msg.type === 'token_probe') {
        console.log('[SpotifyLogin] probe — isAnonymous:', msg.isAnonymous, 'token:', msg.accessToken?.slice(0, 20));
        if (msg.accessToken && !msg.isAnonymous) {
          // Token found — also try to grab sp_dc before dismissing
          tryFinishWithCookies().then((found) => {
            if (!found) {
              dismiss(() => onSuccess(msg.accessToken, msg.expirationTimestampMs ?? null, null));
            }
          });
        }
      } else if (msg.type === 'token_probe_failed') {
        console.log('[SpotifyLogin] probe failed:', msg.error);
      }
    } catch {}
  }

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={() => dismiss(onCancel)}>
      <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
        <View style={[styles.header, { paddingTop: Math.max(insets.top, 10) }]}>
          <View style={styles.headerActions}>
            <Pressable hitSlop={14} onPress={handleDone} style={styles.headerBtn}>
              <Text style={styles.done}>Done</Text>
            </Pressable>
            <Pressable hitSlop={14} onPress={() => dismiss(onCancel)} style={styles.headerBtn}>
              <Text style={styles.cancel}>Cancel</Text>
            </Pressable>
          </View>
        </View>

        {loading && <ActivityIndicator style={styles.spinner} color="#1DB954" />}

        <WebView
          ref={webViewRef}
          source={source}
          injectedJavaScriptBeforeContentLoaded={INTERCEPT_TOKEN}
          onLoadStart={() => setLoading(true)}
          onLoadEnd={() => {
            setLoading(false);
            if ((source?.uri ?? '').includes('open.spotify.com')) {
              probeSpotifyToken();
            }
          }}
          onMessage={handleMessage}
          onContentProcessDidTerminate={() => webViewRef.current?.reload()}
          onNavigationStateChange={(navState) => {
            if (navState.url?.includes('open.spotify.com')) {
              probeSpotifyToken();
            }
          }}
          style={styles.webview}
          sharedCookiesEnabled
          thirdPartyCookiesEnabled
        />
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111' },
  header: {
    zIndex: 2,
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingBottom: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#333',
    backgroundColor: '#111',
  },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  headerBtn: { minHeight: 34, justifyContent: 'center', paddingHorizontal: 6 },
  done: { fontSize: 14, color: '#1DB954', fontWeight: '600' },
  cancel: { fontSize: 14, color: '#888' },
  spinner: { position: 'absolute', top: 80, alignSelf: 'center', zIndex: 1 },
  webview: { flex: 1 },
});
