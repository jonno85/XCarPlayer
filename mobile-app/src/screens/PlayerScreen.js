import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import TrackPlayer, { usePlaybackState, useProgress, useActiveTrack, State } from 'react-native-track-player';

export default function PlayerScreen() {
  const track = useActiveTrack();
  const state = usePlaybackState();
  const { position, duration } = useProgress();

  const isPlaying = state.state === State.Playing;

  function fmt(secs) {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  return (
    <View style={styles.container}>
      <View style={styles.artwork} />

      <Text style={styles.title}>{track?.title ?? '—'}</Text>
      <Text style={styles.artist}>{track?.artist ?? ''}</Text>
      <Text style={styles.album}>{track?.album ?? ''}</Text>

      <Text style={styles.progress}>{fmt(position)} / {fmt(duration)}</Text>

      <View style={styles.controls}>
        <TouchableOpacity onPress={() => TrackPlayer.skipToPrevious()} style={styles.btn}>
          <Text style={styles.btnText}>{'|<'}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => (isPlaying ? TrackPlayer.pause() : TrackPlayer.play())}
          style={[styles.btn, styles.btnMain]}
        >
          <Text style={styles.btnText}>{isPlaying ? 'II' : '▶'}</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => TrackPlayer.skipToNext()} style={styles.btn}>
          <Text style={styles.btnText}>{'>|'}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111', alignItems: 'center', justifyContent: 'center', padding: 24 },
  artwork: { width: 200, height: 200, backgroundColor: '#333', borderRadius: 8, marginBottom: 24 },
  title: { fontSize: 20, color: '#fff', fontWeight: '600', textAlign: 'center' },
  artist: { fontSize: 14, color: '#aaa', marginTop: 4 },
  album: { fontSize: 12, color: '#666', marginTop: 2 },
  progress: { fontSize: 12, color: '#666', marginTop: 16 },
  controls: { flexDirection: 'row', alignItems: 'center', marginTop: 32, gap: 24 },
  btn: { padding: 12 },
  btnMain: { padding: 20, backgroundColor: '#1DB954', borderRadius: 40 },
  btnText: { fontSize: 18, color: '#fff' },
});
