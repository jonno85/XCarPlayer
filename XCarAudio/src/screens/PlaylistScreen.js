import React from 'react';
import { View, Text, FlatList, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { usePlaylistTracks } from '../hooks/useAudioStation';
import { getStreamUrl, trackToPlayerItem } from '../services/audioStation';
import { loadPlaylist, playTrackAt } from '../services/player';

export default function PlaylistScreen({ route, navigation }) {
  const { playlist } = route.params;
  const { data: tracks, isLoading, error } = usePlaylistTracks(playlist.id);

  async function handleTrackPress(index) {
    const playerTracks = await Promise.all(
      tracks.map(async (t) => trackToPlayerItem(t, await getStreamUrl(t.id)))
    );
    await loadPlaylist(playerTracks);
    await playTrackAt(index);
    navigation.navigate('Player');
  }

  if (isLoading) return <View style={styles.container}><ActivityIndicator style={styles.center} /></View>;
  if (error) return <View style={styles.container}><Text style={styles.error}>Failed to load tracks: {error.message}</Text></View>;

  return (
    <View style={styles.container}>
      <FlatList
        data={tracks}
        keyExtractor={(item) => item.id}
        renderItem={({ item, index }) => (
          <TouchableOpacity style={styles.row} onPress={() => handleTrackPress(index)}>
            <Text style={styles.title}>{item.title}</Text>
            <Text style={styles.sub}>{item.artist || ''}</Text>
          </TouchableOpacity>
        )}
        contentContainerStyle={styles.list}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111' },
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
