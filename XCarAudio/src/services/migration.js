/**
 * Migration orchestrator.
 * Sends a playlist URL to the NAS agent, which handles metadata extraction,
 * YouTube search, and download entirely on the NAS.
 */

import { createPlaylistJob } from './nasAgent';

/**
 * @param {string} playlistUrl  - Spotify, YouTube, or Beatport playlist URL
 * @param {string} playlistName - target folder / playlist name in AudioStation
 * @returns {Promise<object>}   - playlist job object (single job, poll with getPlaylistJob)
 */
export async function startPlaylistMigration(playlistUrl, playlistName) {
  return createPlaylistJob({ playlistUrl, playlistName });
}
