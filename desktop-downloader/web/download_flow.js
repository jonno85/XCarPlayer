"use strict";

function detectSourceFromUrl(url) {
  const value = String(url || "").trim().toLowerCase();
  if (!value) return "";
  if (value.includes("open.spotify.com") || value.startsWith("spotify:")) return "spotify";
  if (value.includes("youtube.com") || value.includes("youtu.be")) return "youtube";
  if (value.includes("beatport.com")) return "beatport";
  return "";
}

function isYoutubePlaylistUrl(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^www\./, "");
    if (host !== "youtube.com" && host !== "m.youtube.com" && host !== "music.youtube.com" && host !== "youtu.be") {
      return false;
    }
    return parsed.pathname.includes("/playlist");
  } catch (_error) {
    return /youtube\.com\/playlist|youtu\.be\/playlist/i.test(String(url || ""));
  }
}

function preparedTracksForPayload(state, url) {
  if (state.source === "search" && state.selectedSearch) {
    return [{
      title: state.selectedSearch.title,
      direct_url: state.selectedSearch.url,
      duration_ms: state.selectedSearch.duration_ms,
      released_at: state.selectedSearch.released_at,
      included: true,
    }];
  }
  if (
    state.previewSource !== state.source
    || !Array.isArray(state.previewTracks)
    || !state.previewTracks.length
  ) {
    return undefined;
  }
  const previewed = String(state.previewUrl || "");
  if (/^(https?:\/\/|spotify:)/i.test(previewed) && previewed !== url) {
    return undefined;
  }
  return state.previewTracks;
}

function shouldStartAfterPaste({ working, lastJobFinished, outputDir, rightsConfirmed }) {
  return Boolean(lastJobFinished && !working && outputDir && rightsConfirmed);
}

function shouldIgnoreJobSnapshot(job, currentJobId) {
  return Boolean(currentJobId && job && job.id && job.id !== currentJobId);
}

const DownloadFlow = {
  detectSourceFromUrl,
  isYoutubePlaylistUrl,
  preparedTracksForPayload,
  shouldStartAfterPaste,
  shouldIgnoreJobSnapshot,
};

if (typeof module === "object" && module.exports) {
  module.exports = DownloadFlow;
}
if (typeof globalThis !== "undefined") {
  globalThis.DownloadFlow = DownloadFlow;
}
