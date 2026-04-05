import TrackPlayer, { Event } from 'react-native-track-player';

export async function playbackService() {
  TrackPlayer.addEventListener(Event.RemotePlay, () => TrackPlayer.play());
  TrackPlayer.addEventListener(Event.RemotePause, () => TrackPlayer.pause());
  TrackPlayer.addEventListener(Event.RemoteStop, () => TrackPlayer.stop());
  TrackPlayer.addEventListener(Event.RemoteNext, () => TrackPlayer.skipToNext());
  TrackPlayer.addEventListener(Event.RemotePrevious, () => TrackPlayer.skipToPrevious());
  TrackPlayer.addEventListener(Event.RemoteSeek, (event) => TrackPlayer.seekTo(event.position));
  TrackPlayer.addEventListener(Event.RemoteJumpForward, async (event) => {
    const pos = await TrackPlayer.getPosition();
    await TrackPlayer.seekTo(pos + (event.interval || 15));
  });
  TrackPlayer.addEventListener(Event.RemoteJumpBackward, async (event) => {
    const pos = await TrackPlayer.getPosition();
    await TrackPlayer.seekTo(pos - (event.interval || 15));
  });
}
