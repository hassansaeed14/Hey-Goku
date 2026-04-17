(() => {
  const STORAGE_KEYS = {
    sessionId: "aura_live_session_id",
    detailsOpen: "aura_details_open",
  };

  const FALLBACK_REPLY = "Something went wrong on my side. Try again.";
  const WAKE_FALLBACK = "Hey AURA";
  const WAKE_ACKNOWLEDGEMENT = "Yes?";
  const COMMAND_NO_SPEECH_RETRY_LIMIT = 1;
  const CHAT_REQUEST_TIMEOUT_MS = 20000;
  const REFRESH_INTERVAL_MS = 120000;
  const WAKE_RESUME_DELAY_MS = 900;
  const NO_SPEECH_RECOVERY_DELAY_MS = 1400;
  const RECOGNITION_IDLE_TIMEOUT_MS = 1500;

  const state = {
    sessionId: "default",
    detailsOpen: false,
    auth: null,
    providerSnapshot: null,
    systemHealth: null,
    voiceStatus: null,
    currentProvider: null,
    providerRefreshInFlight: false,
    voicePhase: "idle",
    wakeModeEnabled: false,
    wakeModeGestureNeeded: false,
    wakeStandbyActive: false,
    recognition: null,
    recognitionActive: false,
    recognitionMode: "off",
    recognitionHandoffPending: false,
    listening: false,
    speaking: false,
    busy: false,
    voiceActionInFlight: false,
    activeSpeechRunId: 0,
    currentUtterance: null,
    recognitionStopReason: "idle",
    bargeInArmed: false,
    bargeInTriggered: false,
    currentSpokenText: "",
    partialTranscript: "",
    commandRetryCount: 0,
    currentRequestController: null,
    refreshInFlight: false,
    refreshQueuedForce: false,
    refreshIntervalId: null,
    lastStatusRefreshAt: 0,
    recognitionStartTimer: null,
    activity: [],
    browserVoice: {
      mode: "Checking",
      permission: "Checking",
      inputDevice: "Checking",
      lastTranscript: "No data yet",
      lastIssue: "No issues yet",
      lastEvent: "idle",
      heardSpeech: false,
    },
  };

  const el = {};

  document.addEventListener("DOMContentLoaded", () => {
    void init();
  });

  async function init() {
    cacheDom();
    state.sessionId = ensureSessionId();
    state.detailsOpen = readBoolean(STORAGE_KEYS.detailsOpen, window.innerWidth >= 1200);
    bindEvents();
    syncDetailsDrawer();
    setupRecognition();
    await refreshBrowserVoiceDiagnostics({ requestPermission: false });
    renderProviderList();
    renderActivityList();
    setAssistantState("idle", {
      pill: "Idle",
      kicker: "Standby",
      headline: "Ready when you are.",
      description: `Say "${preferredWakePhrase()}" after wake mode is active, or use Talk and the text command field below.`,
    });
    updateLiveTranscript("Waiting for your voice or text command.");
    updateLiveResponse("AURA is standing by.");
    updateWakeBanner("Checking voice and provider status...");
    await bootstrap();
    scheduleRefresh();
  }

  function cacheDom() {
    const ids = [
      "presenceSummary",
      "statePillLabel",
      "detailsToggle",
      "mobileBackdrop",
      "assistantCoreButton",
      "stateKicker",
      "stateHeadline",
      "stateDescription",
      "liveTranscript",
      "liveResponse",
      "responseMetaProvider",
      "responseMetaMode",
      "detailsDrawer",
      "refreshStatusButton",
      "accessMode",
      "brainState",
      "activeProvider",
      "wakeModeStatus",
      "routeSummary",
      "providersList",
      "browserVoiceMode",
      "micPermissionState",
      "inputDeviceSummary",
      "lastTranscriptSummary",
      "lastVoiceIssue",
      "accountSummary",
      "authActionLink",
      "adminLink",
      "activityList",
      "wakeBanner",
      "wakeModeButton",
      "talkButton",
      "interruptButton",
      "textCommandInput",
      "sendButton",
    ];

    ids.forEach((id) => {
      el[id] = document.getElementById(id);
    });
    el.body = document.body;
  }

  function bindEvents() {
    el.detailsToggle.addEventListener("click", () => setDetailsOpen(!state.detailsOpen));
    el.mobileBackdrop.addEventListener("click", () => setDetailsOpen(false));
    el.refreshStatusButton.addEventListener("click", () => {
      void refreshStatus({ force: true, includeProviderRefresh: true });
    });
    el.wakeModeButton.addEventListener("click", () => {
      void toggleWakeMode();
    });
    el.talkButton.addEventListener("click", () => {
      void startTalkCapture();
    });
    el.interruptButton.addEventListener("click", interruptAssistant);
    el.sendButton.addEventListener("click", () => {
      void submitTextCommand();
    });
    el.textCommandInput.addEventListener("keydown", handleTextInputKeydown);
    el.assistantCoreButton.addEventListener("click", () => {
      void handleCoreButtonClick();
    });
    window.addEventListener("resize", handleResize);
    document.addEventListener("visibilitychange", handleVisibilityChange);
  }

  async function bootstrap() {
    await refreshStatus({ force: true, quiet: true });
    if (state.auth?.authenticated) {
      await attemptAutomaticWakeStandby();
    } else {
      updateWakeBanner(publicWakeBanner());
    }
  }

  async function refreshStatus({ force = false, quiet = false, includeProviderRefresh = false } = {}) {
    if (state.refreshInFlight) {
      if (force) {
        state.refreshQueuedForce = true;
      }
      return;
    }

    state.refreshInFlight = true;

    try {
      const authPayload = await fetchStatusPayload("/api/auth/session");
      if (authPayload) {
        state.auth = authPayload;
      }

      const healthPayload = await fetchStatusPayload("/api/system/health");
      if (healthPayload) {
        state.systemHealth = healthPayload;
      }

      const voicePayload = await fetchStatusPayload("/api/voice/status");
      if (voicePayload) {
        state.voiceStatus = voicePayload;
      }

      state.lastStatusRefreshAt = Date.now();
      renderStatusSurfaces();
      if (!quiet && !state.busy && !state.speaking && !state.listening) {
        updateWakeBanner(currentWakeBanner());
      }
      if (includeProviderRefresh) {
        window.setTimeout(() => {
          void refreshProviderSnapshot({ force });
        }, quiet ? 1200 : 0);
      }
    } finally {
      state.refreshInFlight = false;
      if (state.refreshQueuedForce) {
        state.refreshQueuedForce = false;
        window.setTimeout(() => {
          void refreshStatus({ force: true, quiet: true });
        }, 200);
      }
    }
  }

  async function refreshProviderSnapshot({ force = false } = {}) {
    if (state.providerRefreshInFlight) {
      return;
    }

    state.providerRefreshInFlight = true;
    const refreshSuffix = force ? "?refresh=1" : "";

    try {
      const payload = await fetchJson(`/api/providers${refreshSuffix}`);
      state.providerSnapshot = payload;
      renderStatusSurfaces();
    } catch (_error) {
      renderProviderList();
    } finally {
      state.providerRefreshInFlight = false;
    }
  }

  async function fetchStatusPayload(url) {
    try {
      return await fetchJson(url);
    } catch (_error) {
      return null;
    }
  }

  function renderStatusSurfaces() {
    const assistantRuntime = currentRuntime();
    const authPayload = state.auth || {};
    const activeProvider = assistantRuntime.active_provider || assistantRuntime.preferred_provider || "No data yet";
    const brain = state.systemHealth?.brain || "unknown";

    el.accessMode.textContent = authPayload.authenticated ? "Authenticated" : "Public";
    el.brainState.textContent = humanizeStatus(brain);
    el.activeProvider.textContent = humanizeProviderName(activeProvider);
    if (state.voicePhase === "wake_listening") {
      el.wakeModeStatus.textContent = "Standby active";
    } else if (state.voicePhase === "command_listening") {
      el.wakeModeStatus.textContent = "Listening";
    } else if (state.voicePhase === "interrupted") {
      el.wakeModeStatus.textContent = "Interrupted";
    } else if (state.voicePhase === "processing") {
      el.wakeModeStatus.textContent = "Thinking";
    } else if (state.voicePhase === "speaking") {
      el.wakeModeStatus.textContent = "Speaking";
    } else if (state.wakeModeEnabled) {
      el.wakeModeStatus.textContent = "Wake ready";
    } else if (state.wakeModeGestureNeeded) {
      el.wakeModeStatus.textContent = "Needs tap";
    } else {
      el.wakeModeStatus.textContent = "Standby off";
    }
    el.routeSummary.textContent = assistantRuntime.message || "No live routing data yet.";
    el.presenceSummary.textContent = assistantRuntime.message || "Private voice-first assistant console.";
    el.responseMetaProvider.textContent = `Provider: ${humanizeProviderName(activeProvider)}`;
    el.responseMetaMode.textContent = `Mode: ${authPayload.authenticated ? "account" : "public"}`;
    renderProviderList();
    renderVoiceDiagnostics();
    renderAccountSummary();
    renderWakeControls();
  }

  function renderProviderList() {
    const items = state.providerSnapshot?.items || state.systemHealth?.provider_details || [];
    el.providersList.innerHTML = "";

    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "provider-empty";
      empty.textContent = "Provider details are unavailable right now. Use Refresh status to check them again.";
      el.providersList.appendChild(empty);
      return;
    }

    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = `provider-card provider-card--${String(item.status || "unknown").toLowerCase()}`;

      const header = document.createElement("div");
      header.className = "provider-card__header";

      const title = document.createElement("strong");
      title.textContent = humanizeProviderName(item.provider);

      const badge = document.createElement("span");
      badge.className = `provider-badge provider-badge--${String(item.status || "unknown").toLowerCase()}`;
      badge.textContent = humanizeStatus(item.status || "unknown");

      header.append(title, badge);

      const model = document.createElement("p");
      model.className = "provider-card__model";
      model.textContent = item.model ? `Model: ${item.model}` : "Model: not available";

      const reason = document.createElement("p");
      reason.className = "provider-card__reason";
      reason.textContent = item.reason || "No provider diagnostics yet.";

      card.append(header, model, reason);

      if (item.error) {
        const error = document.createElement("p");
        error.className = "provider-card__error";
        error.textContent = `Error: ${item.error}`;
        card.appendChild(error);
      }

      el.providersList.appendChild(card);
    });
  }

  function renderAccountSummary() {
    const authPayload = state.auth || {};
    const user = authPayload.user || null;

    if (authPayload.authenticated && user) {
      const name = user.preferred_name || user.name || user.username || "there";
      el.accountSummary.textContent = `Signed in as ${name}. Wake mode can stay armed while this page is open.`;
      el.authActionLink.textContent = "Signed in";
      el.authActionLink.removeAttribute("href");
      el.authActionLink.setAttribute("aria-disabled", "true");
      el.adminLink.hidden = !Boolean(user.admin);
      return;
    }

    el.accountSummary.textContent = "Public mode keeps text and one-tap voice available. Sign in if you want wake-mode-first use and protected account features.";
    el.authActionLink.textContent = "Sign in";
    el.authActionLink.href = "/login";
    el.authActionLink.removeAttribute("aria-disabled");
    el.adminLink.hidden = true;
  }

  function renderVoiceDiagnostics() {
    const diagnostics = state.browserVoice;
    el.browserVoiceMode.textContent = diagnostics.mode || "No data yet";
    el.micPermissionState.textContent = diagnostics.permission || "No data yet";
    el.inputDeviceSummary.textContent = diagnostics.inputDevice || "No data yet";
    el.lastTranscriptSummary.textContent = diagnostics.lastTranscript || "No data yet";
    el.lastVoiceIssue.textContent = diagnostics.lastIssue || "No issues yet";
  }

  function renderActivityList() {
    el.activityList.innerHTML = "";

    if (!state.activity.length) {
      const empty = document.createElement("p");
      empty.className = "activity-empty";
      empty.textContent = "No assistant activity yet.";
      el.activityList.appendChild(empty);
      return;
    }

    state.activity.slice(0, 6).forEach((item) => {
      const row = document.createElement("article");
      row.className = `activity-item activity-item--${item.tone || "neutral"}`;

      const head = document.createElement("div");
      head.className = "activity-item__head";

      const label = document.createElement("strong");
      label.textContent = item.label;

      const time = document.createElement("span");
      time.textContent = item.time;

      head.append(label, time);

      const detail = document.createElement("p");
      detail.textContent = item.detail;

      row.append(head, detail);
      el.activityList.appendChild(row);
    });
  }

  function addActivity(label, detail, tone = "neutral") {
    state.activity.unshift({
      label,
      detail,
      tone,
      time: formatTime(new Date()),
    });
    state.activity = state.activity.slice(0, 12);
    renderActivityList();
  }

  function renderWakeControls() {
    el.wakeModeButton.classList.toggle("is-active", state.wakeModeEnabled);
    if (!canUseVoice()) {
      el.wakeModeButton.textContent = "Wake unavailable";
    } else if (state.voicePhase === "wake_listening") {
      el.wakeModeButton.textContent = "Wake mode on";
    } else if (state.voicePhase === "command_listening") {
      el.wakeModeButton.textContent = "Listening";
    } else if (state.voicePhase === "interrupted") {
      el.wakeModeButton.textContent = "Interrupted";
    } else if (state.voicePhase === "processing") {
      el.wakeModeButton.textContent = "Working";
    } else if (state.voicePhase === "speaking") {
      el.wakeModeButton.textContent = "Speaking";
    } else if (state.wakeModeEnabled) {
      el.wakeModeButton.textContent = "Wake mode on";
    } else {
      el.wakeModeButton.textContent = "Wake mode";
    }
    el.wakeModeButton.disabled = state.voiceActionInFlight;
    el.talkButton.disabled = !canUseVoice() || state.busy || state.voicePhase !== "idle" || state.voiceActionInFlight;
    el.interruptButton.disabled = !(state.busy || state.recognitionActive || state.voicePhase !== "idle");
  }

  function setBrowserVoiceDiagnostics(patch) {
    state.browserVoice = {
      ...state.browserVoice,
      ...patch,
    };
    renderVoiceDiagnostics();
  }

  function setVoicePhase(phase) {
    state.voicePhase = phase;
    state.listening = phase === "wake_listening" || phase === "command_listening";
    state.speaking = phase === "speaking";
    state.wakeStandbyActive = phase === "wake_listening" && state.recognitionActive;
    renderWakeControls();
  }

  function clearBargeInState({ keepTriggered = false } = {}) {
    state.bargeInArmed = false;
    state.currentSpokenText = "";
    if (!keepTriggered) {
      state.bargeInTriggered = false;
    }
  }

  function hasBrowserMicPermission() {
    return String(state.browserVoice.permission || "").trim().toLowerCase() === "granted";
  }

  function normalizeSpeechEchoText(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[^\w\s']/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function isLikelySpeechEcho(transcript) {
    const heard = normalizeSpeechEchoText(transcript);
    const spoken = normalizeSpeechEchoText(state.currentSpokenText);
    if (!heard || !spoken) {
      return false;
    }
    if (spoken.includes(heard) || heard.includes(spoken)) {
      return true;
    }

    const heardWords = heard.split(" ").filter(Boolean);
    const spokenWords = new Set(spoken.split(" ").filter(Boolean));
    if (!heardWords.length || !spokenWords.size) {
      return false;
    }

    const overlap = heardWords.filter((word) => spokenWords.has(word)).length;
    return (overlap / heardWords.length) >= 0.75;
  }

  function triggerBargeIn(transcript) {
    if (state.bargeInTriggered) {
      return;
    }
    state.bargeInTriggered = true;
    state.bargeInArmed = false;
    stopSpeech();
    setVoicePhase("interrupted");
    setAssistantState("interrupted", {
      pill: "Interrupted",
      kicker: "Voice override",
      headline: "Go ahead.",
      description: "I stopped speaking. I'm listening to you now.",
    });
    updateWakeBanner("Interrupted. Listening for your command now.");
    addActivity("Interrupted", `AURA stopped speaking when it heard: ${transcript}`, "warn");
  }

  async function armBargeInListener() {
    if (!canUseVoice() || !hasBrowserMicPermission() || state.bargeInArmed || state.recognitionActive || state.voicePhase !== "speaking") {
      return false;
    }

    state.bargeInArmed = true;
    state.bargeInTriggered = false;
    const started = await transitionRecognitionMode("command", {
      automatic: true,
      resetCommandRetryCount: true,
    });
    if (!started) {
      state.bargeInArmed = false;
    }
    return started;
  }

  function browserPermissionLabel(value) {
    const normalized = String(value || "").trim().toLowerCase();
    const labels = {
      granted: "Granted",
      prompt: "Prompt required",
      denied: "Denied",
      unsupported: "Unsupported",
      "not-allowed": "Denied",
      "service-not-allowed": "Denied",
    };
    return labels[normalized] || humanizeStatus(normalized || "unknown");
  }

  function logVoiceEvent(eventName, detail = {}) {
    try {
      console.debug("[AURA voice]", eventName, detail);
    } catch (_error) {
      // keep diagnostics lightweight
    }
  }

  function clearRecognitionStartTimer() {
    if (!state.recognitionStartTimer) {
      return;
    }
    window.clearTimeout(state.recognitionStartTimer);
    state.recognitionStartTimer = null;
  }

  function scheduleRecognitionStart(
    mode,
    { delay = WAKE_RESUME_DELAY_MS, automatic = true, resetCommandRetryCount = false, reason = "resume" } = {},
  ) {
    clearRecognitionStartTimer();
    state.recognitionStartTimer = window.setTimeout(() => {
      state.recognitionStartTimer = null;
      if (state.recognitionActive || state.busy || state.speaking) {
        return;
      }
      if (mode === "wake" && !state.wakeModeEnabled) {
        return;
      }
      logVoiceEvent("recognition_restart", { mode, reason, automatic });
      void transitionRecognitionMode(mode, { automatic, resetCommandRetryCount });
    }, delay);
  }

  async function waitForRecognitionIdle(timeoutMs = RECOGNITION_IDLE_TIMEOUT_MS) {
    if (!state.recognitionActive) {
      return true;
    }

    const startedAt = Date.now();
    while (Date.now() - startedAt < timeoutMs) {
      await new Promise((resolve) => {
        window.setTimeout(resolve, 50);
      });
      if (!state.recognitionActive) {
        return true;
      }
    }
    return !state.recognitionActive;
  }

  async function transitionRecognitionMode(mode, { automatic = false, resetCommandRetryCount = false } = {}) {
    clearRecognitionStartTimer();

    if (state.recognitionActive) {
      state.recognitionHandoffPending = true;
      stopRecognition("handoff");
      const idle = await waitForRecognitionIdle();
      if (!idle) {
        state.recognitionHandoffPending = false;
        setVoicePhase("idle");
        setBrowserVoiceDiagnostics({
          lastEvent: "handoff_timeout",
          lastIssue: "The microphone session did not close cleanly.",
        });
        setAssistantState("error", {
          pill: "Error",
          kicker: "Voice issue",
          headline: "I could not reset the microphone cleanly.",
          description: "Try Talk again in a moment.",
        });
        return false;
      }
    }

    return startRecognitionSession(mode, { automatic, resetCommandRetryCount });
  }

  function handleNoSpeechDetected(partialTranscript) {
    const transcript = String(partialTranscript || "").trim();
    const hadPartial = Boolean(transcript);
    const activeMode = state.recognitionMode;
    const message = hadPartial
      ? "I caught part of that, so I will use what I heard."
      : activeMode === "wake"
        ? `I did not hear the wake phrase. Say "${preferredWakePhrase()}" when you are ready.`
        : "I did not hear anything clearly enough to continue.";

    setBrowserVoiceDiagnostics({
      lastTranscript: hadPartial ? transcript : state.browserVoice.lastTranscript,
      heardSpeech: hadPartial,
      lastEvent: activeMode === "wake" ? "wake_no_speech" : "command_no_speech",
      lastIssue: message,
    });

    if (activeMode === "command" && hadPartial) {
      addActivity("Partial voice", "AURA used the speech it captured instead of discarding it.", "warn");
      void handleCommandTranscript(transcript);
      return;
    }

    if (activeMode === "command" && state.commandRetryCount < COMMAND_NO_SPEECH_RETRY_LIMIT) {
      state.commandRetryCount += 1;
      setVoicePhase("idle");
      setAssistantState("no_speech", {
        pill: "No speech",
        kicker: "Voice",
        headline: "I did not catch that.",
        description: "Please say it once more. I am listening again now.",
      });
      updateWakeBanner("I did not catch that. Please say it once more.");
      scheduleRecognitionStart("command", {
        delay: NO_SPEECH_RECOVERY_DELAY_MS,
        automatic: true,
        resetCommandRetryCount: false,
        reason: "command_retry",
      });
      return;
    }

    state.commandRetryCount = 0;
    setVoicePhase("idle");
    if (activeMode === "wake") {
      setIdleState();
    } else {
      setAssistantState("no_speech", {
        pill: "No speech",
        kicker: "Voice",
        headline: "I did not hear a clear command.",
        description: "Try again with Talk, or use the text command field below.",
      });
    }
    updateWakeBanner(message);

    if (state.wakeModeEnabled) {
      scheduleRecognitionStart("wake", {
        delay: NO_SPEECH_RECOVERY_DELAY_MS,
        automatic: true,
        reason: activeMode === "wake" ? "wake_retry" : "return_to_standby",
      });
    }
  }

  async function refreshBrowserVoiceDiagnostics({ requestPermission = false } = {}) {
    const mode = state.voiceStatus?.wake_word?.mode === "browser_assisted"
      ? "Browser-assisted wake mode"
      : "Browser voice";
    const updates = { mode };

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setBrowserVoiceDiagnostics({
        ...updates,
        permission: "Unsupported",
        inputDevice: "Browser microphone API is unavailable",
        lastIssue: "This browser cannot provide the microphone path AURA needs.",
      });
      return false;
    }

    let permissionState = state.browserVoice.permission || "Unknown";
    if (navigator.permissions?.query) {
      try {
        const permission = await navigator.permissions.query({ name: "microphone" });
        permissionState = permission.state;
      } catch (_error) {
        permissionState = state.browserVoice.permission || "Unknown";
      }
    }

    if (requestPermission && permissionState !== "granted") {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
        const track = stream.getAudioTracks()[0] || null;
        permissionState = "granted";
        updates.inputDevice = track?.label || "Browser-selected microphone";
        stream.getTracks().forEach((mediaTrack) => mediaTrack.stop());
      } catch (error) {
        const message = humanizeSpeechError(error?.name || error?.message || "not-allowed");
        setBrowserVoiceDiagnostics({
          ...updates,
          permission: browserPermissionLabel(error?.name || "denied"),
          lastIssue: message,
        });
        return false;
      }
    }

    if (navigator.mediaDevices.enumerateDevices) {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const inputs = devices.filter((device) => device.kind === "audioinput");
        if (!updates.inputDevice && inputs.length) {
          const labeled = inputs.find((device) => device.label);
          updates.inputDevice = labeled?.label || `${inputs.length} audio input device${inputs.length === 1 ? "" : "s"} available`;
        } else if (!updates.inputDevice) {
          updates.inputDevice = "No audio input device was reported";
        }
      } catch (_error) {
        if (!updates.inputDevice) {
          updates.inputDevice = "Browser did not expose input device details";
        }
      }
    }

    setBrowserVoiceDiagnostics({
      ...updates,
      permission: browserPermissionLabel(permissionState),
      inputDevice: updates.inputDevice || state.browserVoice.inputDevice || "No data yet",
    });
    return permissionState === "granted";
  }

  function handleResize() {
    if (window.innerWidth >= 1200) {
      el.mobileBackdrop.hidden = true;
    } else if (!state.detailsOpen) {
      el.mobileBackdrop.hidden = true;
    }
  }

  function handleVisibilityChange() {
    if (document.hidden || state.refreshInFlight || state.busy || state.recognitionActive) {
      return;
    }
    if ((Date.now() - state.lastStatusRefreshAt) >= REFRESH_INTERVAL_MS) {
      void refreshStatus({ quiet: true });
    }
  }

  function setDetailsOpen(open) {
    state.detailsOpen = Boolean(open);
    localStorage.setItem(STORAGE_KEYS.detailsOpen, String(state.detailsOpen));
    syncDetailsDrawer();
  }

  function syncDetailsDrawer() {
    el.body.classList.toggle("details-open", state.detailsOpen);
    el.detailsToggle.setAttribute("aria-expanded", state.detailsOpen ? "true" : "false");
    el.mobileBackdrop.hidden = !state.detailsOpen || window.innerWidth >= 1200;
  }

  async function attemptAutomaticWakeStandby() {
    if (!canUseVoice()) {
      updateWakeBanner(currentWakeBanner());
      return;
    }

    const started = await enableWakeMode({ automatic: true });
    if (!started) {
      state.wakeModeGestureNeeded = true;
      updateWakeBanner('Wake mode needs one tap in this browser before "Hey AURA" can work reliably.');
    }
  }

  async function handleCoreButtonClick() {
    if (state.auth?.authenticated) {
      if (state.wakeModeEnabled) {
        await startTalkCapture();
        return;
      }
      await toggleWakeMode();
      return;
    }

    await startTalkCapture();
  }

  async function toggleWakeMode() {
    if (state.voiceActionInFlight) {
      return;
    }
    if (state.wakeModeEnabled) {
      disableWakeMode();
      return;
    }
    await enableWakeMode({ automatic: false });
  }

  async function enableWakeMode({ automatic = false } = {}) {
    if (state.voiceActionInFlight) {
      return false;
    }
    state.voiceActionInFlight = true;
    renderWakeControls();

    try {
      if (!canUseVoice()) {
        updateWakeBanner(currentWakeBanner());
        return false;
      }

      const microphoneReady = await refreshBrowserVoiceDiagnostics({ requestPermission: !automatic });
      if (!microphoneReady) {
        const micMessage = state.browserVoice.lastIssue || "Mic permission denied.";
        updateWakeBanner(micMessage);
        if (!automatic) {
          addActivity("Microphone", micMessage, "error");
        }
        return false;
      }

      state.wakeModeEnabled = true;
      state.wakeModeGestureNeeded = false;
      state.commandRetryCount = 0;
      clearRecognitionStartTimer();

      if (state.busy || state.voicePhase === "processing" || state.voicePhase === "speaking") {
        updateWakeBanner(`Wake mode will arm as soon as AURA is free. Then say "${preferredWakePhrase()}".`);
        return true;
      }

      const started = await transitionRecognitionMode("wake", { automatic, resetCommandRetryCount: false });
      if (!started) {
        state.wakeModeEnabled = false;
        updateWakeBanner(state.browserVoice.lastIssue || currentWakeBanner());
        return false;
      }

      addActivity("Wake mode", `Standby listening is active for "${preferredWakePhrase()}".`, "good");
      updateWakeBanner(currentWakeBanner());
      return true;
    } finally {
      state.voiceActionInFlight = false;
      renderWakeControls();
    }
  }

  function disableWakeMode() {
    clearRecognitionStartTimer();
    state.wakeModeEnabled = false;
    state.wakeModeGestureNeeded = false;
    state.commandRetryCount = 0;
    state.recognitionHandoffPending = false;
    stopRecognition("manual");
    stopSpeech();
    clearBargeInState();
    setVoicePhase("idle");
    setIdleState();
    updateWakeBanner(currentWakeBanner());
    addActivity("Wake mode", "Standby listening was turned off.", "neutral");
  }

  async function startTalkCapture() {
    if (state.voiceActionInFlight) {
      return;
    }
    state.voiceActionInFlight = true;
    renderWakeControls();

    try {
      if (!canUseVoice() || state.busy || state.voicePhase === "processing" || state.voicePhase === "speaking") {
        updateWakeBanner(currentWakeBanner());
        return;
      }

      const microphoneReady = await refreshBrowserVoiceDiagnostics({ requestPermission: true });
      if (!microphoneReady) {
        updateWakeBanner(state.browserVoice.lastIssue || "Mic permission denied.");
        return;
      }

      const started = await transitionRecognitionMode("command", {
        automatic: false,
        resetCommandRetryCount: true,
      });
      if (!started) {
        updateWakeBanner("I couldn't start listening. Try again.");
      }
    } finally {
      state.voiceActionInFlight = false;
      renderWakeControls();
    }
  }

  function setupRecognition() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setBrowserVoiceDiagnostics({
        mode: "Browser voice is unavailable",
        permission: "Unsupported",
        inputDevice: "SpeechRecognition is not available here",
        lastIssue: "Use text commands or a browser with Web Speech support.",
      });
      renderWakeControls();
      return;
    }

    const recognition = new Recognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      clearRecognitionStartTimer();
      state.recognitionActive = true;
      state.recognitionStopReason = "running";
      state.partialTranscript = "";
      setBrowserVoiceDiagnostics({
        lastEvent: state.recognitionMode === "wake" ? "wake_standby" : "listening",
        lastIssue: state.recognitionMode === "wake"
          ? `Waiting for "${preferredWakePhrase()}".`
          : "Listening for your command.",
      });

      if (state.recognitionMode === "wake") {
        setVoicePhase("wake_listening");
        setAssistantState("idle", {
          pill: "Standby",
          kicker: "Standby",
          headline: "Wake mode is on.",
          description: `Say "${preferredWakePhrase()}" while this page stays open.`,
        });
      } else if (state.bargeInArmed && state.currentSpokenText) {
        setBrowserVoiceDiagnostics({
          lastEvent: "barge_in_ready",
          lastIssue: "Listening for a live interruption while AURA is speaking.",
        });
      } else {
        setVoicePhase("command_listening");
        setAssistantState("listening", {
          pill: "Listening",
          kicker: "Listening",
          headline: "Go ahead.",
          description: "I am listening for your request.",
        });
      }

      updateWakeBanner(currentWakeBanner());
    };

    recognition.onresult = (event) => {
      const results = Array.from(event.results || []);
      const finalTranscript = results
        .filter((result) => result.isFinal)
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim();
      const interimTranscript = results
        .filter((result) => !result.isFinal)
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim();
      const transcript = finalTranscript || interimTranscript;

      if (!transcript) {
        return;
      }

      state.partialTranscript = transcript;
      if (state.bargeInArmed && isLikelySpeechEcho(transcript)) {
        setBrowserVoiceDiagnostics({
          lastTranscript: transcript,
          heardSpeech: true,
          lastEvent: "barge_in_echo_ignored",
          lastIssue: "Ignoring AURA's own speech while waiting for an interruption.",
        });
        return;
      }

      if (state.bargeInArmed && !state.bargeInTriggered) {
        triggerBargeIn(transcript);
        if (!finalTranscript) {
          return;
        }
      }

      updateLiveTranscript(transcript);
      setBrowserVoiceDiagnostics({
        lastTranscript: transcript,
        heardSpeech: true,
        lastEvent: state.recognitionMode === "wake" ? "wake_heard" : "speech_heard",
        lastIssue: finalTranscript ? "Speech captured cleanly." : "Speech is coming in.",
      });
      logVoiceEvent("speech_result", {
        mode: state.recognitionMode,
        transcript,
        final: Boolean(finalTranscript),
      });

      if (!finalTranscript) {
        if (state.recognitionMode === "command") {
          if (state.voicePhase === "interrupted") {
            setVoicePhase("command_listening");
          }
          setAssistantState("listening", {
            pill: "Listening",
            kicker: "Listening",
            headline: "I'm listening.",
            description: "Keep going. I have your voice but I am waiting for the full command.",
          });
        }
        return;
      }

      const activeMode = state.recognitionMode;
      if (state.bargeInTriggered && activeMode === "command") {
        setVoicePhase("command_listening");
      }
      state.recognitionHandoffPending = true;
      stopRecognition("handoff");
      if (activeMode === "wake") {
        void handleWakeTranscript(finalTranscript);
      } else {
        void handleCommandTranscript(finalTranscript);
      }
    };

    recognition.onerror = (event) => {
      const code = String(event.error || "").trim().toLowerCase();
      const partialTranscript = String(state.partialTranscript || "").trim();
      const phaseBeforeError = state.voicePhase;
      state.recognitionActive = false;
      if (phaseBeforeError !== "speaking") {
        setVoicePhase("idle");
      }
      logVoiceEvent("speech_error", {
        mode: state.recognitionMode,
        error: code,
        partialTranscript,
      });

      if (state.recognitionHandoffPending && code === "aborted") {
        state.recognitionStopReason = "handoff";
        return;
      }

      if (code === "no-speech") {
        state.recognitionStopReason = "handled_no_speech";
        if (state.bargeInArmed && phaseBeforeError === "speaking") {
          state.bargeInArmed = false;
          return;
        }
        handleNoSpeechDetected(partialTranscript);
        return;
      }

      if (code === "aborted") {
        state.recognitionStopReason = "manual";
        setBrowserVoiceDiagnostics({
          lastEvent: "voice_aborted",
          lastIssue: partialTranscript ? "Listening stopped after partial speech." : "Listening was stopped.",
        });
        if (!state.busy && !state.speaking) {
          setIdleState();
        }
        return;
      }

      const permissionDenied = code === "not-allowed" || code === "service-not-allowed";
      const message = permissionDenied ? "Mic permission denied." : humanizeSpeechError(code);
      if (phaseBeforeError === "speaking") {
        state.bargeInArmed = false;
        if (permissionDenied) {
          state.wakeModeEnabled = false;
          state.wakeModeGestureNeeded = true;
        }
        setBrowserVoiceDiagnostics({
          lastEvent: "barge_in_error",
          permission: permissionDenied ? "Denied" : state.browserVoice.permission,
          lastIssue: message,
        });
        return;
      }
      state.recognitionStopReason = "handled_error";
      state.wakeModeEnabled = false;
      if (permissionDenied) {
        state.wakeModeEnabled = false;
        state.wakeModeGestureNeeded = true;
      } else {
        state.wakeModeGestureNeeded = false;
      }
      setBrowserVoiceDiagnostics({
        lastEvent: "voice_error",
        permission: permissionDenied ? "Denied" : state.browserVoice.permission,
        lastIssue: message,
      });
      setAssistantState("error", {
        pill: "Error",
        kicker: "Voice issue",
        headline: "I lost the microphone flow.",
        description: message,
      });
      updateWakeBanner(message);
      addActivity("Voice error", message, "error");
    };

    recognition.onend = () => {
      const endedMode = state.recognitionMode;
      const stopReason = state.recognitionStopReason || "idle";
      state.recognitionActive = false;
      state.recognitionMode = "off";
      if (state.voicePhase === "wake_listening" || state.voicePhase === "command_listening") {
        setVoicePhase("idle");
      }

      if (state.recognitionHandoffPending) {
        state.recognitionHandoffPending = false;
        state.recognitionStopReason = "idle";
        return;
      }

      if (!state.busy && !state.speaking) {
        setIdleState();
      }

      if (state.voicePhase === "speaking" && state.currentSpokenText && !state.bargeInTriggered) {
        state.bargeInArmed = false;
        window.setTimeout(() => {
          void armBargeInListener();
        }, 150);
        state.recognitionStopReason = "idle";
        return;
      }

      if (stopReason === "running" && state.wakeModeEnabled && !state.busy && !state.speaking) {
        scheduleRecognitionStart("wake", {
          reason: endedMode === "wake" ? "wake_end" : "return_to_standby",
        });
      }

      state.recognitionStopReason = "idle";
    };

    state.recognition = recognition;
    renderWakeControls();
  }

  function startRecognitionSession(mode, { automatic = false, resetCommandRetryCount = false } = {}) {
    if (!state.recognition) {
      return false;
    }
    if (!isVoiceAllowedHere()) {
      updateWakeBanner(currentWakeBanner());
      return false;
    }
    if (state.recognitionActive) {
      return false;
    }
    if (mode === "wake" && !state.wakeModeEnabled) {
      return false;
    }

    clearRecognitionStartTimer();
    state.recognitionMode = mode;
    state.recognitionStopReason = "starting";
    state.partialTranscript = "";
    if (mode === "command" && resetCommandRetryCount) {
      state.commandRetryCount = 0;
    }
    state.recognition.lang = preferredRecognitionLanguage();
    state.recognition.continuous = mode === "command" && state.bargeInArmed;
    state.recognition.interimResults = mode === "command";
    state.recognition.maxAlternatives = 1;

    try {
      state.recognition.start();
      logVoiceEvent("speech_start", { mode, automatic });
      return true;
    } catch (error) {
      if (!automatic) {
        updateWakeBanner(error.message || "Voice listening could not start.");
      }
      setBrowserVoiceDiagnostics({
        lastEvent: "start_failed",
        lastIssue: error.message || "Voice listening could not start.",
      });
      return false;
    }
  }

  function stopRecognition(reason = "manual") {
    if (!state.recognition || (!state.recognitionActive && state.recognitionMode === "off")) {
      return;
    }
    state.recognitionStopReason = reason;
    try {
      state.recognition.stop();
    } catch (_error) {
      // ignore browser stop races
    }
  }

  async function handleWakeTranscript(transcript) {
    updateLiveTranscript(transcript);
    const wakeMatch = detectWakePhrase(transcript);
    setBrowserVoiceDiagnostics({
      lastTranscript: transcript,
      heardSpeech: true,
      lastEvent: wakeMatch.detected ? "wake_match" : "wake_miss",
      lastIssue: wakeMatch.detected
        ? (wakeMatch.remainingText
          ? "Wake phrase matched. Using the spoken command now."
          : "Wake phrase matched. Waiting for your command.")
        : `Heard speech, but not "${preferredWakePhrase()}".`,
    });

    if (!wakeMatch.detected) {
      logVoiceEvent("wake_miss", { transcript });
      addActivity("Standby", "Heard speech, but the wake phrase was not detected.", "neutral");
      updateWakeBanner(`Standby is active. Say "${preferredWakePhrase()}" to wake AURA.`);
      setVoicePhase("idle");
      setIdleState();
      if (state.wakeModeEnabled && !state.busy && state.voicePhase === "idle") {
        scheduleRecognitionStart("wake", {
          delay: NO_SPEECH_RECOVERY_DELAY_MS,
          automatic: true,
          reason: "wake_miss",
        });
      }
      return;
    }

    logVoiceEvent("wake_detected", {
      transcript,
      remainingText: wakeMatch.remainingText,
    });
    addActivity("Wake detected", `AURA heard ${preferredWakePhrase()}.`, "good");

    if (!wakeMatch.remainingText) {
      updateLiveResponse(WAKE_ACKNOWLEDGEMENT, { provider: "local_wake", mode: "wake" });
      setAssistantState("listening", {
        pill: "Listening",
        kicker: "Wake detected",
        headline: "Yes?",
        description: "I'm listening for your command now.",
      });
      updateWakeBanner("Wake detected. Go ahead.");
      await speakAssistant(WAKE_ACKNOWLEDGEMENT, { resumeWakeAfter: false });
      await transitionRecognitionMode("command", {
        automatic: true,
        resetCommandRetryCount: true,
      });
      return;
    }

    await processVoiceCommand(wakeMatch.remainingText);
  }

  async function handleCommandTranscript(transcript) {
    const cleanedTranscript = String(transcript || "").trim();
    if (!cleanedTranscript) {
      handleNoSpeechDetected("");
      return;
    }
    updateLiveTranscript(cleanedTranscript);
    await processVoiceCommand(cleanedTranscript);
  }

  async function processVoiceCommand(transcript) {
    const commandText = String(transcript || "").trim();
    if (!commandText) {
      handleNoSpeechDetected("");
      return;
    }

    state.bargeInTriggered = false;
    setVoicePhase("processing");
    setAssistantState("thinking", {
      pill: "Thinking",
      kicker: "Working",
      headline: "One second.",
      description: "I'm working through that now.",
    });
    updateWakeBanner("Working on that now.");

    try {
      const payload = await submitChatMessage(commandText);
      const assistantPayload = extractAssistantReplyPayload(payload);
      const answer = assistantPayload.answer || FALLBACK_REPLY;
      const provider = assistantPayload.provider || "local";

      state.currentProvider = provider;
      updateLiveTranscript(commandText);
      updateLiveResponse(answer, { provider, mode: "voice" });
      addActivity("Voice request", commandText, "neutral");
      addActivity("Answer ready", answer.slice(0, 140), assistantPayload.success === false ? "warn" : "good");
      await speakAssistant(answer, { resumeWakeAfter: true });
    } catch (error) {
      if (error?.name === "AbortError") {
        setVoicePhase("idle");
        setIdleState();
        return;
      }
      handleAssistantFailure(error.message || FALLBACK_REPLY);
    }
  }

  async function submitTextCommand() {
    if (state.busy) {
      return;
    }

    const text = String(el.textCommandInput.value || "").trim();
    if (!text) {
      return;
    }

    el.textCommandInput.value = "";
    updateLiveTranscript(text);
    if (state.recognitionActive) {
      state.recognitionHandoffPending = true;
      stopRecognition();
      await waitForRecognitionIdle();
    }
    setAssistantState("thinking", {
      pill: "Thinking",
      kicker: "Text command",
      headline: "One second.",
      description: "I'm working through that now.",
    });

    try {
      const payload = await submitChatMessage(text);
      const assistantPayload = extractAssistantReplyPayload(payload);
      const answer = assistantPayload.answer || FALLBACK_REPLY;
      const provider = assistantPayload.provider || "local";
      state.currentProvider = provider;
      updateLiveResponse(answer, { provider, mode: assistantPayload.mode || "text" });
      addActivity("Text command", text, "neutral");
      addActivity("Answer ready", answer.slice(0, 140), assistantPayload.success === false ? "warn" : "good");

      await speakAssistant(answer, { resumeWakeAfter: false });

      if (assistantPayload.success === false || assistantPayload.degraded) {
        setAssistantState("error", {
          pill: "Degraded",
          kicker: "Fallback answer",
          headline: "I still have an answer for you.",
          description: assistantPayload.error || assistantRuntimeMessage(),
        });
      } else {
        setIdleState();
      }
      updateWakeBanner(currentWakeBanner());
    } catch (error) {
      if (error?.name === "AbortError") {
        setIdleState();
        return;
      }
      handleAssistantFailure(error.message || FALLBACK_REPLY);
    } finally {
      resumeWakeStandby();
    }
  }

  function handleTextInputKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitTextCommand();
    }
  }

  async function submitChatMessage(message) {
    return requestJson("/api/chat", {
      message,
      mode: "hybrid",
    }, {
      timeoutMs: CHAT_REQUEST_TIMEOUT_MS,
    });
  }

  async function requestJson(url, payload, { timeoutMs = 0 } = {}) {
    if (state.currentRequestController) {
      state.currentRequestController.abort();
    }

    const controller = new AbortController();
    let timedOut = false;
    let timeoutId = null;
    state.currentRequestController = controller;
    state.busy = true;
    renderWakeControls();

    try {
      if (timeoutMs > 0) {
        timeoutId = window.setTimeout(() => {
          timedOut = true;
          controller.abort();
        }, timeoutMs);
      }

      const response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-AURA-Session-Id": state.sessionId,
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      let body = {};
      try {
        body = await response.json();
      } catch (_error) {
        body = {};
      }

      if (!response.ok && !body.content && !body.reply && !body.result) {
        throw new Error(body.error || `Request failed (${response.status})`);
      }
      if (response.ok && !body.content && !body.reply && !body.result && body.success !== false) {
        throw new Error("The assistant returned an empty response.");
      }
      return body;
    } catch (error) {
      if (timedOut) {
        throw new Error("The assistant took too long to respond. Try again.");
      }
      if (error?.name === "AbortError") {
        throw error;
      }
      throw error;
    } finally {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      if (state.currentRequestController === controller) {
        state.currentRequestController = null;
      }
      state.busy = false;
      renderWakeControls();
    }
  }

  function extractAssistantReplyPayload(payload) {
    const safePayload = payload && typeof payload === "object" ? payload : {};
    const nestedResult = safePayload.result && typeof safePayload.result === "object" ? safePayload.result : {};
    const answer = normalizeAssistantText(
      safePayload.content
        || safePayload.reply
        || nestedResult.content
        || nestedResult.reply
        || nestedResult.response
        || "",
    );

    return {
      answer,
      provider: safePayload.provider || nestedResult.provider || "local",
      mode: safePayload.mode || nestedResult.mode || "text",
      success: safePayload.success !== false && nestedResult.success !== false,
      degraded: Boolean(safePayload.degraded || nestedResult.degraded || safePayload.status === "degraded"),
      error: safePayload.error || nestedResult.error || "",
    };
  }

  function interruptAssistant() {
    if (state.currentRequestController) {
      state.currentRequestController.abort();
      state.currentRequestController = null;
    }
    clearRecognitionStartTimer();
    stopRecognition("manual");
    stopSpeech();
    clearBargeInState();
    addActivity("Interrupted", "The current assistant action was stopped.", "warn");
    setVoicePhase("idle");
    setIdleState();
    if (state.wakeModeEnabled) {
      scheduleRecognitionStart("wake", {
        reason: "interrupt",
      });
    }
  }

  function stopSpeech() {
    const wasSpeaking = state.voicePhase === "speaking";
    state.activeSpeechRunId += 1;
    state.currentUtterance = null;
    state.bargeInArmed = false;
    state.currentSpokenText = "";
    if (window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
      } catch (_error) {
        // ignore browser cancellation races
      }
    }
    if (wasSpeaking) {
      setVoicePhase("idle");
    } else {
      renderWakeControls();
    }
  }

  async function speakAssistant(text, { resumeWakeAfter = true } = {}) {
    const spokenText = prepareSpokenText(text);
    if (!spokenText) {
      if (resumeWakeAfter) {
        setIdleState();
        resumeWakeStandby();
      }
      return;
    }

    if (!window.speechSynthesis || typeof window.SpeechSynthesisUtterance === "undefined") {
      addActivity("Voice", "Browser speech synthesis is unavailable here.", "warn");
      setVoicePhase("idle");
      if (resumeWakeAfter) {
        setIdleState();
        resumeWakeStandby();
      }
      return;
    }

    stopSpeech();
    state.currentSpokenText = spokenText;
    state.bargeInTriggered = false;
    const speechRunId = state.activeSpeechRunId;

    await new Promise((resolve) => {
      let settled = false;
      const utterance = new SpeechSynthesisUtterance(spokenText);
      state.currentUtterance = utterance;
      utterance.lang = preferredSpeechLanguage();
      utterance.rate = 1;
      utterance.pitch = 1;
      utterance.volume = 1;

      const finishSpeech = () => {
        if (settled) {
          return;
        }
        settled = true;
        if (state.activeSpeechRunId === speechRunId && state.currentUtterance === utterance) {
          state.currentUtterance = null;
          clearBargeInState();
          setVoicePhase("idle");
        }
        resolve();
      };

      utterance.onstart = () => {
        if (state.activeSpeechRunId !== speechRunId || state.currentUtterance !== utterance) {
          return;
        }
        setVoicePhase("speaking");
        setAssistantState("speaking", {
          pill: "Speaking",
          kicker: "Responding",
          headline: "Done.",
          description: "I have the answer for you.",
        });
        window.setTimeout(() => {
          void armBargeInListener();
        }, 120);
      };

      utterance.onend = finishSpeech;

      utterance.onerror = () => {
        addActivity("Voice", "Browser speech playback could not finish cleanly.", "warn");
        finishSpeech();
      };

      window.setTimeout(() => {
        if (state.activeSpeechRunId !== speechRunId || state.currentUtterance !== utterance) {
          finishSpeech();
          return;
        }
        try {
          window.speechSynthesis.speak(utterance);
        } catch (_error) {
          finishSpeech();
        }
      }, 0);
    });

    if (resumeWakeAfter) {
      setIdleState();
      resumeWakeStandby();
    }
  }

  function handleAssistantFailure(message) {
    const safeMessage = normalizeAssistantText(message || FALLBACK_REPLY) || FALLBACK_REPLY;
    setVoicePhase("idle");
    updateLiveResponse(safeMessage, { provider: "degraded", mode: "fallback" });
    addActivity("Assistant issue", safeMessage, "error");
    setAssistantState("error", {
      pill: "Error",
      kicker: "Assistant issue",
      headline: "I couldn't complete that cleanly.",
      description: safeMessage,
    });
    updateWakeBanner(safeMessage);
    resumeWakeStandby();
  }

  function setIdleState() {
    const wakePhrase = preferredWakePhrase();
    const standbyActive = state.voicePhase === "wake_listening";
    setAssistantState("idle", {
      pill: standbyActive ? "Standby" : "Idle",
      kicker: standbyActive ? "Standby" : "Idle",
      headline: standbyActive ? "Wake mode is on." : "Ready when you are.",
      description: standbyActive
        ? `Say "${wakePhrase}" while this page stays open.`
        : "Use Wake mode, Talk, or the text command field when you want me.",
    });
    updateWakeBanner(currentWakeBanner());
  }

  function resumeWakeStandby() {
    if (!state.wakeModeEnabled || state.recognitionActive || state.busy || state.voicePhase !== "idle") {
      return;
    }
    scheduleRecognitionStart("wake", {
      reason: "resume_standby",
    });
  }

  function setAssistantState(stateName, copy) {
    el.body.dataset.assistantState = stateName;
    el.statePillLabel.textContent = copy.pill;
    el.stateKicker.textContent = copy.kicker;
    el.stateHeadline.textContent = copy.headline;
    el.stateDescription.textContent = copy.description;
  }

  function updateLiveTranscript(text) {
    el.liveTranscript.textContent = text || "Waiting for your voice or text command.";
  }

  function updateLiveResponse(text, { provider = null, mode = null } = {}) {
    el.liveResponse.textContent = text || "AURA is standing by.";
    if (provider) {
      el.responseMetaProvider.textContent = `Provider: ${humanizeProviderName(provider)}`;
    }
    if (mode) {
      el.responseMetaMode.textContent = `Mode: ${mode}`;
    }
  }

  function updateWakeBanner(text) {
    el.wakeBanner.textContent = text;
  }

  function currentWakeBanner() {
    if (!state.recognition) {
      return "Browser wake mode is not available here. Text commands still work.";
    }
    if (!isVoiceAllowedHere()) {
      return "Wake mode needs localhost or HTTPS in this browser.";
    }
    if (state.voicePhase === "wake_listening") {
      return `Wake mode is on. Say "${preferredWakePhrase()}" while this page stays open.`;
    }
    if (state.voicePhase === "interrupted") {
      return "Interrupted. Listening for your command now.";
    }
    if (state.voicePhase === "command_listening") {
      return "Listening for your command now.";
    }
    if (state.voicePhase === "processing") {
      return "Working on your request now.";
    }
    if (state.voicePhase === "speaking") {
      return "Responding now.";
    }
    if (state.wakeModeEnabled) {
      return `Wake mode is ready. Say "${preferredWakePhrase()}" when you're ready.`;
    }
    if (state.wakeModeGestureNeeded) {
      return `Wake mode needs one tap before "${preferredWakePhrase()}" can work in this browser.`;
    }
    if (state.auth?.authenticated) {
      return `Wake mode is available. Tap Wake mode if the browser still needs microphone permission, then say "${preferredWakePhrase()}".`;
    }
    return publicWakeBanner();
  }

  function publicWakeBanner() {
    return `Public mode keeps text and one-tap Talk available now. Sign in if you want standby wake mode for "${preferredWakePhrase()}".`;
  }

  function currentRuntime() {
    return state.providerSnapshot?.assistant_runtime || state.systemHealth?.assistant_runtime || {};
  }

  function assistantRuntimeMessage() {
    return currentRuntime().message || "AURA is routing around an unhealthy path right now.";
  }

  function preferredWakePhrase() {
    return state.voiceStatus?.wake_word?.default_phrase || state.voiceStatus?.settings?.wake_words?.[0] || WAKE_FALLBACK;
  }

  function preferredRecognitionLanguage() {
    return state.voiceStatus?.settings?.language || "en-US";
  }

  function preferredSpeechLanguage() {
    return state.voiceStatus?.settings?.language || "en-US";
  }

  function isVoiceAllowedHere() {
    return Boolean(window.isSecureContext || window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");
  }

  function canUseVoice() {
    return Boolean(state.recognition && isVoiceAllowedHere());
  }

  function normalizeWakeText(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[.,/#!$%^&*;:{}=_`~()?"']/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function buildWakeVariants(wakeWord) {
    const canonical = normalizeWakeText(wakeWord);
    if (!canonical) {
      return [];
    }
    const variants = new Set([
      canonical,
      canonical.replace(/^hey\s+/, "hi "),
      canonical.replace(/^hey\s+/, "hello "),
      canonical.replace(/^hey\s+/, "heya "),
      canonical.replace(/\baura\b/g, "ora"),
    ]);
    return Array.from(variants).filter(Boolean);
  }

  function detectWakePhrase(transcript) {
    const wakeWords = state.voiceStatus?.settings?.wake_words || [WAKE_FALLBACK];
    const normalized = normalizeWakeText(transcript);

    for (const wakeWord of wakeWords) {
      const variants = buildWakeVariants(wakeWord);
      for (const candidate of variants) {
        const pattern = new RegExp(`^(?:${escapeRegex(candidate)})(?:\\s+|$)`);
        if (pattern.test(normalized)) {
          return {
            detected: true,
            wakeWord: candidate,
            remainingText: normalized.replace(pattern, "").trim(),
          };
        }
      }
    }

    return {
      detected: false,
      wakeWord: null,
      remainingText: normalized,
    };
  }

  async function fetchJson(url) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: {
        "X-AURA-Session-Id": state.sessionId,
      },
    });

    let payload = {};
    try {
      payload = await response.json();
    } catch (_error) {
      payload = {};
    }

    if (!response.ok) {
      throw new Error(payload.error || payload.detail || `Request failed (${response.status})`);
    }
    return payload;
  }

  function scheduleRefresh() {
    if (state.refreshIntervalId) {
      window.clearInterval(state.refreshIntervalId);
    }
    state.refreshIntervalId = window.setInterval(() => {
      if (document.hidden || state.refreshInFlight || state.recognitionActive || state.busy || state.speaking) {
        return;
      }
      void refreshStatus({ quiet: true });
    }, REFRESH_INTERVAL_MS);
  }

  function ensureSessionId() {
    const existing = localStorage.getItem(STORAGE_KEYS.sessionId);
    if (existing) {
      return existing;
    }
    const generated = `live-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(STORAGE_KEYS.sessionId, generated);
    return generated;
  }

  function readBoolean(key, fallback) {
    const raw = localStorage.getItem(key);
    if (raw === null) {
      return fallback;
    }
    return raw === "true";
  }

  function humanizeProviderName(value) {
    const normalized = String(value || "").trim();
    if (!normalized) {
      return "No data yet";
    }
    return normalized.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
  }

  function humanizeStatus(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (!normalized) {
      return "No data yet";
    }
    return normalized.replace(/_/g, " ");
  }

  function humanizeSpeechError(code) {
    const normalized = String(code || "").trim().toLowerCase();
    const messages = {
      "no-speech": "I did not hear anything clearly enough to continue.",
      aborted: "Listening was stopped.",
      "audio-capture": "No microphone input is available.",
      "not-allowed": "Mic permission denied.",
      "service-not-allowed": "Mic permission denied.",
      network: "The browser voice service is unavailable right now.",
    };
    return messages[normalized] || "The voice path could not continue.";
  }

  function normalizeAssistantText(value) {
    return String(value || "")
      .replace(/\r\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function prepareSpokenText(text) {
    const cleaned = String(text || "")
      .replace(/```[\s\S]*?```/g, "I've prepared the code for you.")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/#{1,6}\s*/g, "")
      .replace(/(?:^|\s)\d+\.\s+/g, ". ")
      .replace(/\n\s*-\s+/g, ". ")
      .replace(/\n+/g, " ")
      .replace(/\s{2,}/g, " ")
      .trim();

    if (!cleaned) {
      return "";
    }

    const sentences = cleaned.match(/[^.!?]+[.!?]?/g) || [cleaned];
    const preview = sentences
      .map((sentence) => sentence.trim())
      .filter(Boolean)
      .slice(0, 3)
      .join(" ")
      .trim();

    if (cleaned.length > 360 && sentences.length > 3) {
      return `${preview} I have the rest on screen.`;
    }

    return cleaned;
  }

  function formatTime(date) {
    return new Intl.DateTimeFormat([], {
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  }

  function escapeRegex(value) {
    return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }
})();
