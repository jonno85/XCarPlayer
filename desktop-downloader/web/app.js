(() => {
  "use strict";

  const state = {
    source: "youtube", jobId: null, polling: null, working: false,
    language: "en", history: [], queue: [], queueIndex: -1,
    previewTracks: [], previewSource: "", importText: "", importFilename: "",
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
      signedBrowser: "Signed-in browser",
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
      noFile: "No file chosen", textSearchHelp: "The app searches YouTube for each song and writes it in your selected format.",
      simpleDesign: "Simple by design", simpleOne: "Pick where your song names come from.",
      simpleTwo: "Paste a link, or choose a plain text list.", simpleThree: "Watch the progress while files land in your music folder.",
      aboutSources: "About sources", aboutSourcesHelp: "Spotify and Beatport provide public song metadata; matching audio is searched on YouTube.",
      downloadStatus: "Download status", preparingTitle: "Getting things ready", preparing: "Preparing",
      preparingHelp: "Your download is being prepared.", showDetails: "Show download details",
      pause: "Pause", resume: "Resume", stop: "Stop", paused: "Paused", stopped: "Stopped",
      pausedTitle: "Download paused", stoppedTitle: "Download stopped",
      checkingUpdates: "Checking for updates…", checkingGithub: "Looking at the GitHub source.",
      openReleases: "Open GitHub Releases", close: "Close", installUpdate: "Install update",
      spotifyNoLogin: "No login, Premium, or app key required",
      spotifyPublicHelp: "The app reads track names from Spotify’s public page. Private playlists are unavailable; Spotify may limit very large public pages to 100 tracks.",
      importExporter: "Or import exporter TXT/CSV", previewTracks: "Preview tracks",
      chooseTextCsv: "Choose TXT/CSV file", previewTitle: "Check tracks before downloading",
      toggleAll: "Toggle all", previewHelp: "Edit artist/title if needed. Existing files are highlighted and will not be downloaded twice.",
      previewSummary: "{total} tracks · {existing} already in your library", artist: "Artist",
      title: "Title", previewFirst: "Preview the Spotify playlist before downloading.",
      readingTracks: "Reading track list…",
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
      signedBrowser: "Browser con accesso",
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
      noFile: "Nessun file scelto", textSearchHelp: "L’app cerca ogni brano su YouTube e lo salva nel formato selezionato.",
      simpleDesign: "Semplice per scelta", simpleOne: "Scegli da dove provengono i nomi dei brani.",
      simpleTwo: "Incolla un link o scegli una lista di testo.", simpleThree: "Segui l’avanzamento mentre i file arrivano nella cartella musicale.",
      aboutSources: "Informazioni sulle sorgenti", aboutSourcesHelp: "Spotify e Beatport forniscono metadati pubblici; l’audio corrispondente viene cercato su YouTube.",
      downloadStatus: "Stato download", preparingTitle: "Preparazione in corso", preparing: "Preparazione",
      preparingHelp: "Il download è in preparazione.", showDetails: "Mostra dettagli download",
      pause: "Pausa", resume: "Riprendi", stop: "Interrompi", paused: "In pausa", stopped: "Interrotto",
      pausedTitle: "Download in pausa", stoppedTitle: "Download interrotto",
      checkingUpdates: "Controllo aggiornamenti…", checkingGithub: "Controllo della sorgente GitHub.",
      openReleases: "Apri GitHub Releases", close: "Chiudi", installUpdate: "Installa aggiornamento",
      spotifyNoLogin: "Non servono accesso, Premium o chiavi app",
      spotifyPublicHelp: "L’app legge i nomi dei brani dalla pagina pubblica di Spotify. Le playlist private non sono disponibili; Spotify può limitare le pagine molto grandi a 100 brani.",
      importExporter: "Oppure importa TXT/CSV da un exporter", previewTracks: "Anteprima brani",
      chooseTextCsv: "Scegli file TXT/CSV", previewTitle: "Controlla i brani prima del download",
      toggleAll: "Seleziona/deseleziona tutti", previewHelp: "Correggi artista o titolo se necessario. I file esistenti sono evidenziati e non verranno scaricati due volte.",
      previewSummary: "{total} brani · {existing} già nella libreria", artist: "Artista",
      title: "Titolo", previewFirst: "Visualizza l’anteprima della playlist Spotify prima del download.",
      readingTracks: "Lettura elenco brani…",
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
    if (state.previewTracks.length) renderPreview();
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
    $("#spotify-public-import").classList.toggle("hidden", source !== "spotify");
    $("#preview-url-button").classList.toggle("hidden", source !== "spotify");
    $("#track-preview").classList.toggle(
      "hidden", !state.previewTracks.length || state.previewSource !== source
    );
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
    reader.onload = () => {
      $("#song-list").value = String(reader.result || "");
      state.importFilename = file.name;
      previewTracks("text", $("#song-list").value, file.name);
    };
    reader.onerror = () => message("That text file could not be read.", "error");
    reader.readAsText(file);
  }

  function readSpotifyImport(event) {
    const file = event.target.files[0];
    $("#spotify-import-name").textContent = file ? file.name : t("noFile");
    if (!file) return;
    if (file.size > 1_000_000) return message("Please choose a TXT/CSV file smaller than 1 MB.", "error");
    const reader = new FileReader();
    reader.onload = () => {
      state.importText = String(reader.result || "");
      state.importFilename = file.name;
      previewTracks("spotify-import", state.importText, file.name);
    };
    reader.onerror = () => message("That exporter file could not be read.", "error");
    reader.readAsText(file);
  }

  async function previewTracks(mode, content = "", filename = "") {
    const source = mode === "spotify-import" ? "text" : mode;
    const button = mode === "text" ? $("#preview-text-button") : $("#preview-url-button");
    button.disabled = true;
    button.textContent = t("readingTracks");
    try {
      const { preview } = await request("/api/preview", {
        method: "POST",
        body: JSON.stringify({
          source,
          url: $("#source-url").value.trim(),
          tracks: content || $("#song-list").value,
          filename,
          output_dir: $("#output-directory").value,
        }),
      });
      state.previewSource = mode === "spotify-import" ? "spotify" : mode;
      state.previewTracks = preview.tracks;
      renderPreview();
    } catch (error) {
      message(error.message, "error");
    } finally {
      button.disabled = false;
      button.textContent = t("previewTracks");
    }
  }

  function renderPreview() {
    const panel = $("#track-preview");
    const list = $("#preview-list");
    list.replaceChildren();
    const existing = state.previewTracks.filter((track) => track.existing).length;
    $("#preview-summary").textContent = t("previewSummary")
      .replace("{total}", state.previewTracks.length)
      .replace("{existing}", existing);
    state.previewTracks.forEach((track, index) => {
      const row = document.createElement("div");
      row.className = "preview-row";
      const included = document.createElement("input");
      included.type = "checkbox";
      included.checked = track.included !== false;
      included.addEventListener("change", () => { track.included = included.checked; });
      const artist = document.createElement("input");
      artist.type = "text";
      artist.value = track.artist;
      artist.placeholder = t("artist");
      artist.setAttribute("aria-label", `${t("artist")} ${index + 1}`);
      artist.addEventListener("input", () => { track.artist = artist.value; });
      const title = document.createElement("input");
      title.type = "text";
      title.value = track.title;
      title.placeholder = t("title");
      title.setAttribute("aria-label", `${t("title")} ${index + 1}`);
      title.addEventListener("input", () => { track.title = title.value; });
      row.append(included, artist, title);
      if (track.existing) {
        const chip = document.createElement("span");
        chip.className = "existing-chip";
        chip.textContent = t("existing");
        row.appendChild(chip);
      }
      list.appendChild(row);
    });
    panel.classList.toggle("hidden", state.previewSource !== state.source);
  }

  function invalidatePreview() {
    state.previewTracks = [];
    state.previewSource = "";
    $("#track-preview").classList.add("hidden");
  }

  function renderJob(job) {
    $("#status-panel").classList.add("is-visible");
    const completed = Number(job.completed || 0);
    const failed = Number(job.failed || 0);
    const existing = Number(job.existing || 0);
    const total = Number(job.total || 0);
    const isPaused = job.state === "paused";
    const isStopped = job.state === "stopped";
    const finished = job.state === "complete" || job.state === "failed" || isStopped;
    const isFailed = job.state === "failed";
    const badge = $("#status-badge");
    const badgeKey = isFailed ? "attention" : isStopped ? "stopped" : isPaused ? "paused" : finished ? "finished" : "working";
    badge.textContent = t(badgeKey);
    badge.className = `badge${isFailed ? " is-failed" : isStopped ? " is-stopped" : isPaused ? " is-paused" : finished ? "" : " is-running"}`;
    const titleKey = isFailed ? "needsAttention" : isStopped ? "stoppedTitle" : isPaused ? "pausedTitle" : finished ? "ready" : "building";
    $("#status-title").textContent = t(titleKey);
    $("#status-copy").textContent = job.message || t("working");
    $("#current-track").textContent = job.current || (finished ? job.output_dir : "");
    $("#download-log").textContent = (job.log || []).join("\n") || "…";
    $("#pause-download").classList.toggle("hidden", finished || isPaused);
    $("#resume-download").classList.toggle("hidden", !isPaused);
    $("#stop-download").classList.toggle("hidden", finished);
    const progress = $("#progress");
    if (total && (finished || completed || failed || existing || isPaused)) {
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

  async function controlJob(action) {
    if (!state.jobId) return;
    try {
      const { job } = await request(`/api/job/${action}`, {
        method: "POST",
        body: JSON.stringify({ id: state.jobId }),
      });
      renderJob(job);
    } catch (error) {
      message(error.message, "error");
    }
  }
    event.preventDefault();
    if (state.working) return;
    const outputDir = $("#output-directory").value.trim();
    if (!outputDir) return message(t("chooseFolderFirst"), "error");
    if (!$("#rights-confirmed").checked) return message(t("permission"), "error");
    if (state.source === "spotify" && (
      state.previewSource !== "spotify" || !state.previewTracks.length
    )) return message(t("previewFirst"), "error");
    const payload = {
      source: state.source, output_dir: outputDir, rights_confirmed: true,
      url: $("#source-url").value.trim(), tracks: $("#song-list").value,
      download_type: $("#download-type").value, youtube_browser: $("#youtube-browser").value,
      prepared_tracks: state.previewSource === state.source ? state.previewTracks : undefined,
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
      if (path) {
        $("#output-directory").value = path;
        invalidatePreview();
      }
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
    $("#spotify-import-file").addEventListener("change", readSpotifyImport);
    $("#preview-url-button").addEventListener("click", () => previewTracks("spotify"));
    $("#preview-text-button").addEventListener("click", () => previewTracks(
      "text", $("#song-list").value, state.importFilename
    ));
    $("#source-url").addEventListener("input", invalidatePreview);
    $("#select-all-tracks").addEventListener("click", () => {
      const selected = state.previewTracks.some((track) => track.included === false);
      state.previewTracks.forEach((track) => { track.included = selected; });
      renderPreview();
    });
    $("#download-form").addEventListener("submit", startDownload);
    $("#pause-download").addEventListener("click", () => controlJob("pause"));
    $("#resume-download").addEventListener("click", () => controlJob("resume"));
    $("#stop-download").addEventListener("click", () => {
      if (window.confirm(state.language === "it"
        ? "Interrompere il download? I brani già salvati restano nella cartella."
        : "Stop this download? Tracks already saved will stay in your folder.")) {
        controlJob("stop");
      }
    });
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
