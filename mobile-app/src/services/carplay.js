import { HybridAutoPlay, ListTemplate } from '@iternio/react-native-auto-play';
import { getPlaylists, getPlaylistTracks, getSession } from './audioStation';
import CarplayNowPlaying from 'carplay-now-playing';
import TrackPlayer from 'react-native-track-player';


// CarPlay UI for @iternio/react-native-auto-play
// This service handles both CarPlay and Android Auto!

export default function registerAutoPlay() {
  console.log('[AutoPlay] Service registered');
  HybridAutoPlay.addListener('didConnect', onConnect);
  HybridAutoPlay.addListener('didDisconnect', onDisconnect);
  
  // If we are already connected (e.g. app refreshed during active session), trigger onConnect
  if (HybridAutoPlay.isConnected && HybridAutoPlay.isConnected()) {
    console.log('[AutoPlay] Already connected, triggering onConnect manually');
    onConnect();
  }
}

async function onConnect() {
  console.log('[AutoPlay] onConnect triggered');
  try {
    const playlists = await getPlaylists();
    console.log(`[AutoPlay] Fetched ${playlists.length} playlists`);
    const rootTemplate = buildPlaylistListTemplate(playlists);
    rootTemplate.setRootTemplate();
  } catch (error) {
    console.error('[AutoPlay] Error on connect:', error);
    const detailText = getCarplayErrorText(error);
    
    // Show a helpful error template instead of a black screen
    const errorTemplate = new ListTemplate({
      title: { text: 'X Car Audio' },
      sections: {
        type: 'default',
        items: [{
          type: 'default',
          title: { text: 'Not Connected' },
          detailedText: { text: detailText }
        }]
      }
    });
    errorTemplate.setRootTemplate();
  }
}

function getCarplayErrorText(error) {
  const message = String(error?.message || '').toLowerCase();
  if (message.includes('not connected') || message.includes('sign in')) {
    return 'Open Settings on your phone and reconnect to Synology';
  }
  return 'Cannot reach your NAS right now. Check phone network/VPN and try again.';
}

function onDisconnect() {
  console.log('[AutoPlay] Disconnected from car head unit');
}

function buildPlaylistListTemplate(playlists) {
  return new ListTemplate({
    title: { text: 'X Car Audio' },
    sections: {
      type: 'default',
      items: playlists.map((pl) => ({
        type: 'default',
        title: { text: pl.name },
        detailedText: { text: `${pl.additional?.songs?.length ?? 0} tracks` },
        onPress: async () => {
          await openPlaylist(pl);
        },
      })),
    },
  });
}

async function openPlaylist(playlist) {
  const tracks = await getPlaylistTracks(playlist.id);
  const trackListTemplate = new ListTemplate({
    title: { text: playlist.name },
    sections: {
      type: 'default',
      items: tracks.map((t, index) => ({
        type: 'default',
        title: { text: t.title },
        detailedText: { text: t.additional?.song_tag?.artist || '' },
        onPress: async () => {
          console.log(`[AutoPlay] Loading playlist with ${tracks.length} tracks...`);
          const session = await getSession();
          if (!session) {
            console.error('[AutoPlay] No session found');
            return;
          }

          const playerTracks = tracks.map((st) => ({
            id: st.id,
            url: `${session.baseUrl}/webapi/AudioStation/stream.cgi?api=SYNO.AudioStation.Stream&version=2&method=stream&id=${encodeURIComponent(st.id)}&_sid=${encodeURIComponent(session.sid)}`,
            title: st.title,
            artist: st.artist,
            album: '', // Removed for cleaner UI layout
            duration: st.duration || 0,
            artwork: st.cover,
            headers: session.synotoken ? { 'X-SYNO-TOKEN': session.synotoken } : undefined,
          }));
          try {
             console.log(`[AutoPlay] Loading ${playerTracks.length} tracks...`);
             await loadPlaylist(playerTracks);
             
             console.log(`[AutoPlay] Playing track at index ${index}...`);
             await TrackPlayer.skip(index);
             await TrackPlayer.play();
          } catch (e) {
            console.error('[AutoPlay] Playback Error:', e);
          }
          
          setTimeout(async () => {
             try {
               console.log('[AutoPlay] Triggering pushNowPlaying...');
               if (CarplayNowPlaying.pushNowPlaying) {
                 const result = await CarplayNowPlaying.pushNowPlaying();
                 console.log('[AutoPlay] Native Push Result:', result);
               }
             } catch (err) {
               console.error('[AutoPlay] pushNowPlaying error:', err);
             }
          }, 400);
        },
      })),
    },
  });

  trackListTemplate.push();
}
