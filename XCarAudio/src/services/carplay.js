import { HybridAutoPlay, ListTemplate, NowPlayingTemplate } from '@iternio/react-native-auto-play';
import { getPlaylists, getPlaylistTracks, getStreamUrl } from './audioStation';
import { loadPlaylist, playTrackAt } from './player';

// CarPlay UI for @iternio/react-native-auto-play
// This service handles both CarPlay and Android Auto!

export default function registerAutoPlay() {
  HybridAutoPlay.addListener('didConnect', onConnect);
  HybridAutoPlay.addListener('didDisconnect', onDisconnect);
}

async function onConnect() {
  try {
    const playlists = await getPlaylists();
    const rootTemplate = buildPlaylistListTemplate(playlists);
    rootTemplate.setRootTemplate();
  } catch (error) {
    console.error('[AutoPlay] Error on connect:', error);
  }
}

function onDisconnect() {
  console.log('[AutoPlay] Disconnected from car head unit');
}

function buildPlaylistListTemplate(playlists) {
  return new ListTemplate({
    title: { text: 'X Car Audio' },
    sections: [
      {
        items: playlists.map((pl) => ({
          title: { text: pl.name },
          subtitle: { text: `${pl.additional?.songs?.length ?? 0} tracks` },
          onPress: async () => {
            await openPlaylist(pl);
          },
        })),
      },
    ],
  });
}

async function openPlaylist(playlist) {
  const tracks = await getPlaylistTracks(playlist.id);
  const trackListTemplate = new ListTemplate({
    title: { text: playlist.name },
    sections: [
      {
        items: tracks.map((t, index) => ({
          title: { text: t.title },
          subtitle: { text: t.additional?.song_tag?.artist || '' },
          onPress: async () => {
            const playerTracks = await Promise.all(
              tracks.map(async (st) => ({
                id: st.id,
                url: await getStreamUrl(st.id),
                title: st.title,
                artist: st.additional?.song_tag?.artist || '',
                album: st.additional?.song_tag?.album || '',
              }))
            );
            await loadPlaylist(playerTracks);
            await playTrackAt(index);
            
            // Push Now Playing template
            new NowPlayingTemplate({}).push();
          },
        })),
      },
    ],
  });

  trackListTemplate.push();
}
