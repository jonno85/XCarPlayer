(() => {
  "use strict";

  const state = { source: "youtube", jobId: null, polling: null, working: false };
  const $ = (selector) => document.querySelector(selector);
  const sourceCards = document.querySelectorAll("[data-source]");
  const sourceDetails = {
    youtube: {
      label: "YouTube link",
      placeholder: "https://www.youtube.com/watch?v=…",
      helper: "Choose “Playlist” below if the link contains more than one song.",
    },
    spotify: {
      label: "Spotify track or playlist link",
      placeholder: "https://open.spotify.com/playlist/…",
      helper: "We read the public song names, then search YouTube for matching audio.",
    },
    beatport: {
      label: "Beatport track or playlist link",
      placeholder: "https://www.beatport.com/…",
      helper: "We read the public song names, then search YouTube for matching audio.",
    },
  };

  async function request(url, options = {}) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Something went wrong.");
    return body;
  }

  function message(text, kind = "") {
    const node = $("#message");
    node.textContent = text;
    node.className = `message is-visible ${kind}`;
    window.setTimeout(() => {
      if (node.textContent === text) node.className = "message";
    }, 6000);
  }

  function setSource(source) {
    state.source = source;
    sourceCards.forEach((card) => card.classList.toggle("is-selected", card.dataset.source === source));
    const isText = source === "text";
    $("#url-section").classList.toggle("hidden", isText);
    $("#text-section").classList.toggle("hidden", !isText);
    if (!isText) {
      const detail = sourceDetails[source];
      $("#url-label").textContent = detail.label;
      $("#source-url").placeholder = detail.placeholder;
      $("#url-helper").textContent = detail.helper;
    }
    $("#download-type-section").classList.toggle("hidden", source !== "youtube");
    $("#spotify-credentials").classList.toggle("hidden", source !== "spotify");
  }

  function setWorking(working) {
    state.working = working;
    $("#download-button").disabled = working;
    $("#download-button").textContent = working ? "Download in progress…" : "Download to my library";
  }

  function readSongFile(event) {
    const file = event.target.files[0];
    $("#file-name").textContent = file ? file.name : "No file chosen";
    if (!file) return;
    if (file.size > 1_000_000) {
      message("Please choose a text file smaller than 1 MB.", "error");
      event.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => { $("#song-list").value = String(reader.result || ""); };
    reader.onerror = () => message("That text file could not be read.", "error");
    reader.readAsText(file);
  }

  function renderJob(job) {
    $("#status-panel").classList.add("is-visible");
    const completed = Number(job.completed || 0);
    const failed = Number(job.failed || 0);
    const total = Number(job.total || 0);
    const finished = job.state === "complete" || job.state === "failed";
    const isFailed = job.state === "failed";
    const badge = $("#status-badge");
    badge.textContent = isFailed ? "Needs attention" : finished ? "Finished" : "Working";
    badge.className = `badge${isFailed ? " is-failed" : finished ? "" : " is-running"}`;
    $("#status-title").textContent = isFailed ? "Download needs attention" : finished ? "Your library is ready" : "Building your library";
    $("#status-copy").textContent = job.message || "Working…";
    $("#current-track").textContent = job.current || (finished ? `Saved in: ${job.output_dir}` : "");
    $("#download-log").textContent = (job.log || []).join("\n") || "Waiting for download details…";
    const progress = $("#progress");
    if (total && (finished || completed || failed)) {
      const percent = Math.min(100, Math.round(((completed + failed) / total) * 100));
      progress.style.width = `${percent}%`;
      progress.style.marginLeft = "0";
      progress.classList.remove("is-indeterminate");
    } else {
      progress.style.width = "";
      progress.style.marginLeft = "";
      progress.classList.add("is-indeterminate");
    }
    if (finished) {
      setWorking(false);
      window.clearInterval(state.polling);
      state.polling = null;
    }
  }

  async function pollJob() {
    if (!state.jobId) return;
    try {
      const { job } = await request(`/api/job?id=${encodeURIComponent(state.jobId)}`);
      renderJob(job);
    } catch (error) {
      window.clearInterval(state.polling);
      state.polling = null;
      setWorking(false);
      message(error.message, "error");
    }
  }

  async function startDownload(event) {
    event.preventDefault();
    if (state.working) return;
    const outputDir = $("#output-directory").value.trim();
    if (!outputDir) return message("Choose a music folder first.", "error");
    if (!$("#rights-confirmed").checked) {
      return message("Please confirm you have permission to download these tracks.", "error");
    }
    const payload = {
      source: state.source,
      output_dir: outputDir,
      rights_confirmed: true,
      url: $("#source-url").value.trim(),
      tracks: $("#song-list").value,
      download_type: $("#download-type").value,
      spotify_client_id: $("#spotify-client-id").value.trim(),
      spotify_client_secret: $("#spotify-client-secret").value.trim(),
    };
    setWorking(true);
    $("#status-panel").classList.add("is-visible");
    try {
      const { job } = await request("/api/download", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.jobId = job.id;
      renderJob(job);
      state.polling = window.setInterval(pollJob, 900);
      pollJob();
    } catch (error) {
      setWorking(false);
      message(error.message, "error");
    }
  }

  async function saveFolder() {
    const downloadDir = $("#output-directory").value.trim();
    if (!downloadDir) return message("Choose a folder to save as your default.", "error");
    try {
      const current = await request("/api/config");
      const { settings } = await request("/api/config", {
        method: "POST",
        body: JSON.stringify({
          download_dir: downloadDir,
          github_repository: current.settings.github_repository,
        }),
      });
      $("#output-directory").value = settings.download_dir;
      message("Default music folder saved on this computer.", "success");
    } catch (error) {
      message(error.message, "error");
    }
  }

  async function showUpdates() {
    $("#update-dialog").classList.add("is-visible");
    $("#update-title").textContent = "Checking for updates…";
    $("#update-message").textContent = "Looking at the GitHub source.";
    $("#install-update").classList.add("hidden");
    $("#release-link").classList.add("hidden");
    try {
      const status = await request("/api/update-status");
      $("#update-title").textContent = status.available ? "An update is available" : "Updates";
      $("#update-message").textContent = status.message;
      $("#install-update").classList.toggle("hidden", !status.can_install);
      if (status.release_url) {
        $("#release-link").href = status.release_url;
        $("#release-link").classList.remove("hidden");
      }
    } catch (error) {
      $("#update-title").textContent = "Could not check updates";
      $("#update-message").textContent = error.message;
    }
  }

  async function installUpdate() {
    $("#install-update").disabled = true;
    $("#update-message").textContent = "Installing the update…";
    try {
      const result = await request("/api/install-update", { method: "POST", body: "{}" });
      $("#update-message").textContent = result.message;
      $("#install-update").classList.add("hidden");
    } catch (error) {
      $("#update-message").textContent = error.message;
    } finally {
      $("#install-update").disabled = false;
    }
  }

  async function quit() {
    if (state.working && !window.confirm("A download is still running. Quit anyway?")) return;
    try {
      await request("/api/quit", { method: "POST", body: "{}" });
      document.body.innerHTML = "<main class='page'><section class='panel main-panel'><h1>See you next time.</h1><p class='lede'>Music Library Downloader has closed. You can close this browser tab.</p></section></main>";
    } catch (error) {
      message(error.message, "error");
    }
  }

  async function initialize() {
    try {
      const { settings } = await request("/api/config");
      $("#output-directory").value = settings.download_dir;
    } catch (error) {
      message(`Could not load your saved settings: ${error.message}`, "error");
    }
    sourceCards.forEach((card) => card.addEventListener("click", () => setSource(card.dataset.source)));
    $("#song-file").addEventListener("change", readSongFile);
    $("#download-form").addEventListener("submit", startDownload);
    $("#save-folder").addEventListener("click", saveFolder);
    $("#updates-button").addEventListener("click", showUpdates);
    $("#quit-button").addEventListener("click", quit);
    $("#close-update").addEventListener("click", () => $("#update-dialog").classList.remove("is-visible"));
    $("#install-update").addEventListener("click", installUpdate);
    $("#update-dialog").addEventListener("click", (event) => {
      if (event.target === $("#update-dialog")) $("#update-dialog").classList.remove("is-visible");
    });
    setSource("youtube");
  }

  document.addEventListener("DOMContentLoaded", initialize);
})();
