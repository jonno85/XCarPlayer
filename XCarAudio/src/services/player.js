import TrackPlayer, { Capability, AppKilledPlaybackBehavior } from 'react-native-track-player';

export async function setupPlayer() {
  await TrackPlayer.setupPlayer({
    // Keep playback active when app is killed (iOS background audio)
    android: {
      appKilledPlaybackBehavior: AppKilledPlaybackBehavior.StopPlaybackAndRemoveNotification,
    },
  });

  await TrackPlayer.updateOptions({
    capabilities: [
      Capability.Play,
      Capability.Pause,
      Capability.SkipToNext,
      Capability.SkipToPrevious,
      Capability.Stop,
      Capability.SeekTo,
    ],
    compactCapabilities: [Capability.Play, Capability.Pause, Capability.SkipToNext],
    progressUpdateEventInterval: 1,
  });
}

export async function loadPlaylist(tracks) {
  await TrackPlayer.reset();
  await TrackPlayer.add(tracks);
  await TrackPlayer.play();
}

export async function playTrackAt(index) {
  await TrackPlayer.skip(index);
  await TrackPlayer.play();
}
