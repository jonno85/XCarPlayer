(() => {
  "use strict";

  const state = {
    source: "youtube", jobId: null, polling: null, working: false,
    language: "en", history: [], queue: [], queueIndex: -1,
  };
  const $ = (selector) => document.querySelector(selector);
  const sourceCards = document.querySelectorAll("[data-source]");
  const words = {
    en: {
      updates: "Check for updates", quit: "Quit", eyebrow: "Your music, neatly collected",
      hero: "From link to library, without the fuss.",
      lede: "Paste a music link or load a song list. The app creates consistent audio files in the music folder you choose.",
      pickSource: "Pick your source", whatAdd: "What would you like to add?",
      youtubeHelp: "A song or a playlist link", metadataHelp: "Public track or playlist metadata",
      songList: "Song list", textHelp: "A .txt file, one song per line", pasteLink: "Paste the link",
      linkContains: "This link contains", singleItem: "One song or video", playlist: "A playlist",
      youtubeSignIn: "Only if YouTube asks you to sign in",
      youtubeSignInHelp: "Choose the browser where you are already signed in to YouTube. Its cookies stay on this computer and are only read to complete this download.",
      signedBrowser: "Signed-in browser", spotifyKey: "Spotify needs a one-time app key — add it here",
      addList: "Add your song list", textOrPaste: "Text file or pasted songs", chooseText: "Choose .txt file",
      saveLibrary: "Save to your library", musicFolder: "Music folder", chooseFolder: "Choose folder…",
      saveDefault: "Save as default", folderHelp: "Use the folder picker; your default is stored only on this computer.",
      audioOptions: "Audio format & Rekordbox options", audioFormat: "Audio format",
      playlistName: "Playlist name", losslessWarning: "FLAC/WAV do not restore quality already lost at the source. MP3 is the safest choice for older Pioneer hardware.",
      rekordboxPlaylist: "Create a Rekordbox-compatible .m3u8 playlist",
      rights: "I have the rights or permission to download these tracks and will follow the source service’s terms.",
      download: "Download to my library", downloading: "Download in progress…",
      libraryHistory: "Library & history", previousDownloads: "Previous downloads",
      compareFolder: "Compare folder", historyHelp: "Downloaded and already-existing tracks are highlighted here. Folder comparison never moves or deletes files.",
      noHistory: "No downloads recorded yet.", play: "Play", missing: "File missing", existing: "Already existed",
      downloaded: "Downloaded", chooseFolderFirst: "Choose a music folder first.",
      folderSaved: "Default music folder saved on this computer.", folderCancelled: "No folder was selected.",
      permission: "Please confirm you have permission to download these tracks.",
      working: "Working", finished: "Finished", attention: "Needs attention",
      building: "Building your library", ready: "Your library is ready", needsAttention: "Download needs attention",
      scanResult: "{total} audio files: {tracked} in download history, {untracked} other library files.",
      youtubeLabel: "YouTube link", spotifyLabel: "Spotify track or playlist link",
      beatportLabel: "Beatport track or playlist link",
      youtubeHint: "Choose “Playlist” below if the link contains more than one song.",
      metadataHint: "We read the public song names, then search YouTube for matching audio.",
      spotifyHelp: "Spotify links provide track names only. This app looks for matching audio on YouTube. Create a free key at",
      spotifyPrivacy: "Your key is used for this download only and is not saved.",
      noFile: "No file chosen", textSearchHelp: "The app searches YouTube for each song and writes it in your selected format.",
      simpleDesign: "Simple by design", simpleOne: "Pick where your song names come from.",
      simpleTwo: "Paste a link, or choose a plain text list.", simpleThree: "Watch the progress while files land in your music folder.",
      aboutSources: "About sources", aboutSourcesHelp: "Spotify and Beatport provide public song metadata; matching audio is searched on YouTube.",
      downloadStatus: "Download status", preparingTitle: "Getting things ready", preparing: "Preparing",
      preparingHelp: "Your download is being prepared.", showDetails: "Show download details",
      checkingUpdates: "Checking for updates…", checkingGithub: "Looking at the GitHub source.",
      openReleases: "Open GitHub Releases", close: "Close", installUpdate: "Install update",
    },
    it: {
      updates: "Controlla aggiornamenti", quit: "Esci", eyebrow: "La tua musica, raccolta con ordine",
      hero: "Dal link alla libreria, senza complicazioni.",
      lede: "Incolla un link musicale o carica una lista. L’app crea file audio uniformi nella cartella scelta.",
      pickSource: "Scegli la sorgente", whatAdd: "Cosa vuoi aggiungere?",
      youtubeHelp: "Link a un brano o playlist", metadataHelp: "Metadati di brano o playlist pubblica",
      songList: "Lista brani", textHelp: "File .txt, un brano per riga", pasteLink: "Incolla il link",
      linkContains: "Questo link contiene", singleItem: "Un brano o video", playlist: "Una playlist",
      youtubeSignIn: "Solo se YouTube richiede l’accesso",
      youtubeSignInHelp: "Scegli il browser in cui hai già effettuato l’accesso a YouTube. I cookie restano su questo computer e vengono letti solo per completare il download.",
      signedBrowser: "Browser con accesso", spotifyKey: "Spotify richiede una chiave una sola volta — aggiungila qui",
      addList: "Aggiungi la lista brani", textOrPaste: "File di testo o brani incollati", chooseText: "Scegli file .txt",
      saveLibrary: "Salva nella libreria", musicFolder: "Cartella musica", chooseFolder: "Scegli cartella…",
      saveDefault: "Salva predefinita", folderHelp: "Usa il selettore; la cartella predefinita viene salvata solo su questo computer.",
      audioOptions: "Formato audio e opzioni Rekordbox", audioFormat: "Formato audio",
      playlistName: "Nome playlist", losslessWarning: "FLAC/WAV non recuperano qualità già persa alla sorgente. MP3 è la scelta più compatibile con hardware Pioneer meno recente.",
      rekordboxPlaylist: "Crea una playlist .m3u8 compatibile con Rekordbox",
      rights: "Possiedo i diritti o il permesso per scaricare questi brani e rispetterò i termini del servizio sorgente.",
      download: "Scarica nella libreria", downloading: "Download in corso…",
      libraryHistory: "Libreria e cronologia", previousDownloads: "Download precedenti",
      compareFolder: "Confronta cartella", historyHelp: "I brani scaricati o già esistenti sono evidenziati qui. Il confronto non sposta né elimina file.",
      noHistory: "Nessun download registrato.", play: "Riproduci", missing: "File mancante", existing: "Già presente",
      downloaded: "Scaricato", chooseFolderFirst: "Scegli prima una cartella per la musica.",
      folderSaved: "Cartella musicale predefinita salvata su questo computer.", folderCancelled: "Nessuna cartella selezionata.",
      permission: "Conferma di avere il permesso per scaricare questi brani.",
      working: "In corso", finished: "Completato", attention: "Attenzione",
      building: "Creazione della libreria", ready: "La libreria è pronta", needsAttention: "Il download richiede attenzione",
      scanResult: "{total} file audio: {tracked} nella cronologia, {untracked} altri file della libreria.",
      youtubeLabel: "Link YouTube", spotifyLabel: "Link a brano o playlist Spotify",
      beatportLabel: "Link a brano o playlist Beatport",
      youtubeHint: "Scegli “Playlist” qui sotto se il link contiene più brani.",
      metadataHint: "Leggiamo i nomi pubblici dei brani e cerchiamo l’audio corrispondente su YouTube.",
      spotifyHelp: "I link Spotify forniscono solo i nomi dei brani. L’app cerca l’audio corrispondente su YouTube. Crea una chiave gratuita su",
      spotifyPrivacy: "La chiave viene usata solo per questo download e non viene salvata.",
      noFile: "Nessun file scelto", textSearchHelp: "L’app cerca ogni brano su YouTube e lo salva nel formato selezionato.",
      simpleDesign: "Semplice per scelta", simpleOne: "Scegli da dove provengono i nomi dei brani.",
      simpleTwo: "Incolla un link o scegli una lista di testo.", simpleThree: "Segui l’avanzamento mentre i file arrivano nella cartella musicale.",
      aboutSources: "Informazioni sulle sorgenti", aboutSourcesHelp: "Spotify e Beatport forniscono metadati pubblici; l’audio corrispondente viene cercato su YouTube.",
      downloadStatus: "Stato download", preparingTitle: "Preparazione in corso", preparing: "Preparazione",
      preparingHelp: "Il download è in preparazione.", showDetails: "Mostra dettagli download",
      checkingUpdates: "Controllo aggiornamenti…", checkingGithub: "Controllo della sorgente GitHub.",
      openReleases: "Apri GitHub Releases", close: "Chiudi", installUpdate: "Installa aggiornamento",
    },
  };

  const t = (key) => words[state.language][key] || words.en[key] || key;

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

  function applyLanguage(language) {
    state.language = language === "it" ? "it" : "en";
    document.documentElement.lang = state.language;
    $("#language-select").value = state.language;
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    setSource(state.source);
    setWorking(state.working);
    renderHistory();
  }

  function setSource(source) {
    state.source = source;
    sourceCards.forEach((card) => card.classList.toggle("is-selected", card.dataset.source === source));
    const isText = source === "text";
    $("#url-section").classList.toggle("hidden", isText);
    $("#text-section").classList.toggle("hidden", !isText);
    if (!isText) {
      $("#url-label").textContent = t(`${source}Label`);
      $("#source-url").placeholder = source === "youtube" ? "https://www.youtube.com/watch?v=…" : `https://${source === "spotify" ? "open.spotify.com" : "www.beatport.com"}/…`;
      $("#url-helper").textContent = t(source === "youtube" ? "youtubeHint" : "metadataHint");
    }
    $("#download-type-section").classList.toggle("hidden", source !== "youtube");
    $("#youtube-sign-in").classList.toggle("hidden", source !== "youtube");
    $("#spotify-credentials").classList.toggle("hidden", source !== "spotify");
  }

  function setWorking(working) {
    state.working = working;
    $("#download-button").disabled = working;
    $("#download-button").textContent = t(working ? "downloading" : "download");
  }

  function readSongFile(event) {
    const file = event.target.files[0];
    $("#file-name").textContent = file ? file.name : "No file chosen";
    if (!file) return;
    if (file.size > 1_000_000) return message("Please choose a text file smaller than 1 MB.", "error");
    const reader = new FileReader();
    reader.onload = () => { $("#song-list").value = String(reader.result || ""); };
    reader.onerror = () => message("That text file could not be read.", "error");
    reader.readAsText(file);
  }

  function renderJob(job) {
    $("#status-panel").classList.add("is-visible");
    const completed = Number(job.completed || 0);
    const failed = Number(job.failed || 0);
    const existing = Number(job.existing || 0);
    const total = Number(job.total || 0);
    const finished = job.state === "complete" || job.state === "failed";
    const isFailed = job.state === "failed";
    const badge = $("#status-badge");
    badge.textContent = t(isFailed ? "attention" : finished ? "finished" : "working");
    badge.className = `badge${isFailed ? " is-failed" : finished ? "" : " is-running"}`;
    $("#status-title").textContent = t(isFailed ? "needsAttention" : finished ? "ready" : "building");
    $("#status-copy").textContent = job.message || t("working");
    $("#current-track").textContent = job.current || (finished ? job.output_dir : "");
    $("#download-log").textContent = (job.log || []).join("\n") || "…";
    const progress = $("#progress");
    if (total && (finished || completed || failed || existing)) {
      progress.style.width = `${Math.min(100, Math.round(((completed + failed + existing) / total) * 100))}%`;
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
      loadHistory();
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
    if (!outputDir) return message(t("chooseFolderFirst"), "error");
    if (!$("#rights-confirmed").checked) return message(t("permission"), "error");
    const payload = {
      source: state.source, output_dir: outputDir, rights_confirmed: true,
      url: $("#source-url").value.trim(), tracks: $("#song-list").value,
      download_type: $("#download-type").value, youtube_browser: $("#youtube-browser").value,
      spotify_client_id: $("#spotify-client-id").value.trim(),
      spotify_client_secret: $("#spotify-client-secret").value.trim(),
      audio_format: $("#audio-format").value,
      rekordbox_playlist: $("#rekordbox-playlist").checked,
      playlist_name: $("#playlist-name").value.trim(),
    };
    setWorking(true);
    $("#status-panel").classList.add("is-visible");
    try {
      const { job } = await request("/api/download", { method: "POST", body: JSON.stringify(payload) });
      state.jobId = job.id;
      renderJob(job);
      state.polling = window.setInterval(pollJob, 900);
      pollJob();
    } catch (error) {
      setWorking(false);
      message(error.message, "error");
    }
  }

  async function savePreferences(showMessage = false) {
    const current = await request("/api/config");
    const { settings } = await request("/api/config", {
      method: "POST",
      body: JSON.stringify({
        ...current.settings,
        download_dir: $("#output-directory").value.trim(),
        language: state.language,
        audio_format: $("#audio-format").value,
      }),
    });
    if (showMessage) message(t("folderSaved"), "success");
    return settings;
  }

  async function pickFolder() {
    try {
      const { path } = await request("/api/pick-folder", {
        method: "POST",
        body: JSON.stringify({ current: $("#output-directory").value }),
      });
      if (path) $("#output-directory").value = path;
      else message(t("folderCancelled"));
    } catch (error) {
      message(error.message, "error");
    }
  }

  async function loadHistory() {
    try {
      const { entries } = await request("/api/history");
      state.history = entries;
      renderHistory();
    } catch (error) {
      $("#history-list").textContent = error.message;
    }
  }

  function renderHistory() {
    const list = $("#history-list");
    if (!list) return;
    list.replaceChildren();
    if (!state.history.length) {
      const empty = document.createElement("p");
      empty.className = "helper";
      empty.textContent = t("noHistory");
      list.appendChild(empty);
      return;
    }
    state.history.slice(0, 100).forEach((entry) => {
      const row = document.createElement("div");
      row.className = `history-item${entry.available ? "" : " is-missing"}`;
      const copy = document.createElement("div");
      const title = document.createElement("div");
      title.className = "history-title";
      title.textContent = entry.label;
      const meta = document.createElement("div");
      meta.className = "history-meta";
      const status = entry.available ? (entry.source === "existing" ? t("existing") : t("downloaded")) : t("missing");
      meta.textContent = `${status} · ${String(entry.format).toUpperCase()} · ${new Date(entry.downloaded_at).toLocaleString(state.language)}`;
      copy.append(title, meta);
      row.appendChild(copy);
      if (entry.available) {
        const play = document.createElement("button");
        play.type = "button";
        play.className = "play-button";
        play.title = t("play");
        play.textContent = "▶";
        play.addEventListener("click", () => playEntry(entry.id));
        row.appendChild(play);
      }
      list.appendChild(row);
    });
  }

  function playEntry(entryId) {
    const selected = state.history.find((entry) => entry.id === entryId);
    state.queue = state.history
      .filter((entry) => entry.available && selected && entry.playlist_id === selected.playlist_id)
      .reverse();
    state.queueIndex = state.queue.findIndex((entry) => entry.id === entryId);
    playCurrent();
  }

  function playCurrent() {
    if (state.queueIndex < 0 || state.queueIndex >= state.queue.length) return;
    const player = $("#audio-player");
    player.src = `/api/media?id=${encodeURIComponent(state.queue[state.queueIndex].id)}`;
    player.play().catch(() => {});
  }

  async function scanLibrary() {
    const directory = $("#output-directory").value;
    if (!directory) return message(t("chooseFolderFirst"), "error");
    try {
      const { library } = await request("/api/scan-library", {
        method: "POST", body: JSON.stringify({ directory }),
      });
      $("#library-summary").textContent = t("scanResult")
        .replace("{total}", library.total).replace("{tracked}", library.tracked).replace("{untracked}", library.untracked);
    } catch (error) {
      message(error.message, "error");
    }
  }

  async function showUpdates() {
    $("#update-dialog").classList.add("is-visible");
    $("#update-title").textContent = "Checking for updates…";
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
      $("#update-message").textContent = error.message;
    }
  }

  async function installUpdate() {
    $("#install-update").disabled = true;
    try {
      const result = await request("/api/install-update", { method: "POST", body: "{}" });
      $("#update-message").textContent = result.message;
      $("#install-update").classList.add("hidden");
    } finally {
      $("#install-update").disabled = false;
    }
  }

  async function quit() {
    if (state.working && !window.confirm("A download is still running. Quit anyway?")) return;
    await request("/api/quit", { method: "POST", body: "{}" });
    document.body.innerHTML = `<main class="page"><section class="panel main-panel"><h1>${state.language === "it" ? "Alla prossima." : "See you next time."}</h1></section></main>`;
  }

  async function initialize() {
    try {
      const { settings } = await request("/api/config");
      $("#output-directory").value = settings.download_dir;
      $("#audio-format").value = settings.audio_format || "mp3";
      applyLanguage(settings.language || "en");
    } catch (error) {
      message(error.message, "error");
    }
    sourceCards.forEach((card) => card.addEventListener("click", () => setSource(card.dataset.source)));
    $("#song-file").addEventListener("change", readSongFile);
    $("#download-form").addEventListener("submit", startDownload);
    $("#pick-folder").addEventListener("click", pickFolder);
    $("#save-folder").addEventListener("click", () => savePreferences(true).catch((error) => message(error.message, "error")));
    $("#language-select").addEventListener("change", (event) => {
      applyLanguage(event.target.value);
      savePreferences(false).catch(() => {});
    });
    $("#audio-format").addEventListener("change", () => savePreferences(false).catch(() => {}));
    $("#scan-library").addEventListener("click", scanLibrary);
    $("#audio-player").addEventListener("ended", () => {
      if (++state.queueIndex < state.queue.length) playCurrent();
    });
    $("#updates-button").addEventListener("click", showUpdates);
    $("#quit-button").addEventListener("click", () => quit().catch((error) => message(error.message, "error")));
    $("#close-update").addEventListener("click", () => $("#update-dialog").classList.remove("is-visible"));
    $("#install-update").addEventListener("click", installUpdate);
    $("#update-dialog").addEventListener("click", (event) => {
      if (event.target === $("#update-dialog")) $("#update-dialog").classList.remove("is-visible");
    });
    setSource("youtube");
    loadHistory();
  }

  document.addEventListener("DOMContentLoaded", initialize);
})();
