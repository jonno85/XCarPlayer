/**
 * Migration flow:
 * 1. User pastes a playlist URL (Spotify, YouTube, or Beatport)
 * 2. Source is auto-detected from the URL
 * 3. User optionally edits the playlist name (used as AudioStation folder)
 * 4. Taps "Migrate" → single job queued on NAS agent
 * 5. Progress screen polls job status
 */

import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ActivityIndicator, StyleSheet, Alert,
} from 'react-native';
import { startPlaylistMigration } from '../services/migration';
import MigrationJobsScreen from './MigrationJobsScreen';
import {
  getValidSpotifyToken, getSpotifyAuthMode, getSpotifyManualCredential, getDefaultPlaylistUrl,
} from '../services/spotifyAuth';

function detectSource(url) {
  if (!url) return null;
  if (url.includes('spotify.com') || url.startsWith('spotify:')) return 'Spotify';
  if (url.includes('youtube.com') || url.includes('youtu.be')) return 'YouTube';
  if (url.includes('beatport.com')) return 'Beatport';
  return null;
}

function defaultPlaylistName(url) {
  try {
    const source = detectSource(url);
    if (source) return `${source} Playlist`;
  } catch {}
  return '';
}

export default function MigrationScreen() {
  const [playlistUrl, setPlaylistUrl] = useState('https://open.spotify.com/playlist/5jkcDwuWgkdxndfSZcVOAu?si=xWKCZPJ5SOSOh5hDmIC_jQ');
  const [playlistName, setPlaylistName] = useState('2026');
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState(null);

  useEffect(() => {
    getDefaultPlaylistUrl().then((url) => { if (url) setPlaylistUrl(url); });
  }, []);

  const source = detectSource(playlistUrl);

  function handleUrlChange(text) {
    setPlaylistUrl(text);
    if (!playlistName) {
      setPlaylistName(defaultPlaylistName(text));
    }
  }

  async function runMigrate() {
    setLoading(true);
    try {
      const created = await startPlaylistMigration(playlistUrl.trim(), playlistName.trim());
      setJob(created);
    } catch (e) {
      Alert.alert('Migration failed', e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleMigrate() {
    if (!playlistUrl.trim()) { Alert.alert('Enter a playlist URL'); return; }
    if (!playlistName.trim()) { Alert.alert('Enter a playlist name'); return; }
    if (!source) { Alert.alert('Unsupported URL', 'Paste a Spotify, YouTube, or Beatport playlist URL.'); return; }

    if (source === 'Spotify') {
      const [token, authMode, manualCredential] = await Promise.all([
        getValidSpotifyToken(),
        getSpotifyAuthMode(),
        getSpotifyManualCredential(),
      ]);
      const hasCredential = authMode === 'manual' ? !!manualCredential?.trim() : !!token;
      if (!hasCredential) {
        Alert.alert(
          'Spotify not connected',
          authMode === 'manual'
            ? 'No manual credential is set. Go to Settings → Spotify to paste a token or sp_dc cookie. Private playlists will fail without it.'
            : 'Your Spotify session has expired or was never set up. Go to Settings → Spotify to reconnect. Private playlists will fail without it.',
          [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Continue anyway', onPress: runMigrate },
          ]
        );
        return;
      }
    }
    runMigrate();
  }

  if (job) {
    return (
      <MigrationJobsScreen
        job={job}
        onBack={() => { setJob(null); setPlaylistUrl(''); setPlaylistName(''); }}
      />
    );
  }

  return (
    <>
    <View style={styles.container}>
      <Text style={styles.heading}>Migrate a Playlist</Text>
      <Text style={styles.sub}>Paste a playlist URL to download it to your NAS</Text>

      <Text style={styles.label}>Playlist URL</Text>
      <Text style={styles.hint}>Spotify public playlists can work via backend app credentials; private playlists need user auth</Text>
      <TextInput
        style={styles.input}
        placeholder="https://open.spotify.com/playlist/… or YouTube / Beatport"
        placeholderTextColor="#555"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        value={playlistUrl}
        onChangeText={handleUrlChange}
      />
      {source ? (
        <Text style={styles.sourceBadge}>{source} detected</Text>
      ) : playlistUrl.length > 0 ? (
        <Text style={styles.sourceBadgeUnknown}>Unsupported URL</Text>
      ) : null}

      <Text style={[styles.label, { marginTop: 20 }]}>Playlist Name</Text>
      <Text style={styles.hint}>Used as the folder name in AudioStation</Text>
      <TextInput
        style={styles.input}
        placeholder="My Playlist"
        placeholderTextColor="#555"
        value={playlistName}
        onChangeText={setPlaylistName}
      />

      <TouchableOpacity
        style={[styles.btn, (!source || loading) && styles.btnDisabled]}
        onPress={handleMigrate}
        disabled={!source || loading}
      >
        {loading
          ? <ActivityIndicator color="#fff" />
          : <Text style={styles.btnText}>Migrate</Text>
        }
      </TouchableOpacity>
    </View>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111', padding: 24 },
  heading: { fontSize: 20, color: '#fff', fontWeight: '700', marginBottom: 8 },
  sub: { fontSize: 13, color: '#888', marginBottom: 24 },
  label: { color: '#aaa', fontSize: 12, marginBottom: 4 },
  hint: { color: '#555', fontSize: 11, marginBottom: 4 },
  input: {
    backgroundColor: '#222', color: '#fff', borderRadius: 8, padding: 12, fontSize: 14,
  },
  sourceBadge: { fontSize: 11, color: '#1DB954', marginTop: 6 },
  sourceBadgeUnknown: { fontSize: 11, color: '#e74c3c', marginTop: 6 },
  btn: {
    marginTop: 32, backgroundColor: '#1DB954', borderRadius: 8, padding: 14, alignItems: 'center',
  },
  btnDisabled: { opacity: 0.4 },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '600' },
});
