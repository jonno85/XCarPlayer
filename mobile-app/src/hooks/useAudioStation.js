import { useQuery } from '@tanstack/react-query';
import { getPlaylists, getPlaylistTracks } from '../services/audioStation';

export function usePlaylists() {
  return useQuery({
    queryKey: ['playlists'],
    queryFn: getPlaylists,
    staleTime: 60_000,
  });
}

export function usePlaylistTracks(playlistId) {
  return useQuery({
    queryKey: ['playlist', playlistId],
    queryFn: () => getPlaylistTracks(playlistId),
    enabled: !!playlistId,
    staleTime: 60_000,
  });
}
