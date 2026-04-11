import { useEffect, useState } from 'react';
import { ScrollView, Switch, Text, TextInput, TouchableOpacity, StyleSheet, Alert, View, Platform } from 'react-native';
import { login, logout } from '../services/audioStation';
import { saveAgentUrl, saveAgentKey, testAgentConnection, getAgentUrl, getAgentKey } from '../services/nasAgent';
import {
  getValidSpotifyToken, getSpotifyToken, saveSpotifyToken, clearSpotifyToken,
  getSpotifyAuthMode, setSpotifyAuthMode,
  getSpotifyManualCredential, saveSpotifyManualCredential, clearSpotifyManualCredential,
  getDefaultPlaylistUrl, saveDefaultPlaylistUrl,
} from '../services/spotifyAuth';
import SpotifyLoginScreen from './SpotifyLoginScreen';
import { useQueryClient } from '@tanstack/react-query';

export default function SettingsScreen() {
  const queryClient = useQueryClient();
  const [quickConnectId, setQuickConnectId] = useState('jfilippininas');
  const [username, setUsername] = useState('jonathan');
  const [password, setPassword] = useState('Mi?3BsNb');
  const [otpCode, setOtpCode] = useState('');
  const [otpToken, setOtpToken] = useState(null);
  const [loading, setLoading] = useState(false);
  const [agentUrl, setAgentUrl] = useState('');
  const [agentKey, setAgentKey] = useState('');
  const [agentTesting, setAgentTesting] = useState(false);
  const [spotifyConnected, setSpotifyConnected] = useState(false);
  const [showSpotifyLogin, setShowSpotifyLogin] = useState(false);
  const [spotifyAuthMode, setLocalSpotifyAuthMode] = useState('webview');
  const [manualCredential, setManualCredential] = useState('');
  const [spotifyLed, setSpotifyLed] = useState({ color: '#555', label: 'checking…' });
  const [defaultPlaylist, setDefaultPlaylist] = useState('');

  async function refreshSpotifyLed() {
    const [mode, validToken, rawToken, cred] = await Promise.all([
      getSpotifyAuthMode(),
      getValidSpotifyToken(),
      getSpotifyToken(),
      getSpotifyManualCredential(),
    ]);
    if (mode === 'manual') {
      if (cred?.trim()) {
        const isSpDc = cred.trim().startsWith('sp_dc=');
        setSpotifyLed({ color: '#1DB954', label: isSpDc ? 'sp_dc saved' : 'token saved' });
      } else {
        setSpotifyLed({ color: '#e74c3c', label: 'no credential' });
      }
    } else {
      if (validToken) {
        setSpotifyLed({ color: '#1DB954', label: 'token valid' });
      } else if (rawToken) {
        setSpotifyLed({ color: '#f39c12', label: 'token expired' });
      } else {
        setSpotifyLed({ color: '#e74c3c', label: 'not connected' });
      }
    }
  }

  useEffect(() => {
    getValidSpotifyToken().then((v) => setSpotifyConnected(!!v));
    getAgentUrl().then((v) => { if (v) setAgentUrl(v); });
    getAgentKey().then((v) => { if (v) setAgentKey(v); });
    getSpotifyAuthMode().then(setLocalSpotifyAuthMode);
    getSpotifyManualCredential().then((v) => { if (v) setManualCredential(v); });
    getDefaultPlaylistUrl().then((v) => { if (v) setDefaultPlaylist(v); });
    refreshSpotifyLed();
  }, []);

  async function handleLogin() {
    if (!quickConnectId || !username || !password) {
      Alert.alert('Fill in all fields');
      return;
    }
    if (otpToken && !otpCode) {
      Alert.alert('Enter your verification code');
      return;
    }
    setLoading(true);
    try {
      await login(quickConnectId, username, password, otpToken ? { otpCode, token: otpToken } : undefined);
      setOtpCode('');
      setOtpToken(null);
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
      Alert.alert('Connected', 'Successfully connected to your Synology NAS.');
    } catch (e) {
      if (e.code === 'OTP_REQUIRED') {
        setOtpToken(e.otpToken ?? null);
        Alert.alert('Two-factor required', 'Enter the verification code from Synology and tap connect again.');
      } else {
        Alert.alert('Connection failed', e.message);
      }
      console.warn('Login error:', e.message, e?.response?.status, e?.response?.data, e?.code);
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    await logout();
    setOtpCode('');
    setOtpToken(null);
    queryClient.invalidateQueries({ queryKey: ['playlists'] });
    Alert.alert('Disconnected');
  }

  async function handleSpotifySuccess(token, expiryMs, spDc) {
    setShowSpotifyLogin(false);

    if (spDc && !token) {
      // Only sp_dc found (no token probe) — save directly as manual credential
      const credential = `sp_dc=${spDc}`;
      await saveSpotifyManualCredential(credential);
      setManualCredential(credential);
      await setSpotifyAuthMode('manual');
      setLocalSpotifyAuthMode('manual');
      refreshSpotifyLed();
      Alert.alert('Spotify connected', 'sp_dc cookie saved — works for months, no re-login needed.');
      return;
    }

    await saveSpotifyToken(token, expiryMs);
    setSpotifyConnected(true);
    refreshSpotifyLed();

    if (spDc) {
      Alert.alert(
        'Save long-lived credential?',
        'sp_dc cookie found. Save it so you never need to re-login (lasts months vs ~1 hour for the access token).',
        [
          { text: 'Skip', style: 'cancel', onPress: () => Alert.alert('Spotify connected', 'Access token saved (~1 hour).') },
          {
            text: 'Save sp_dc',
            onPress: async () => {
              const credential = `sp_dc=${spDc}`;
              await saveSpotifyManualCredential(credential);
              setManualCredential(credential);
              await setSpotifyAuthMode('manual');
              setLocalSpotifyAuthMode('manual');
              refreshSpotifyLed();
              Alert.alert('Saved', 'sp_dc cookie saved. Future migrations will use it automatically.');
            },
          },
        ]
      );
    } else {
      Alert.alert('Spotify connected', 'Access token saved (~1 hour).');
    }
  }

  async function handleSpotifyDisconnect() {
    await clearSpotifyToken();
    setSpotifyConnected(false);
    refreshSpotifyLed();
  }

  const usingManualSpotifyAuth = spotifyAuthMode === 'manual';

  return (
    <>
    <SpotifyLoginScreen
      visible={showSpotifyLogin}
      onSuccess={handleSpotifySuccess}
      onCancel={() => setShowSpotifyLogin(false)}
    />
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.label}>QuickConnect ID</Text>
      <TextInput
        style={styles.input}
        placeholder="your-nas-id or https://..."
        placeholderTextColor="#555"
        autoCapitalize="none"
        value={quickConnectId}
        onChangeText={setQuickConnectId}
      />

      <Text style={styles.label}>Username</Text>
      <TextInput
        style={styles.input}
        placeholder="admin"
        placeholderTextColor="#555"
        autoCapitalize="none"
        value={username}
        onChangeText={setUsername}
      />

      <Text style={styles.label}>Password</Text>
      <TextInput
        style={styles.input}
        placeholder="••••••••"
        placeholderTextColor="#555"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />

      {otpToken ? (
        <>
          <Text style={styles.label}>Verification Code</Text>
          <TextInput
            style={styles.input}
            placeholder="123456"
            placeholderTextColor="#555"
            keyboardType="number-pad"
            value={otpCode}
            onChangeText={setOtpCode}
          />
        </>
      ) : null}

      <TouchableOpacity style={styles.btn} onPress={handleLogin} disabled={loading}>
        <Text style={styles.btnText}>
          {loading ? 'Connecting…' : otpToken ? 'Verify and Connect' : 'Connect to NAS'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity style={[styles.btn, styles.btnSecondary]} onPress={handleLogout}>
        <Text style={styles.btnText}>Disconnect</Text>
      </TouchableOpacity>

      <Text style={[styles.label, { marginTop: 32 }]}>NAS Agent URL</Text>
      <Text style={styles.hint}>e.g. http://192.168.1.x:8899 or http://yournas.synology.me:8899</Text>
      <TextInput
        style={styles.input}
        placeholder="http://..."
        placeholderTextColor="#555"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        value={agentUrl}
        onChangeText={setAgentUrl}
      />

      <Text style={[styles.label, { marginTop: 16 }]}>NAS Agent API Key</Text>
      <Text style={styles.hint}>Matches API_KEY in your NAS agent .env</Text>
      <TextInput
        style={styles.input}
        placeholder="your-secret-key"
        placeholderTextColor="#555"
        autoCapitalize="none"
        secureTextEntry
        value={agentKey}
        onChangeText={setAgentKey}
      />

      <TouchableOpacity
        style={styles.btn}
        disabled={agentTesting}
        onPress={async () => {
          if (!agentUrl) { Alert.alert('Enter the agent URL'); return; }
          if (!agentKey) { Alert.alert('Enter the API key'); return; }
          setAgentTesting(true);
          try {
            await testAgentConnection(agentUrl, agentKey);
            await Promise.all([saveAgentUrl(agentUrl), saveAgentKey(agentKey)]);
            Alert.alert('Agent connected', `Reachable at ${agentUrl} — settings saved.`);
          } catch (e) {
            Alert.alert('Agent unreachable', e.message);
          } finally {
            setAgentTesting(false);
          }
        }}
      >
        <Text style={styles.btnText}>{agentTesting ? 'Testing…' : 'Save Agent Settings'}</Text>
      </TouchableOpacity>

      <View style={styles.ledRow}>
        <Text style={[styles.label, { marginTop: 0 }]}>Spotify</Text>
        <View style={[styles.led, { backgroundColor: spotifyLed.color }]} />
        <Text style={[styles.ledLabel, { color: spotifyLed.color }]}>{spotifyLed.label}</Text>
      </View>
      <Text style={styles.hint}>Choose whether Spotify migrations use app login or a pasted access token / sp_dc cookie</Text>

      <View style={styles.toggleRow}>
        <View style={styles.toggleLabels}>
          <Text style={styles.toggleTitle}>Manual token / cookie</Text>
          <Text style={styles.hint}>Skip Spotify login and send a pasted access token or sp_dc cookie to the NAS agent</Text>
        </View>
        <Switch
          value={usingManualSpotifyAuth}
          onValueChange={(v) => {
            const nextMode = v ? 'manual' : 'webview';
            setLocalSpotifyAuthMode(nextMode);
            setSpotifyAuthMode(nextMode);
            refreshSpotifyLed();
          }}
          trackColor={{ false: '#333', true: '#1DB954' }}
          thumbColor="#fff"
        />
      </View>

      {usingManualSpotifyAuth ? (
        <>
          <Text style={[styles.label, { marginTop: 16 }]}>Manual Spotify Credential</Text>
          <Text style={styles.hint}>Paste either a bearer access token or an sp_dc cookie value. The app will pass it to the backend for playlist metadata fetches.</Text>
          <TextInput
            style={[styles.input, styles.textArea]}
            placeholder="BQ... or sp_dc=..."
            placeholderTextColor="#555"
            autoCapitalize="none"
            autoCorrect={false}
            value={manualCredential}
            onChangeText={(value) => {
              setManualCredential(value);
              saveSpotifyManualCredential(value);
              refreshSpotifyLed();
            }}
            multiline
          />
          <TouchableOpacity
            style={[styles.btn, styles.btnSecondary, { marginTop: 12 }]}
            onPress={async () => {
              await clearSpotifyManualCredential();
              setManualCredential('');
              Alert.alert('Spotify credential cleared');
            }}
          >
            <Text style={styles.btnText}>Clear Spotify Credential</Text>
          </TouchableOpacity>
        </>
      ) : spotifyConnected ? (
        <>
          <Text style={[styles.hint, { color: '#1DB954', marginTop: 6 }]}>Connected</Text>
          <TouchableOpacity style={[styles.btn, styles.btnSecondary]} onPress={handleSpotifyDisconnect}>
            <Text style={styles.btnText}>Disconnect Spotify</Text>
          </TouchableOpacity>
        </>
      ) : (
        <TouchableOpacity style={styles.btn} onPress={() => setShowSpotifyLogin(true)}>
          <Text style={styles.btnText}>Connect Spotify</Text>
        </TouchableOpacity>
      )}

      <Text style={[styles.label, { marginTop: 16 }]}>Default playlist URL</Text>
      <Text style={styles.hint}>Pre-fills the URL in the Migrate tab</Text>
      <TextInput
        style={styles.input}
        placeholder="https://open.spotify.com/playlist/..."
        placeholderTextColor="#555"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        value={defaultPlaylist}
        onChangeText={setDefaultPlaylist}
      />
      <TouchableOpacity
        style={[styles.btn, styles.btnSecondary, { marginTop: 12 }]}
        onPress={async () => { await saveDefaultPlaylistUrl(defaultPlaylist); Alert.alert('Saved'); }}
      >
        <Text style={styles.btnText}>Save</Text>
      </TouchableOpacity>
    </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111' },
  content: { padding: 24, paddingBottom: 48 },
  label: { color: '#aaa', fontSize: 12, marginTop: 16, marginBottom: 4 },
  input: {
    backgroundColor: '#222',
    color: '#fff',
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
  },
  textArea: { minHeight: 96, textAlignVertical: 'top' },
  btn: {
    marginTop: 24,
    backgroundColor: '#1DB954',
    borderRadius: 8,
    padding: 14,
    alignItems: 'center',
  },
  btnSecondary: { backgroundColor: '#333', marginTop: 12 },
  btnText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  hint: { color: '#555', fontSize: 11, marginBottom: 4 },
  ledRow: {
    flexDirection: 'row', alignItems: 'center', marginTop: 32, gap: 8,
  },
  led: {
    width: 10, height: 10, borderRadius: 5, marginTop: 1,
  },
  ledLabel: {
    fontSize: 11, fontWeight: '600',
  },
  toggleRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginTop: 16,
  },
  toggleLabels: { flex: 1, marginRight: 12 },
  toggleTitle: { color: '#aaa', fontSize: 12, marginBottom: 2 },
});
