/**
 * Migration orchestrator.
 * Takes a playlist (name + tracks) and queues each track as a NAS agent job.
 * Returns an array of job objects that the UI can poll.
 */

import { createDownloadJob } from './nasAgent';

/**
 * @param {string} playlistName
 * @param {{ title: string, artist: string }[]} tracks
 * @param {(progress: number) => void} onProgress - called with 0..1 as jobs are queued
 * @returns {Promise<{ jobId: string, title: string, artist: string }[]>}
 */
export async function startMigration(playlistName, tracks, onProgress) {
  const results = [];

  for (let i = 0; i < tracks.length; i++) {
    const track = tracks[i];
    try {
      const job = await createDownloadJob({
        playlistName,
        title: track.title,
        artist: track.artist,
      });
      results.push({ jobId: job.id, title: track.title, artist: track.artist, status: job.status });
    } catch (e) {
      results.push({ jobId: null, title: track.title, artist: track.artist, status: 'queue_failed', error: e.message });
    }
    onProgress((i + 1) / tracks.length);
  }

  return results;
}
