/**
 * Migration flow:
 * 1. User picks a source (Spotify)
 * 2. Selects a playlist
 * 3. Taps "Migrate" → jobs queued on NAS agent
 * 4. Progress screen polls job status
 */

import React, { useState } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, ActivityIndicator, StyleSheet, Alert,
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { useSpotifyAuth, exchangeSpotifyCode, getSpotifyPlaylists, getSpotifyPlaylistTracks } from '../services/spotify';
import { startMigration } from '../services/migration';
import MigrationJobsScreen from './MigrationJobsScreen';

export default function MigrationScreen() {
  const [step, setStep] = useState('source'); // source | playlists | jobs
  const [jobs, setJobs] = useState([]);
  const [queueProgress, setQueueProgress] = useState(0);
  const [queuingActive, setQueuingActive] = useState(false);

  const { request, response, promptAsync, redirectUri } = useSpotifyAuth();

  // Kick off Spotify OAuth when response arrives
  React.useEffect(() => {
    if (response?.type === 'success') {
      const { code } = response.params;
      exchangeSpotifyCode(code, request.codeVerifier, redirectUri)
        .then(() => setStep('playlists'))
        .catch((e) => Alert.alert('Spotify auth failed', e.message));
    }
  }, [response]);

  async function handleMigrate(playlist) {
    setQueuingActive(true);
    setStep('jobs');
    try {
      const tracks = await getSpotifyPlaylistTracks(playlist.id);
      const queued = await startMigration(playlist.name, tracks, setQueueProgress);
      setJobs(queued);
    } catch (e) {
      Alert.alert('Migration failed', e.message);
    } finally {
      setQueuingActive(false);
    }
  }

  if (step === 'jobs') {
    return (
      <MigrationJobsScreen
        jobs={jobs}
        queueProgress={queueProgress}
        queuingActive={queuingActive}
        onBack={() => setStep('source')}
      />
    );
  }

  if (step === 'playlists') {
    return <SpotifyPlaylistPicker onSelect={handleMigrate} onBack={() => setStep('source')} />;
  }

  // Step: source selection
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Migrate a Playlist</Text>
      <Text style={styles.sub}>Choose a source to import from</Text>

      <TouchableOpacity style={styles.sourceBtn} onPress={() => promptAsync()}>
        <Text style={styles.sourceBtnText}>Spotify</Text>
        <Text style={styles.sourceSub}>Import playlist metadata via OAuth</Text>
      </TouchableOpacity>

      <View style={[styles.sourceBtn, styles.sourceBtnDisabled]}>
        <Text style={styles.sourceBtnText}>Beatport</Text>
        <Text style={styles.sourceSub}>Coming in Phase 3</Text>
      </View>
    </View>
  );
}

function SpotifyPlaylistPicker({ onSelect, onBack }) {
  const { data: playlists, isLoading, error } = useQuery({
    queryKey: ['spotify-playlists'],
    queryFn: getSpotifyPlaylists,
  });

  if (isLoading) return <ActivityIndicator style={styles.center} />;
  if (error) return <Text style={styles.error}>{error.message}</Text>;

  return (
    <View style={{ flex: 1, backgroundColor: '#111' }}>
      <TouchableOpacity onPress={onBack} style={styles.backBtn}>
        <Text style={styles.backText}>← Back</Text>
      </TouchableOpacity>
      <Text style={styles.heading}>Select Playlist</Text>
      <FlatList
        data={playlists}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => onSelect(item)}>
            <Text style={styles.title}>{item.name}</Text>
            <Text style={styles.sub}>{item.tracks?.total ?? ''} tracks</Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111', padding: 24 },
  center: { flex: 1 },
  heading: { fontSize: 20, color: '#fff', fontWeight: '700', marginBottom: 8, paddingHorizontal: 24, paddingTop: 16 },
  sub: { fontSize: 13, color: '#888', marginBottom: 24, paddingHorizontal: 24 },
  sourceBtn: {
    backgroundColor: '#1a1a1a',
    borderRadius: 10,
    padding: 18,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#333',
  },
  sourceBtnDisabled: { opacity: 0.4 },
  sourceBtnText: { fontSize: 16, color: '#fff', fontWeight: '600' },
  sourceSub: { fontSize: 12, color: '#888', marginTop: 4 },
  backBtn: { paddingHorizontal: 24, paddingTop: 16 },
  backText: { color: '#1DB954', fontSize: 14 },
  row: {
    paddingVertical: 14, paddingHorizontal: 24,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#333',
  },
  title: { fontSize: 16, color: '#fff' },
  error: { color: 'red', padding: 24 },
});
