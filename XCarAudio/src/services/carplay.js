import { CarPlay, ListTemplate, NowPlayingTemplate } from 'react-native-carplay';
import { getPlaylists, getPlaylistTracks, getStreamUrl } from './audioStation';
import { loadPlaylist, playTrackAt } from './player';

// CarPlay UI: root list of playlists → track list → NowPlaying
// Apple restricts CarPlay templates strictly — no custom UI

export function registerCarPlay() {
  CarPlay.registerOnConnect(onConnect);
  CarPlay.registerOnDisconnect(onDisconnect);
}

async function onConnect() {
  const playlists = await getPlaylists();
  const rootTemplate = buildPlaylistListTemplate(playlists);
  CarPlay.setRootTemplate(rootTemplate);
}

function onDisconnect() {
  // Nothing to tear down — CarPlay handles cleanup
}

function buildPlaylistListTemplate(playlists) {
  return new ListTemplate({
    id: 'playlists',
    title: 'X Car Audio',
    sections: [
      {
        items: playlists.map((pl) => ({
          id: pl.id,
          text: pl.name,
          detailText: `${pl.additional?.songs?.length ?? ''} tracks`,
        })),
      },
    ],
    onItemSelect: async ({ index }) => {
      const playlist = playlists[index];
      await openPlaylist(playlist);
    },
  });
}

async function openPlaylist(playlist) {
  const tracks = await getPlaylistTracks(playlist.id);
  const trackListTemplate = new ListTemplate({
    id: `playlist-${playlist.id}`,
    title: playlist.name,
    sections: [
      {
        items: tracks.map((t) => ({
          id: t.id,
          text: t.title,
          detailText: t.additional?.song_tag?.artist || '',
        })),
      },
    ],
    onItemSelect: async ({ index }) => {
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
      CarPlay.pushTemplate(new NowPlayingTemplate({}));
    },
  });

  CarPlay.pushTemplate(trackListTemplate);
}
