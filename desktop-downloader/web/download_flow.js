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

const ANSI_COLOR = {
  "31": "log-red",
  "32": "log-green",
  "33": "log-yellow",
  "1;31": "log-red",
  "0;31": "log-red",
};

function logFragments(line) {
  const text = String(line || "");
  const ansi = /\u001b\[([0-9;]*)m/g;
  const parts = [];
  let last = 0;
  let className = "";
  let match;
  while ((match = ansi.exec(text))) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index), className });
    const code = match[1];
    className = code === "0" || code === "" ? "" : (ANSI_COLOR[code] || ANSI_COLOR[code.split(";").pop()] || "");
    last = ansi.lastIndex;
  }
  if (last < text.length) parts.push({ text: text.slice(last), className });
  const visible = parts.filter((part) => part.text);
  if (!visible.length) return [{ text: "", className: "" }];
  const plain = visible.map((part) => part.text).join("");
  if (visible.some((part) => part.className)) return visible;
  if (/could not |error:|unexpected error/i.test(plain)) {
    return [{ text: plain, className: "log-red" }];
  }
  if (/^(saved|already in library|rekordbox playlist|rekordbox stem|dj sidecar|beatport catalog)\b/i.test(plain)) {
    return [{ text: plain, className: "log-green" }];
  }
  return visible;
}

const DownloadFlow = {
  detectSourceFromUrl,
  isYoutubePlaylistUrl,
  preparedTracksForPayload,
  shouldStartAfterPaste,
  shouldIgnoreJobSnapshot,
  logFragments,
};

if (typeof module === "object" && module.exports) {
  module.exports = DownloadFlow;
}
if (typeof globalThis !== "undefined") {
  globalThis.DownloadFlow = DownloadFlow;
}
