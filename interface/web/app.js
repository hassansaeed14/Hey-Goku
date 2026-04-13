(() => {
  const STORAGE_KEYS = {
    sessionId: "aura_live_session_id",
    detailsOpen: "aura_details_open",
  };
  const SESSION_GREETING_PREFIX = "aura_session_greeted:";

  const FALLBACK_REPLY = "Something went wrong on my side. Try again.";
  const WAKE_FALLBACK = "Hey AURA";
  const COMMAND_NO_SPEECH_RETRY_LIMIT = 1;
  const REFRESH_INTERVAL_MS = 120000;
  const PROVIDER_REFRESH_INTERVAL_MS = 300000;
  const WAKE_RESUME_DELAY_MS = 900;
  const NO_SPEECH_RECOVERY_DELAY_MS = 1400;

  const state = {
    sessionId: "default",
    detailsOpen: false,
    auth: null,
    providerSnapshot: null,
    systemHealth: null,
    voiceStatus: null,
    currentProvider: null,
    wakeModeEnabled: false,
    wakeModeGestureNeeded: false,
    recognition: null,
    recognitionActive: false,
    recognitionMode: "off",
    recognitionHandoffPending: false,
    listening: false,
    busy: false,
    speaking: false,
    partialTranscript: "",
    commandRetryCount: 0,
    currentRequestController: null,
    refreshInFlight: false,
    refreshQueuedForce: false,
    lastProviderRefreshAt: 0,
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

  document.addEventListener("DOMContentLoaded", init);

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
    el.refreshStatusButton.addEventListener("click", () => refreshStatus({ force: true }));
    el.wakeModeButton.addEventListener("click", () => void toggleWakeMode());
    el.talkButton.addEventListener("click", () => void startTalkCapture());
    el.interruptButton.addEventListener("click", interruptAssistant);
    el.sendButton.addEventListener("click", () => void submitTextCommand());
    el.textCommandInput.addEventListener("keydown", handleTextInputKeydown);
    el.assistantCoreButton.addEventListener("click", () => void handleCoreButtonClick());
    window.addEventListener("resize", handleResize);
  }

  async function bootstrap() {
    const [authResult, providersResult, healthResult, voiceResult] = await Promise.allSettled([
      fetchJson("/api/auth/session"),
      fetchJson("/api/providers"),
      fetchJson("/api/system/health"),
      fetchJson("/api/voice/status"),
    ]);

    if (authResult.status === "fulfilled") {
      state.auth = authResult.value;
    }
    if (providersResult.status === "fulfilled") {
      state.providerSnapshot = providersResult.value;
    }
    if (healthResult.status === "fulfilled") {
      state.systemHealth = healthResult.value;
    }
    if (voiceResult.status === "fulfilled") {
      state.voiceStatus = voiceResult.value;
    }

    renderStatusSurfaces();
    state.lastProviderRefreshAt = state.providerSnapshot ? Date.now() : state.lastProviderRefreshAt;
    await maybeTriggerSessionGreeting("bootstrap");

    if (state.auth?.authenticated) {
      await attemptAutomaticWakeStandby();
    } else {
      updateWakeBanner(publicWakeBanner());
    }
  }

  async function refreshStatus({ force = false, quiet = false } = {}) {
    if (state.refreshInFlight) {
      state.refreshQueuedForce = state.refreshQueuedForce || force;
      return;
    }

    state.refreshInFlight = true;
    const refreshSuffix = force ? "?refresh=1" : "";
    const providerRefreshDue =
      force || !state.providerSnapshot || (Date.now() - state.lastProviderRefreshAt) >= PROVIDER_REFRESH_INTERVAL_MS;

    try {
      const [authResult, providersResult, healthResult, voiceResult] = await Promise.allSettled([
        fetchJson("/api/auth/session"),
        providerRefreshDue ? fetchJson(`/api/providers${refreshSuffix}`) : Promise.resolve(state.providerSnapshot),
        fetchJson("/api/system/health"),
        fetchJson("/api/voice/status"),
      ]);

      if (authResult.status === "fulfilled") {
        state.auth = authResult.value;
      }
      if (providersResult.status === "fulfilled" && providersResult.value) {
        state.providerSnapshot = providersResult.value;
        state.lastProviderRefreshAt = Date.now();
      }
      if (healthResult.status === "fulfilled") {
        state.systemHealth = healthResult.value;
      }
      if (voiceResult.status === "fulfilled") {
        state.voiceStatus = voiceResult.value;
      }

      renderStatusSurfaces();
      const greeted = await maybeTriggerSessionGreeting(force ? "manual_refresh" : "refresh");
      if (greeted && state.auth?.authenticated && !state.wakeModeEnabled) {
        await attemptAutomaticWakeStandby();
      }
      if (!quiet && !state.busy && !state.speaking && !state.listening) {
        updateWakeBanner(currentWakeBanner());
      }
    } finally {
      state.refreshInFlight = false;
      if (state.refreshQueuedForce) {
        state.refreshQueuedForce = false;
        window.setTimeout(() => {
          void refreshStatus({ force: true, quiet: true });
        }, 150);
      }
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
    el.wakeModeStatus.textContent = state.wakeModeEnabled ? "Standby on" : "Standby off";
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
    const items = state.providerSnapshot?.items || [];
    el.providersList.innerHTML = "";

    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "provider-empty";
      empty.textContent = "No provider data yet.";
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
    const diagnostics = state.browserVoice || {};
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
    el.wakeModeButton.textContent = state.wakeModeEnabled ? "Wake mode on" : "Wake mode";
    el.talkButton.disabled = !canUseVoice();
    el.interruptButton.disabled = !(state.busy || state.speaking || state.listening || state.recognitionActive);
  }

  function setBrowserVoiceDiagnostics(patch) {
    state.browserVoice = {
      ...state.browserVoice,
      ...patch,
    };
    renderVoiceDiagnostics();
  }

  function browserPermissionLabel(value) {
    const normalized = String(value || "").trim().toLowerCase();
    const labels = {
      granted: "Granted",
      prompt: "Needs permission",
      denied: "Denied",
      unsupported: "Unsupported",
      unknown: "Unknown",
      "not-allowed": "Denied",
      "service-not-allowed": "Blocked",
    };
    return labels[normalized] || humanizeStatus(normalized) || "Unknown";
  }

  function logVoiceEvent(eventName, details = {}) {
    const payload = {
      event: eventName,
      ...details,
      mode: details.mode || state.recognitionMode,
      at: new Date().toISOString(),
    };
    setBrowserVoiceDiagnostics({
      lastEvent: eventName,
    });
    try {
      console.info("[AURA voice]", payload);
    } catch (_error) {
      // ignore console failures
    }
  }

  function clearRecognitionStartTimer() {
    if (state.recognitionStartTimer) {
      window.clearTimeout(state.recognitionStartTimer);
      state.recognitionStartTimer = null;
    }
  }

  function scheduleRecognitionStart(
    mode,
    {
      delayMs = WAKE_RESUME_DELAY_MS,
      automatic = true,
      resetCommandRetryCount = false,
      reason = "scheduled_restart",
    } = {},
  ) {
    clearRecognitionStartTimer();
    state.recognitionStartTimer = window.setTimeout(() => {
      state.recognitionStartTimer = null;
      if (mode === "wake") {
        if (!state.wakeModeEnabled || state.recognitionActive || state.busy || state.speaking) {
          return;
        }
      } else if (state.recognitionActive || state.busy || state.speaking) {
        return;
      }
      logVoiceEvent("speech_restart", { mode, reason, automatic });
      startRecognitionSession(mode, { automatic, resetCommandRetryCount });
    }, delayMs);
  }

  function sessionGreetingKey() {
    const user = state.auth?.user;
    if (!state.auth?.authenticated || !user) {
      return null;
    }
    const identity = user.id || user.username || "user";
    const loginStamp = user.last_login || user.created || "session";
    return `${SESSION_GREETING_PREFIX}${identity}:${loginStamp}:${state.sessionId}`;
  }

  function buildSessionGreeting() {
    const user = state.auth?.user || {};
    const preferredName = user.preferred_name || user.name || user.username || "";
    const options = preferredName
      ? [
          `Welcome back, ${preferredName}.`,
          `Good to see you again, ${preferredName}.`,
          `${preferredName}, I'm ready when you are.`,
        ]
      : [
          "Welcome back.",
          "Good to see you again.",
          "You're back. Ready when you are.",
        ];
    const seed = `${preferredName}:${user.last_login || user.created || ""}:${state.sessionId}`;
    return options[seed.length % options.length];
  }

  function shouldSpeakGreeting() {
    return Boolean(
      state.auth?.authenticated
      && state.voiceStatus?.settings?.auto_speak_responses
      && window.speechSynthesis,
    );
  }

  async function maybeTriggerSessionGreeting(source = "session") {
    const greetingKey = sessionGreetingKey();
    if (!greetingKey || window.sessionStorage.getItem(greetingKey) === "1") {
      return false;
    }

    window.sessionStorage.setItem(greetingKey, "1");
    const greeting = buildSessionGreeting();
    updateLiveTranscript("Authenticated session active.");
    updateLiveResponse(greeting, { provider: "local", mode: "greeting" });
    addActivity("Greeting", `Session greeting triggered from ${source}.`, "good");
    updateWakeBanner(greeting);

    if (shouldSpeakGreeting()) {
      await speakAssistant(greeting, { resumeWakeAfter: false });
    }

    setIdleState();
    return true;
  }

  function handleNoSpeechDetected(partialTranscript) {
    const captured = String(partialTranscript || "").trim();
    const mode = state.recognitionMode;

    if (captured.length >= 2) {
      state.recognitionHandoffPending = true;
      setBrowserVoiceDiagnostics({
        lastTranscript: captured,
        heardSpeech: true,
        lastEvent: "partial_speech_recovered",
        lastIssue: "AURA recovered the partial transcript it heard.",
      });
      addActivity("Speech recovered", captured, "neutral");
      if (mode === "wake") {
        void handleWakeTranscript(captured);
      } else {
        void handleCommandTranscript(captured);
      }
      return;
    }

    if (mode === "command") {
      const canRetry = state.commandRetryCount < COMMAND_NO_SPEECH_RETRY_LIMIT;
      const message = canRetry
        ? "I didn't catch that. Please say the command again."
        : "I did not hear enough to continue. Returning to standby.";
      state.commandRetryCount += canRetry ? 1 : 0;
      setBrowserVoiceDiagnostics({
        heardSpeech: false,
        lastEvent: "command_no_speech",
        lastIssue: message,
      });
      setAssistantState("no_speech", {
        pill: "No speech",
        kicker: "Listening",
        headline: canRetry ? "I didn't catch that." : "No speech heard.",
        description: canRetry
          ? "Try the command once more."
          : "I'll return to standby and keep wake mode ready.",
      });
      updateWakeBanner(message);
      addActivity("No speech", message, "warn");
      if (canRetry) {
        state.recognitionHandoffPending = true;
        scheduleRecognitionStart("command", {
          delayMs: NO_SPEECH_RECOVERY_DELAY_MS,
          automatic: false,
          resetCommandRetryCount: false,
          reason: "command_no_speech_retry",
        });
        return;
      }
      state.commandRetryCount = 0;
      state.recognitionHandoffPending = true;
      setIdleState();
      resumeWakeStandby({ delayMs: NO_SPEECH_RECOVERY_DELAY_MS, reason: "command_no_speech" });
      return;
    }

    const wakeMessage = `Standby is still on. Say "${preferredWakePhrase()}" when you're ready.`;
    setBrowserVoiceDiagnostics({
      heardSpeech: false,
      lastEvent: "wake_no_speech",
      lastIssue: wakeMessage,
    });
    setAssistantState("no_speech", {
      pill: "Standby",
      kicker: "No speech",
      headline: "I didn't catch the wake phrase.",
      description: `I'm still standing by for "${preferredWakePhrase()}".`,
    });
    updateWakeBanner(wakeMessage);
    addActivity("Standby", "No wake phrase was heard clearly enough.", "neutral");
    state.recognitionHandoffPending = true;
    setIdleState();
    resumeWakeStandby({ delayMs: NO_SPEECH_RECOVERY_DELAY_MS, reason: "wake_no_speech" });
  }

  async function refreshBrowserVoiceDiagnostics({ requestPermission = false } = {}) {
    const mode = state.voiceStatus?.wake_word?.mode === "browser_assisted"
      ? "Browser-assisted wake mode"
      : "Browser voice";
    const updates = {
      mode,
    };

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
        void startTalkCapture();
        return;
      }
      await toggleWakeMode();
      return;
    }

    void startTalkCapture();
  }

  async function toggleWakeMode() {
    if (state.wakeModeEnabled) {
      disableWakeMode();
      return;
    }

    await enableWakeMode({ automatic: false });
  }

  async function enableWakeMode({ automatic = false } = {}) {
    if (!canUseVoice()) {
      updateWakeBanner(currentWakeBanner());
      return false;
    }

    const microphoneReady = await refreshBrowserVoiceDiagnostics({ requestPermission: !automatic });
    if (!automatic && !microphoneReady) {
      updateWakeBanner("Microphone access is needed before wake mode can start.");
      addActivity("Microphone", "Wake mode could not start because the browser microphone is not ready.", "error");
      return false;
    }
    if (automatic && !microphoneReady) {
      return false;
    }

    state.wakeModeEnabled = true;
    state.wakeModeGestureNeeded = false;

    if (state.busy || state.speaking) {
      renderWakeControls();
      updateWakeBanner(`Wake mode will arm as soon as AURA is free. Then say "${preferredWakePhrase()}".`);
      return true;
    }

    if (state.recognitionActive && state.recognitionMode !== "wake") {
      stopRecognition();
    }

    const started = startRecognitionSession("wake", { automatic });
    if (!started) {
      state.wakeModeEnabled = false;
      state.wakeModeGestureNeeded = automatic;
      renderWakeControls();
      updateWakeBanner(currentWakeBanner());
      return false;
    }

    addActivity("Wake mode", `Standby listening is active for "${preferredWakePhrase()}".`, "good");
    renderWakeControls();
    updateWakeBanner(currentWakeBanner());
    return true;
  }

  function disableWakeMode() {
    state.wakeModeEnabled = false;
    state.wakeModeGestureNeeded = false;
    clearRecognitionStartTimer();
    if (state.recognitionMode === "wake" || (!state.busy && !state.speaking)) {
      stopRecognition();
    }
    renderWakeControls();
    setIdleState();
    updateWakeBanner(currentWakeBanner());
    addActivity("Wake mode", "Standby listening was turned off.", "neutral");
  }

  async function startTalkCapture() {
    if (!canUseVoice()) {
      updateWakeBanner(currentWakeBanner());
      return;
    }
    if (state.busy) {
      return;
    }

    if (state.recognitionActive) {
      stopRecognition();
    }

    const microphoneReady = await refreshBrowserVoiceDiagnostics({ requestPermission: true });
    if (!microphoneReady) {
      updateWakeBanner("Microphone access is needed before AURA can listen.");
      return;
    }

    startRecognitionSession("command", { automatic: false, resetCommandRetryCount: true });
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
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      state.recognitionActive = true;
      state.listening = true;
      state.partialTranscript = "";
      state.recognitionHandoffPending = false;
      setBrowserVoiceDiagnostics({
        lastEvent: state.recognitionMode === "wake" ? "wake_standby" : "listening",
        lastIssue: state.recognitionMode === "wake"
          ? `Waiting for "${preferredWakePhrase()}".`
          : "Listening for your command.",
      });
      renderWakeControls();
      if (state.recognitionMode === "wake") {
        setAssistantState("idle", {
          pill: "Standby",
          kicker: "Standby",
          headline: "Wake mode is on.",
          description: `Say "${preferredWakePhrase()}" while this page stays open.`,
        });
      } else {
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
          setAssistantState("listening", {
            pill: "Listening",
            kicker: "Listening",
            headline: "I'm listening.",
            description: "Keep going. I have your voice but I am waiting for the full command.",
          });
        }
        return;
      }

      state.recognitionHandoffPending = true;

      if (state.recognitionMode === "wake") {
        stopRecognition();
        void handleWakeTranscript(finalTranscript);
        return;
      }

      stopRecognition();
      void handleCommandTranscript(finalTranscript);
    };

    recognition.onerror = (event) => {
      state.recognitionActive = false;
      state.listening = false;
      renderWakeControls();
      const code = String(event.error || "").trim().toLowerCase();
      const partialTranscript = String(state.partialTranscript || "").trim();
      logVoiceEvent("speech_error", {
        mode: state.recognitionMode,
        error: code,
        partialTranscript,
      });

      if (code === "no-speech") {
        handleNoSpeechDetected(partialTranscript);
        return;
      }

      if (code === "aborted") {
        setBrowserVoiceDiagnostics({
          lastEvent: "speech_aborted",
          lastIssue: "Listening was stopped.",
        });
        if (state.wakeModeEnabled && !state.busy && !state.speaking) {
          state.recognitionHandoffPending = true;
          setIdleState();
          resumeWakeStandby({ reason: "speech_aborted" });
        }
        return;
      }

      const message = humanizeSpeechError(code);
      setBrowserVoiceDiagnostics({
        lastEvent: "voice_error",
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
      state.recognitionActive = false;
      state.listening = false;
      renderWakeControls();
      if (state.recognitionHandoffPending) {
        state.recognitionHandoffPending = false;
        return;
      }
      if (state.wakeModeEnabled && !state.busy && !state.speaking) {
        resumeWakeStandby({ reason: "recognition_end" });
        setIdleState();
        return;
      }
      if (!state.busy && !state.speaking) {
        setIdleState();
      }
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

    clearRecognitionStartTimer();
    state.recognitionMode = mode;
    state.partialTranscript = "";
    if (mode === "command" && resetCommandRetryCount) {
      state.commandRetryCount = 0;
    }
    state.recognition.lang = preferredRecognitionLanguage();
    state.recognition.continuous = mode === "command";
    state.recognition.interimResults = mode === "command";
    state.recognition.maxAlternatives = mode === "command" ? 2 : 1;

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

  function stopRecognition() {
    if (!state.recognition || !state.recognitionActive) {
      return;
    }
    try {
      state.recognition.stop();
    } catch (_error) {
      // ignore stop races from browser speech recognition
    }
  }

  async function handleWakeTranscript(transcript) {
    updateLiveTranscript(transcript);
    const wakeMatch = detectWakePhrase(transcript);
    logVoiceEvent("wake_transcript", {
      transcript,
      detected: wakeMatch.detected,
      remainingText: wakeMatch.remainingText,
    });

    if (!wakeMatch.detected) {
      addActivity("Standby", "Heard audio, but the wake phrase was not detected.", "neutral");
      setBrowserVoiceDiagnostics({
        lastTranscript: transcript,
        heardSpeech: true,
        lastEvent: "wake_not_matched",
        lastIssue: `Standby is active. Say "${preferredWakePhrase()}" to wake AURA.`,
      });
      updateWakeBanner(`Standby is active. Say “${preferredWakePhrase()}” to wake AURA.`);
      setIdleState();
      resumeWakeStandby({ delayMs: NO_SPEECH_RECOVERY_DELAY_MS, reason: "wake_not_matched" });
      return;
    }

    setAssistantState("understanding", {
      pill: "Awake",
      kicker: "Wake detected",
      headline: "I’m here.",
      description: "Preparing the command flow now.",
    });

    setBrowserVoiceDiagnostics({
      lastTranscript: transcript,
      heardSpeech: true,
      lastEvent: "wake_detected",
      lastIssue: `Wake phrase matched. ${wakeMatch.remainingText ? "Continuing with the command." : "Waiting for the command."}`,
    });
    setAssistantState("understanding", {
      pill: "Awake",
      kicker: "Wake detected",
      headline: "I'm here.",
      description: "Preparing the command flow now.",
    });

    if (!wakeMatch.remainingText) {
      const wakePayload = await submitVoiceTranscript(transcript);
      const acknowledgement = wakePayload.assistant_reply || "Yes?";
      updateLiveResponse(acknowledgement, { provider: "local_wake", mode: "wake" });
      addActivity("Wake detected", `AURA heard ${preferredWakePhrase()}.`, "good");
      await speakAssistant(acknowledgement, { resumeWakeAfter: false });
      if (!state.busy) {
        startRecognitionSession("command", { automatic: false, resetCommandRetryCount: true });
      }
      return;
    }

    await processVoiceCommand(transcript);
  }

  async function handleCommandTranscript(transcript) {
    updateLiveTranscript(transcript);
    await processVoiceCommand(transcript);
  }

  async function processVoiceCommand(transcript) {
    setAssistantState("thinking", {
      pill: "Thinking",
      kicker: "Working",
      headline: "One second.",
      description: "I’m working through that now.",
    });

    setAssistantState("thinking", {
      pill: "Thinking",
      kicker: "Working",
      headline: "One second.",
      description: "I'm working through that now.",
    });

    try {
      const payload = await submitVoiceTranscript(transcript);
      await consumeVoicePayload(payload, transcript);
    } catch (error) {
      if (error?.name === "AbortError") {
        setIdleState();
        return;
      }
      handleAssistantFailure(error.message || FALLBACK_REPLY);
    }
  }

  async function consumeVoicePayload(payload, transcript) {
    if (payload.status === "wake_only") {
      const acknowledgement = payload.assistant_reply || "Yes?";
      updateLiveResponse(acknowledgement, { provider: "local_wake", mode: "wake" });
      await speakAssistant(acknowledgement, { resumeWakeAfter: false });
      startRecognitionSession("command", { automatic: false, resetCommandRetryCount: true });
      return;
    }

    if (!payload.success || !payload.result) {
      handleAssistantFailure(payload.message || payload.error || FALLBACK_REPLY);
      return;
    }

    const result = payload.result || {};
    const commandText = payload.command_text || transcript;
    const answer = normalizeAssistantText(result.response || result.content || result.reply || FALLBACK_REPLY);
    const provider = result.provider || "local";

    state.currentProvider = provider;
    updateLiveTranscript(commandText);
    updateLiveResponse(answer, { provider, mode: "voice" });
    addActivity("Voice request", commandText, "neutral");
    addActivity("Answer ready", answer.slice(0, 140), result.degraded ? "warn" : "good");
    setAssistantState("speaking", {
      pill: "Speaking",
      kicker: "Responding",
      headline: "Done.",
      description: "I have the answer for you.",
    });
    await speakAssistant(answer, { resumeWakeAfter: true });
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
      stopRecognition();
    }
    setAssistantState("thinking", {
      pill: "Thinking",
      kicker: "Text command",
      headline: "One second.",
      description: "I’m working through that now.",
    });

    setAssistantState("thinking", {
      pill: "Thinking",
      kicker: "Text command",
      headline: "One second.",
      description: "I'm working through that now.",
    });

    try {
      const payload = await submitChatMessage(text);
      const answer = normalizeAssistantText(payload.content || payload.reply || FALLBACK_REPLY);
      const provider = payload.provider || "local";
      state.currentProvider = provider;
      updateLiveResponse(answer, { provider, mode: payload.mode || "text" });
      addActivity("Text command", text, "neutral");
      addActivity("Answer ready", answer.slice(0, 140), payload.success === false ? "warn" : "good");

      if (payload.success === false || payload.degraded) {
        setAssistantState("error", {
          pill: "Degraded",
          kicker: "Fallback answer",
          headline: "I still have an answer for you.",
          description: payload.error || assistantRuntimeMessage(),
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
    });
  }

  async function submitVoiceTranscript(text) {
    return requestJson("/api/voice/text", {
      text,
      mode: "hybrid",
    });
  }

  async function requestJson(url, payload) {
    if (state.currentRequestController) {
      state.currentRequestController.abort();
    }

    const controller = new AbortController();
    state.currentRequestController = controller;
    state.busy = true;
    renderWakeControls();

    try {
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

      return body;
    } finally {
      if (state.currentRequestController === controller) {
        state.currentRequestController = null;
      }
      state.busy = false;
      renderWakeControls();
    }
  }

  function interruptAssistant() {
    if (state.currentRequestController) {
      state.currentRequestController.abort();
      state.currentRequestController = null;
    }
    clearRecognitionStartTimer();
    stopRecognition();
    stopSpeech();
    addActivity("Interrupted", "The current assistant action was stopped.", "warn");
    if (state.wakeModeEnabled) {
      setIdleState();
      resumeWakeStandby({ reason: "interrupt" });
      return;
    }
    setIdleState();
  }

  function stopSpeech() {
    if (!window.speechSynthesis) {
      return;
    }
    window.speechSynthesis.cancel();
    state.speaking = false;
  }

  async function speakAssistant(text, { resumeWakeAfter = true } = {}) {
    const spokenText = prepareSpokenText(text);
    if (!spokenText) {
      if (resumeWakeAfter) {
        setIdleState();
      }
      return;
    }

    if (!window.speechSynthesis) {
      if (resumeWakeAfter) {
        setIdleState();
      }
      return;
    }

    stopSpeech();

    await new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(spokenText);
      utterance.lang = preferredSpeechLanguage();
      utterance.rate = 1;
      utterance.pitch = 1;
      utterance.volume = 1;

      utterance.onstart = () => {
        state.speaking = true;
        setAssistantState("speaking", {
          pill: "Speaking",
          kicker: "Responding",
          headline: "Done.",
          description: "I have the answer for you.",
        });
        renderWakeControls();
      };

      utterance.onend = () => {
        state.speaking = false;
        renderWakeControls();
        resolve();
      };

      utterance.onerror = () => {
        state.speaking = false;
        renderWakeControls();
        resolve();
      };

      window.speechSynthesis.speak(utterance);
    });

    if (resumeWakeAfter) {
      setIdleState();
      resumeWakeStandby({ reason: "speech_complete" });
    }
  }

  function handleAssistantFailure(message) {
    const safeMessage = normalizeAssistantText(message || FALLBACK_REPLY) || FALLBACK_REPLY;
    updateLiveResponse(safeMessage, { provider: "degraded", mode: "fallback" });
    addActivity("Assistant issue", safeMessage, "error");
    setAssistantState("error", {
      pill: "Error",
      kicker: "Assistant issue",
      headline: "I couldn’t complete that cleanly.",
      description: safeMessage,
    });
    updateWakeBanner(safeMessage);
    resumeWakeStandby({ reason: "assistant_failure" });
  }

  function setIdleState() {
    const wakePhrase = preferredWakePhrase();
    const wakeEnabled = state.wakeModeEnabled;
    setAssistantState("idle", {
      pill: wakeEnabled ? "Standby" : "Idle",
      kicker: wakeEnabled ? "Standby" : "Idle",
      headline: wakeEnabled ? "Wake mode is on." : "Ready when you are.",
      description: wakeEnabled
        ? `Say “${wakePhrase}” while this page stays open.`
        : `Use Wake mode, Talk, or the text command field when you want me.`,
    });
    updateWakeBanner(currentWakeBanner());
  }

  function resumeWakeStandby({ delayMs = WAKE_RESUME_DELAY_MS, reason = "resume_wake" } = {}) {
    if (!state.wakeModeEnabled || state.recognitionActive || state.busy || state.speaking) {
      return;
    }
    scheduleRecognitionStart("wake", {
      delayMs,
      automatic: true,
      resetCommandRetryCount: false,
      reason,
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
    if (state.wakeModeEnabled) {
      return `Wake mode is on. Say “${preferredWakePhrase()}” while this page stays open.`;
    }
    if (state.auth?.authenticated) {
      return `Wake mode is available. Tap Wake mode once if the browser still needs microphone permission, then say “${preferredWakePhrase()}”.`;
    }
    return publicWakeBanner();
  }

  function publicWakeBanner() {
    return `Public mode keeps text and one-tap Talk available now. Sign in if you want always-ready wake mode around “${preferredWakePhrase()}”.`;
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

  function detectWakePhrase(transcript) {
    const wakeWords = state.voiceStatus?.settings?.wake_words || [WAKE_FALLBACK];
    const lowered = String(transcript || "").trim().toLowerCase();
    const normalized = lowered.replace(/^[\s,.;:!?-]+/, "");

    for (const wakeWord of wakeWords) {
      const candidate = String(wakeWord || "").trim().toLowerCase();
      if (!candidate) {
        continue;
      }
      const pattern = new RegExp(`^(?:${escapeRegex(candidate)})(?:[\\s,.;:!?-]+|$)`);
      if (pattern.test(normalized)) {
        return {
          detected: true,
          wakeWord: candidate,
          remainingText: normalized.replace(pattern, "").trim(),
        };
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
    window.setInterval(() => {
      void refreshStatus({ quiet: true });
    }, 60000);
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
      "not-allowed": "Microphone permission was denied.",
      "service-not-allowed": "This browser is blocking microphone access.",
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
    const trimmedSentences = sentences
      .map((sentence) => sentence.trim())
      .filter(Boolean);
    const preview = trimmedSentences.slice(0, 3).join(" ").trim();

    if (cleaned.length > 360 && trimmedSentences.length > 3) {
      return `${preview} I have the rest on screen.`;
    }

    return cleaned;
  }

  function setIdleState() {
    const wakePhrase = preferredWakePhrase();
    const wakeEnabled = state.wakeModeEnabled;
    setAssistantState("idle", {
      pill: wakeEnabled ? "Standby" : "Idle",
      kicker: wakeEnabled ? "Standby" : "Idle",
      headline: wakeEnabled ? "Wake mode is on." : "Ready when you are.",
      description: wakeEnabled
        ? `Say "${wakePhrase}" while this page stays open.`
        : "Use Wake mode, Talk, or the text command field when you want me.",
    });
    updateWakeBanner(currentWakeBanner());
  }

  function currentWakeBanner() {
    if (!state.recognition) {
      return "Browser wake mode is not available here. Text commands still work.";
    }
    if (!isVoiceAllowedHere()) {
      return "Wake mode needs localhost or HTTPS in this browser.";
    }
    if (state.wakeModeEnabled) {
      return `Wake mode is on. Say "${preferredWakePhrase()}" while this page stays open.`;
    }
    if (state.auth?.authenticated) {
      return `Wake mode is available. Tap Wake mode once if the browser still needs microphone permission, then say "${preferredWakePhrase()}".`;
    }
    return publicWakeBanner();
  }

  function publicWakeBanner() {
    return `Public mode keeps text and one-tap Talk available now. Sign in if you want always-ready wake mode around "${preferredWakePhrase()}".`;
  }

  function normalizeWakeText(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^\w\s]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function buildWakeVariants(phrase) {
    const normalized = normalizeWakeText(phrase);
    if (!normalized) {
      return [];
    }

    const variants = new Set([normalized]);
    const [first, second] = normalized.split(" ");
    if (first && second) {
      const firstOptions = first === "hey" ? ["hey", "hi", "heya"] : [first];
      const secondOptions = second === "aura" ? ["aura", "ora"] : [second];
      firstOptions.forEach((firstVariant) => {
        secondOptions.forEach((secondVariant) => {
          variants.add(`${firstVariant} ${secondVariant}`.trim());
        });
      });
    }

    return Array.from(variants);
  }

  function buildWakePattern(phrase) {
    const tokens = normalizeWakeText(phrase)
      .split(" ")
      .filter(Boolean)
      .map((token) => escapeRegex(token));
    if (!tokens.length) {
      return null;
    }
    return new RegExp(`^\\s*(?:[\\s,.;:!?-])*${tokens.join("[\\s,.;:!?-]+")}(?:[\\s,.;:!?-]+|$)`, "i");
  }

  function detectWakePhrase(transcript) {
    const original = String(transcript || "").trim();
    const wakeWords = state.voiceStatus?.settings?.wake_words || [WAKE_FALLBACK];

    for (const wakeWord of wakeWords) {
      for (const variant of buildWakeVariants(wakeWord)) {
        const pattern = buildWakePattern(variant);
        if (!pattern) {
          continue;
        }
        if (pattern.test(original)) {
          return {
            detected: true,
            wakeWord: normalizeWakeText(wakeWord),
            variant,
            remainingText: original.replace(pattern, "").trim(),
          };
        }
      }
    }

    return {
      detected: false,
      wakeWord: null,
      variant: null,
      remainingText: original,
    };
  }

  function scheduleRefresh() {
    window.setInterval(() => {
      if (state.refreshInFlight || state.busy || state.recognitionActive || state.speaking) {
        return;
      }
      void refreshStatus({ quiet: true });
    }, REFRESH_INTERVAL_MS);
  }

  function handleAssistantFailure(message) {
    const safeMessage = normalizeAssistantText(message || FALLBACK_REPLY) || FALLBACK_REPLY;
    updateLiveResponse(safeMessage, { provider: "degraded", mode: "fallback" });
    addActivity("Assistant issue", safeMessage, "error");
    setAssistantState("error", {
      pill: "Error",
      kicker: "Assistant issue",
      headline: "I couldn't complete that cleanly.",
      description: safeMessage,
    });
    updateWakeBanner(safeMessage);
    resumeWakeStandby({ reason: "assistant_failure" });
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
