import React from 'react';
import { View, Text, FlatList, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { usePlaylists } from '../hooks/useAudioStation';

export default function LibraryScreen({ navigation }) {
  const { data: playlists, isLoading, error } = usePlaylists();

  if (isLoading) return <ActivityIndicator style={styles.center} />;
  if (error) return <Text style={styles.error}>Failed to load playlists: {error.message}</Text>;

  return (
    <FlatList
      data={playlists}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <TouchableOpacity
          style={styles.row}
          onPress={() => navigation.navigate('Playlist', { playlist: item })}
        >
          <Text style={styles.title}>{item.name}</Text>
          <Text style={styles.sub}>{item.additional?.songs?.length ?? ''} tracks</Text>
        </TouchableOpacity>
      )}
      contentContainerStyle={styles.list}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  error: { flex: 1, color: 'red', padding: 16 },
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
