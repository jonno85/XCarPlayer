/**
 * Shows live progress for an active playlist migration.
 * Polls the NAS agent every 3 seconds until the job is done or failed.
 * On completion, auto-creates (or updates) the playlist in DS Audio.
 */

import React, { useEffect, useRef, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import { getPlaylistJob } from '../services/nasAgent';
import { getPlaylists, createPlaylist, addSongs, searchSongs } from '../services/audioStation';

const POLL_INTERVAL_MS = 3000;
const SONG_BATCH_SIZE = 100;

const SOURCE_LABEL = { spotify: 'Spotify', youtube: 'YouTube', beatport: 'Beatport', unknown: '' };

function chunks(arr, size) {
  const out = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

function normalizeErrorMessage(error) {
  if (!error) return 'Failed to create playlist';
  if (error.code === 'OTP_REQUIRED' || error.message === 'Two-factor authentication required') {
    return 'NAS session expired — go to Settings to re-login (2FA required)';
  }
  return error.message || 'Failed to create playlist';
}

export default function MigrationJobsScreen({ job: initialJob, onBack }) {
  const [job, setJob] = useState(initialJob);
  const [playlistStatus, setPlaylistStatus] = useState(null); // null | 'creating' | 'done' | string (error)
  const playlistCreatedRef = useRef(false);

  const isDone = job.status === 'done' || job.status === 'failed';

  // Poll job status
  useEffect(() => {
    if (isDone) return;

    const timer = setInterval(async () => {
      try {
        const updated = await getPlaylistJob(job.id);
        setJob(updated);
      } catch (e) {
        // Keep polling; transient network errors are expected on QuickConnect
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [job.id, isDone]);

  // Auto-create DS Audio playlist when download completes
  useEffect(() => {
    if (job.status !== 'done' || playlistCreatedRef.current) return;
    playlistCreatedRef.current = true;
    createDsAudioPlaylist(job.playlist_name).catch(() => {});
  }, [job.status, job.playlist_name]);

  async function createDsAudioPlaylist(name) {
    setPlaylistStatus('creating');
    try {
      const existing = await getPlaylists();
      let playlist = existing.find((p) => p.name === name);
      if (!playlist) {
        playlist = await createPlaylist(name);
      }

      const songs = await searchSongs(name);
      if (songs.length > 0) {
        const uniqueSongIds = [...new Set(songs.map((s) => s.id).filter(Boolean))];
        for (const batch of chunks(uniqueSongIds, SONG_BATCH_SIZE)) {
          await addSongs(playlist.id, batch);
        }
      }

      setPlaylistStatus('done');
    } catch (e) {
      playlistCreatedRef.current = false;
      setPlaylistStatus(normalizeErrorMessage(e));
    }
  }

  const total = job.tracks_total;
  const done = job.tracks_done;
  const failed = job.tracks_failed;
  const progress = total > 0 ? done / total : 0;

  return (
    <View style={styles.container}>
      <TouchableOpacity onPress={onBack} style={styles.backBtn}>
        <Text style={styles.backText}>← New Migration</Text>
      </TouchableOpacity>

      <View style={styles.summary}>
        <View style={styles.headingRow}>
          <Text style={styles.heading}>{job.playlist_name}</Text>
          {job.source ? <Text style={styles.sourceBadge}>{SOURCE_LABEL[job.source] || job.source}</Text> : null}
        </View>

        {/* Progress bar */}
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${Math.round(progress * 100)}%` }]} />
        </View>

        {/* Current track */}
        {job.current_track ? (
          <Text style={styles.currentTrack} numberOfLines={1}>⬇ {job.current_track}</Text>
        ) : null}

        {/* Counts */}
        <Text style={styles.counts}>
          <Text style={{ color: '#1DB954' }}>{done} done</Text>
          {'  ·  '}
          <Text style={{ color: '#e74c3c' }}>{failed} failed</Text>
          {'  ·  '}
          <Text style={{ color: '#888' }}>{total} total</Text>
        </Text>

        {/* Overall status */}
        {job.status === 'done' && (
          <Text style={styles.statusDone}>Download complete</Text>
        )}
        {job.status === 'failed' && job.error && (
          <Text style={styles.statusFailed}>{job.error}</Text>
        )}

        {/* DS Audio playlist creation status */}
        {playlistStatus === 'creating' && (
          <Text style={styles.playlistStatus}>Adding to DS Audio…</Text>
        )}
        {playlistStatus === 'done' && (
          <Text style={[styles.playlistStatus, { color: '#1DB954' }]}>Playlist added to DS Audio</Text>
        )}
        {playlistStatus && playlistStatus !== 'creating' && playlistStatus !== 'done' && (
          <>
            <Text style={[styles.playlistStatus, { color: '#e74c3c' }]}>Could not create playlist: {playlistStatus}</Text>
            <TouchableOpacity
              style={styles.retryBtn}
              onPress={() => {
                playlistCreatedRef.current = true;
                createDsAudioPlaylist(job.playlist_name).catch(() => {});
              }}
            >
              <Text style={styles.retryText}>Retry Playlist Sync</Text>
            </TouchableOpacity>
          </>
        )}
      </View>

      {/* Failed tracks */}
      {job.failed_tracks?.length > 0 && (
        <View style={styles.failedSection}>
          <Text style={styles.failedHeading}>Failed tracks</Text>
          <FlatList
            data={job.failed_tracks}
            keyExtractor={(_, i) => String(i)}
            renderItem={({ item }) => (
              <View style={styles.failedRow}>
                <Text style={styles.failedTitle} numberOfLines={1}>{item.title}</Text>
                <Text style={styles.failedError} numberOfLines={1}>{item.error}</Text>
              </View>
            )}
          />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111' },
  backBtn: { paddingHorizontal: 24, paddingTop: 16 },
  backText: { color: '#1DB954', fontSize: 14 },
  summary: { paddingHorizontal: 24, paddingVertical: 16 },
  headingRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  heading: { fontSize: 20, color: '#fff', fontWeight: '700', marginRight: 10 },
  sourceBadge: { fontSize: 11, color: '#888', backgroundColor: '#222', borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  progressTrack: { height: 4, backgroundColor: '#333', borderRadius: 2, marginBottom: 10 },
  progressFill: { height: 4, backgroundColor: '#1DB954', borderRadius: 2 },
  currentTrack: { fontSize: 12, color: '#f0a500', marginBottom: 8 },
  counts: { fontSize: 13, marginBottom: 8 },
  statusDone: { fontSize: 13, color: '#1DB954', marginBottom: 4 },
  statusFailed: { fontSize: 12, color: '#e74c3c', marginBottom: 4 },
  playlistStatus: { fontSize: 12, color: '#888', marginTop: 4 },
  retryBtn: {
    marginTop: 8,
    alignSelf: 'flex-start',
    backgroundColor: '#333',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  retryText: { color: '#fff', fontSize: 12, fontWeight: '600' },
  failedSection: { flex: 1, paddingHorizontal: 24 },
  failedHeading: { fontSize: 13, color: '#aaa', marginBottom: 8, fontWeight: '600' },
  failedRow: {
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#222',
  },
  failedTitle: { fontSize: 13, color: '#fff' },
  failedError: { fontSize: 11, color: '#e74c3c', marginTop: 2 },
});
