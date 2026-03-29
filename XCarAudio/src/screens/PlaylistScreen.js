import React from 'react';
import { View, Text, FlatList, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { usePlaylistTracks } from '../hooks/useAudioStation';
import { getStreamUrl } from '../services/audioStation';
import { loadPlaylist, playTrackAt } from '../services/player';

export default function PlaylistScreen({ route, navigation }) {
  const { playlist } = route.params;
  const { data: tracks, isLoading, error } = usePlaylistTracks(playlist.id);

  async function handleTrackPress(index) {
    const playerTracks = await Promise.all(
      tracks.map(async (t) => ({
        id: t.id,
        url: await getStreamUrl(t.id),
        title: t.title,
        artist: t.additional?.song_tag?.artist || '',
        album: t.additional?.song_tag?.album || '',
      }))
    );
    await loadPlaylist(playerTracks);
    await playTrackAt(index);
    navigation.navigate('Player');
  }

  if (isLoading) return <ActivityIndicator style={styles.center} />;
  if (error) return <Text style={styles.error}>Failed to load tracks: {error.message}</Text>;

  return (
    <FlatList
      data={tracks}
      keyExtractor={(item) => item.id}
      renderItem={({ item, index }) => (
        <TouchableOpacity style={styles.row} onPress={() => handleTrackPress(index)}>
          <Text style={styles.title}>{item.title}</Text>
          <Text style={styles.sub}>{item.additional?.song_tag?.artist || ''}</Text>
        </TouchableOpacity>
      )}
      contentContainerStyle={styles.list}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  error: { color: 'red', padding: 16 },
  list: { padding: 8 },
  row: {
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#333',
  },
  title: { fontSize: 16, color: '#fff' },
  sub: { fontSize: 12, color: '#888', marginTop: 2 },
});
