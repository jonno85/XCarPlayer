"use strict";

const assert = require("assert");
const flow = require("../web/download_flow.js");

assert.strictEqual(
  flow.shouldStartAfterPaste({
    working: false,
    lastJobFinished: true,
    outputDir: "/music",
    rightsConfirmed: true,
  }),
  true,
  "pasting a playlist after a finished job should start the next download",
);

assert.strictEqual(
  flow.shouldStartAfterPaste({
    working: true,
    lastJobFinished: false,
    outputDir: "/music",
    rightsConfirmed: true,
  }),
  false,
  "a running job should not be replaced until it finishes",
);

assert.strictEqual(
  flow.preparedTracksForPayload({
    source: "beatport",
    previewSource: "",
    previewUrl: "",
    previewTracks: [],
    selectedSearch: null,
  }, "https://www.beatport.com/playlist/new/123"),
  undefined,
  "a new Beatport/Spotify URL must download without requiring another preview",
);

assert.strictEqual(
  flow.preparedTracksForPayload({
    source: "beatport",
    previewSource: "beatport",
    previewUrl: "https://www.beatport.com/playlist/old/1",
    previewTracks: [{ title: "Old track", included: true }],
    selectedSearch: null,
  }, "https://www.beatport.com/playlist/new/2"),
  undefined,
  "tracks from the previous playlist must not be reused after a new URL is pasted",
);

assert.deepStrictEqual(
  flow.preparedTracksForPayload({
    source: "text",
    previewSource: "text",
    previewUrl: "songs.txt",
    previewTracks: [{ title: "A", included: true }],
    selectedSearch: null,
  }, ""),
  [{ title: "A", included: true }],
);

assert.deepStrictEqual(
  flow.preparedTracksForPayload({
    source: "beatport",
    previewSource: "beatport",
    previewUrl: "https://www.beatport.com/playlist/same/2",
    previewTracks: [{ title: "Keep", included: true }],
    selectedSearch: null,
  }, "https://www.beatport.com/playlist/same/2"),
  [{ title: "Keep", included: true }],
);

assert.strictEqual(flow.shouldIgnoreJobSnapshot({ id: "job-a" }, "job-b"), true);
assert.strictEqual(flow.detectSourceFromUrl("https://open.spotify.com/playlist/abc"), "spotify");
assert.strictEqual(flow.detectSourceFromUrl("https://night.bandcamp.com/album/coastal"), "bandcamp");
assert.strictEqual(flow.detectSourceFromUrl("not a playlist"), "");
assert.strictEqual(flow.isYoutubePlaylistUrl("https://www.youtube.com/playlist?list=PLabc"), true);
assert.strictEqual(flow.isYoutubePlaylistUrl("https://www.youtube.com/watch?v=abc&list=PLabc"), false);

const errorLine = flow.logFragments(
  "Could not download Bobby Darin — Beyond the Sea: \u001b[0;31mERROR:\u001b[0m unable to download video data: HTTP Error 403: Forbidden",
);
assert.deepStrictEqual(
  errorLine.map((part) => [part.className, part.text]),
  [
    ["", "Could not download Bobby Darin — Beyond the Sea: "],
    ["log-red", "ERROR:"],
    ["", " unable to download video data: HTTP Error 403: Forbidden"],
  ],
  "yt-dlp red ERROR codes should become a colored log fragment",
);

assert.strictEqual(
  flow.logFragments("Could not download Song: HTTP Error 403: Forbidden")[0].className,
  "log-red",
  "a failure line without color codes is still marked red",
);

assert.strictEqual(
  flow.logFragments("Saved: Bobby Darin - Beyond the Sea.mp3")[0].className,
  "log-green",
  "a saved track is marked green",
);
assert.strictEqual(
  flow.logFragments("Already in library: Song.mp3")[0].className,
  "log-green",
);
assert.strictEqual(
  flow.logFragments("Could not write DJ sidecar for Song: disk full")[0].className,
  "log-red",
  "a failed follow-up action stays red",
);

console.log("ok");
