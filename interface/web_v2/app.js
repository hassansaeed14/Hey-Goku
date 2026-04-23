(function () {
  const STORAGE_KEYS = {
    sessionId: "aura-v2-session-id",
    sessionTitles: "aura-v2-session-titles",
  };

  const WAKE_FALLBACK = "hey aura";
  const STATE_COPY = {
    idle: {
      label: "Idle",
      sidebar: "Calm and ready",
      orb: "Calm presence",
    },
    listening: {
      label: "Listening",
      sidebar: "Listening closely",
      orb: "Wake focus",
    },
    analyzing: {
      label: "Analyzing",
      sidebar: "Sorting the route",
      orb: "Focused routing",
    },
    thinking: {
      label: "Thinking",
      sidebar: "Working with you",
      orb: "Workspace active",
    },
    responding: {
      label: "Responding",
      sidebar: "Delivering the result",
      orb: "Warm response",
    },
    error: {
      label: "Error",
      sidebar: "Needs a clean retry",
      orb: "Attention required",
    },
  };

  const EXTERNAL_TARGETS = [
    { pattern: /\b(?:open|launch|go to|visit)\s+youtube\b/i, label: "YouTube", type: "web", url: "https://www.youtube.com/" },
    { pattern: /\b(?:open|launch|go to|visit)\s+google\b/i, label: "Google", type: "web", url: "https://www.google.com/" },
    { pattern: /\b(?:open|launch|go to|visit)\s+github\b/i, label: "GitHub", type: "web", url: "https://github.com/" },
    { pattern: /\b(?:open|launch|go to|visit)\s+gmail\b/i, label: "Gmail", type: "web", url: "https://mail.google.com/" },
    { pattern: /\b(?:open|launch|go to|visit)\s+facebook\b/i, label: "Facebook", type: "web", url: "https://www.facebook.com/" },
    { pattern: /\b(?:open|launch|go to|visit)\s+whatsapp\b/i, label: "WhatsApp", type: "web", url: "https://web.whatsapp.com/" },
    { pattern: /\b(?:open|launch|go to|visit)\s+spotify\b/i, label: "Spotify", type: "web", url: "https://open.spotify.com/" },
    { pattern: /\b(?:open|launch)\s+(?:the\s+)?browser\b/i, label: "Browser", type: "web", url: "https://www.google.com/" },
    { pattern: /\b(?:open|launch)\s+(?:vs\s*code|visual studio code|vscode)\b/i, label: "VS Code", type: "desktop" },
    { pattern: /\b(?:open|launch)\s+(?:notepad|calculator|settings)\b/i, label: "Desktop app", type: "desktop" },
  ];

  const INTERNAL_HINTS = [
    { pattern: /\b(notes?|assignment|assignments?|essay|report|slides?|presentation|pdf|docx|txt|pptx)\b/i, label: "Document task", kind: "document" },
    { pattern: /\b(code|coding|program|python|javascript|typescript|debug|function|api|build)\b/i, label: "Coding task", kind: "coding" },
    { pattern: /\b(research|compare|comparison|explain|how|why|latest|status|summary|summarize)\b/i, label: "Research task", kind: "research" },
    { pattern: /\b(write|draft|rewrite|improve|email|letter|blog|article)\b/i, label: "Writing task", kind: "writing" },
  ];

  const RecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition || null;

  const el = {};
  const state = {
    sessionId: "",
    sessionTitles: readSessionTitles(),
    auth: null,
    voiceStatus: null,
    assistantState: "idle",
    assistantStateEvent: "boot:uninitialized",
    orbLayout: "topbar",
    taskScope: "none",
    sessions: [],
    messages: [],
    recentOutputs: [],
    sidebarSearch: "",
    panelVisible: false,
    panelMode: "",
    currentTask: null,
    currentExternal: null,
    requestInFlight: false,
    screenShareActive: false,
    screenShareLabel: "Off",
    screenStream: null,
    voiceSupported: false,
    recognition: null,
    recognitionMode: "",
    recognitionActive: false,
    recognitionStopReason: "",
    speechCommandInFlight: false,
    wakeModeEnabled: false,
    presenceHideTimer: 0,
  };

  function logVoiceDebug(message, details) {
    if (typeof details === "undefined") {
      console.info(`[AURA voice] ${message}`);
      return;
    }
    console.info(`[AURA voice] ${message}`, details);
  }

  function logVoiceError(message, details) {
    if (typeof details === "undefined") {
      console.error(`[AURA voice] ${message}`);
      return;
    }
    console.error(`[AURA voice] ${message}`, details);
  }

  function logOrbState(stateName, eventName) {
    console.info(`[ORB STATE] ${stateName} triggered by ${eventName}`);
  }

  document.addEventListener("DOMContentLoaded", () => {
    cacheElements();
    bindEvents();
    state.sessionId = ensureSessionId();
    setTaskScope("none");
    setAssistantState("idle", "boot:dom_ready");
    setOrbLayout("topbar");
    hidePresence(true);
    autoResizeTextarea();
    void initialize();
  });

  async function initialize() {
    await Promise.allSettled([
      refreshAuthSession(),
      loadVoiceStatus(),
      loadSessions(),
    ]);
    syncVoiceControls();
    logVoiceDebug("Voice support check", {
      speechRecognition: Boolean(window.SpeechRecognition),
      webkitSpeechRecognition: Boolean(window.webkitSpeechRecognition),
      recognitionCtor: Boolean(RecognitionCtor),
      secureContext: window.isSecureContext,
      talkButtonPresent: Boolean(el.talkButton),
      wakeButtonPresent: Boolean(el.wakeButton),
      voiceSupported: state.voiceSupported,
    });
    await loadConversation(state.sessionId);
    renderSidebarSessions();
    renderConversation();
    renderRightPanel();
    updateWorkspaceChrome();
  }

  function cacheElements() {
    Object.assign(el, {
      body: document.body,
      assistantOrb: document.getElementById("assistantOrb"),
      orbStateLabel: document.getElementById("orbStateLabel"),
      orbModeLabel: document.getElementById("orbModeLabel"),
      presenceStage: document.getElementById("presenceStage"),
      presenceEyebrow: document.getElementById("presenceEyebrow"),
      presenceTitle: document.getElementById("presenceTitle"),
      presenceText: document.getElementById("presenceText"),
      sidebarState: document.getElementById("sidebarState"),
      newChatButton: document.getElementById("newChatButton"),
      chatSearch: document.getElementById("chatSearch"),
      chatList: document.getElementById("chatList"),
      chatListEmpty: document.getElementById("chatListEmpty"),
      historyMeta: document.getElementById("historyMeta"),
      profileButton: document.getElementById("profileButton"),
      profileEntryName: document.getElementById("profileEntryName"),
      profileEntryStatus: document.getElementById("profileEntryStatus"),
      accessChip: document.getElementById("accessChip"),
      stateChipLabel: document.getElementById("stateChipLabel"),
      workspaceSummary: document.getElementById("workspaceSummary"),
      screenChipLabel: document.getElementById("screenChipLabel"),
      conversationThread: document.getElementById("conversationThread"),
      chatScroll: document.getElementById("chatScroll"),
      composerForm: document.getElementById("composerForm"),
      messageInput: document.getElementById("messageInput"),
      composerStatus: document.getElementById("composerStatus"),
      voiceTranscript: document.getElementById("voiceTranscript"),
      screenShareButton: document.getElementById("screenShareButton"),
      talkButton: document.getElementById("talkButton"),
      wakeButton: document.getElementById("wakeButton"),
      interruptButton: document.getElementById("interruptButton"),
      sendButton: document.getElementById("sendButton"),
      rightPanel: document.getElementById("rightPanel"),
      rightPanelTitle: document.getElementById("rightPanelTitle"),
      rightPanelBody: document.getElementById("rightPanelBody"),
      panelCloseButton: document.getElementById("panelCloseButton"),
    });
  }

  function bindEvents() {
    el.newChatButton?.addEventListener("click", startNewChat);
    el.chatSearch?.addEventListener("input", () => {
      state.sidebarSearch = String(el.chatSearch.value || "").trim().toLowerCase();
      renderSidebarSessions();
    });
    el.profileButton?.addEventListener("click", () => {
      state.panelVisible = true;
      state.panelMode = "profile";
      renderRightPanel();
    });
    el.panelCloseButton?.addEventListener("click", () => {
      state.panelVisible = false;
      state.panelMode = "";
      renderRightPanel();
    });
    el.composerForm?.addEventListener("submit", handleComposerSubmit);
    el.messageInput?.addEventListener("input", autoResizeTextarea);
    el.messageInput?.addEventListener("keydown", handleComposerKeydown);
    el.assistantOrb?.addEventListener("click", handleOrbActivation);
    el.assistantOrb?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        handleOrbActivation();
      }
    });
    if (el.talkButton) {
      logVoiceDebug("Talk button bound", {
        id: el.talkButton.id,
        hidden: el.talkButton.hidden,
      });
    } else {
      logVoiceError("Talk button missing");
    }
    el.talkButton?.addEventListener("click", () => {
      logVoiceDebug("Talk button click", {
        voiceSupported: state.voiceSupported,
        recognitionCtor: Boolean(RecognitionCtor),
        recognitionActive: state.recognitionActive,
        recognitionMode: state.recognitionMode,
      });
      if (state.recognitionActive && state.recognitionMode === "talk") {
        logVoiceDebug("Talk button requested stop for active recognition");
        stopRecognition("Listening stopped.");
        return;
      }
      void startSpeechCapture("talk");
    });

    if (el.interruptButton) {
      logVoiceDebug("Interrupt button bound", { id: el.interruptButton.id });
    } else {
      logVoiceError("Interrupt button missing from DOM");
    }
    el.interruptButton?.addEventListener("click", () => {
      console.log("BUTTON CLICKED: Interrupt");
      handleInterrupt();
    });
  }

  function handleInterrupt() {
    if (state.recognitionActive) {
      stopRecognition("Listening stopped.");
    }
    if (el.interruptButton) {
      el.interruptButton.hidden = true;
    }
    if (!state.requestInFlight) {
      setAssistantState("idle", "user:interrupt_completed");
      setComposerStatus("Stopped. Ready when you are.");
      settleToIdleLayout();
    } else {
      setComposerStatus("Interrupt noted. Waiting for the current request to finish.");
    }
  }

  function clearPresenceTimer() {
    if (state.presenceHideTimer) {
      window.clearTimeout(state.presenceHideTimer);
      state.presenceHideTimer = 0;
    }
  }

  function setTaskScope(scope) {
    const nextScope = scope || "none";
    state.taskScope = nextScope;
    if (el.body) {
      el.body.dataset.taskScope = nextScope;
    }
  }

  function resetToCalmIdle(delayMs = 1100) {
    window.setTimeout(() => {
      if (!state.requestInFlight && !state.recognitionActive && !state.speechCommandInFlight) {
        setAssistantState("idle", "lifecycle:calm_idle_timeout");
        settleToIdleLayout();
      }
    }, delayMs);
  }

  function clearVoiceTranscript() {
    if (!el.voiceTranscript) {
      return;
    }
    el.voiceTranscript.hidden = true;
    el.voiceTranscript.dataset.final = "false";
    el.voiceTranscript.textContent = "";
  }

  function updateVoiceTranscript(text, options = {}) {
    if (!el.voiceTranscript) {
      return;
    }
    const cleanText = String(text || "").trim();
    if (!cleanText) {
      clearVoiceTranscript();
      return;
    }
    el.voiceTranscript.hidden = false;
    el.voiceTranscript.dataset.final = options.final ? "true" : "false";
    el.voiceTranscript.textContent = `${options.final ? "Heard" : "Listening"}: ${cleanText}`;
  }

  function hidePresence(immediate) {
    if (!el.presenceStage) {
      return;
    }

    clearPresenceTimer();
    const resetClasses = () => {
      el.presenceStage.classList.remove(
        "is-visible",
        "presence-stage--center",
        "presence-stage--docked",
        "presence-stage--floating",
      );
    };

    if (immediate) {
      resetClasses();
      el.presenceStage.hidden = true;
      return;
    }

    el.presenceStage.classList.remove("is-visible");
    window.setTimeout(() => {
      if (!el.presenceStage.classList.contains("is-visible")) {
        resetClasses();
        el.presenceStage.hidden = true;
      }
    }, 280);
  }

  function showPresence(options = {}) {
    if (!el.presenceStage || !el.presenceEyebrow || !el.presenceTitle || !el.presenceText) {
      return;
    }

    clearPresenceTimer();
    const mode = options.mode || "center";
    el.presenceEyebrow.textContent = options.eyebrow || "AURA presence";
    el.presenceTitle.textContent = options.title || "AURA is here.";
    el.presenceText.textContent = options.text || "Calm, present, and ready when you are.";
    el.presenceStage.hidden = false;
    el.presenceStage.classList.remove(
      "is-visible",
      "presence-stage--center",
      "presence-stage--docked",
      "presence-stage--floating",
    );
    el.presenceStage.classList.add(`presence-stage--${mode}`);
    window.requestAnimationFrame(() => {
      el.presenceStage.classList.add("is-visible");
    });

    if (options.duration) {
      state.presenceHideTimer = window.setTimeout(() => {
        hidePresence();
      }, options.duration);
    }
  }

  async function refreshAuthSession() {
    try {
      state.auth = await apiJson("/api/auth/session", { method: "GET" });
    } catch (_error) {
      state.auth = {
        authenticated: false,
        access_mode: "public",
        status: "error",
      };
    }
  }

  async function loadVoiceStatus() {
    try {
      state.voiceStatus = await apiJson("/api/voice/status", { method: "GET" });
    } catch (_error) {
      state.voiceStatus = null;
    }
  }

  async function getMicrophonePermissionState() {
    if (!navigator.permissions || !navigator.permissions.query) {
      return "prompt";
    }
    try {
      const result = await navigator.permissions.query({ name: "microphone" });
      return String(result?.state || "prompt");
    } catch (_error) {
      return "prompt";
    }
  }

  function syncVoiceControls() {
    state.voiceSupported = Boolean(
      RecognitionCtor
      && (window.isSecureContext || window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"),
    );

    if (!el.talkButton) {
      return;
    }

    if (state.voiceSupported) {
      el.talkButton.hidden = false;
      el.talkButton.classList.toggle("is-active", state.recognitionActive && state.recognitionMode === "talk");
      if (el.wakeButton) {
        el.wakeButton.hidden = true;
        el.wakeButton.classList.remove("is-active");
      }
      if (el.interruptButton) {
        el.interruptButton.hidden = !state.recognitionActive;
        el.interruptButton.classList.toggle("is-active", state.recognitionActive);
      }
      return;
    }

    el.talkButton.hidden = true;
    if (el.wakeButton) {
      el.wakeButton.hidden = true;
      el.wakeButton.classList.remove("is-active");
    }
    el.talkButton.classList.remove("is-active");
    if (el.interruptButton) {
      el.interruptButton.hidden = true;
    }
  }

  async function loadSessions() {
    try {
      const payload = await apiJson("/api/sessions", { method: "GET" });
      state.sessions = Array.isArray(payload.sessions) ? payload.sessions : [];
    } catch (_error) {
      state.sessions = [];
    }
  }

  async function loadConversation(sessionId) {
    try {
      const payload = await apiJson(`/api/history?session_id=${encodeURIComponent(sessionId)}&limit=80`, { method: "GET" });
      state.messages = (Array.isArray(payload.messages) ? payload.messages : []).map(normalizeHistoryMessage);
      const title = deriveSessionTitle(state.messages);
      if (title) {
        state.sessionTitles[sessionId] = title;
        persistSessionTitles();
      }
    } catch (_error) {
      state.messages = [];
    }
  }

  async function handleComposerSubmit(event) {
    console.log("BUTTON CLICKED: Send", { requestInFlight: state.requestInFlight });
    event.preventDefault();
    if (state.requestInFlight) {
      return;
    }

    const rawText = String(el.messageInput?.value || "").trim();
    if (!rawText) {
      return;
    }

    el.messageInput.value = "";
    autoResizeTextarea();

    const userMessage = appendMessage({
      role: "user",
      text: rawText,
      badge: "You",
      timestamp: new Date().toISOString(),
    });
    void userMessage;
    rememberSessionTitle(rawText);

    const wakeMatch = detectWakePhrase(rawText);
    let commandText = rawText;
    if (wakeMatch.detected) {
      await runWakeSequence();
      if (!wakeMatch.remainingText) {
        await delay(1600);
        settleToIdleLayout();
        return;
      }
      commandText = wakeMatch.remainingText;
    }

    setAssistantState("analyzing", "chat:input_received");
    setComposerStatus("I hear you. Let me route that.");
    updateWorkspaceSummary("AURA is choosing the cleanest path for this request.");
    await delay(120);

    const classification = classifyCommand(commandText);
    if (classification.kind === "external") {
      handleExternalCommand(commandText, classification);
      return;
    }

    await handleInternalCommand(commandText, classification);
  }

  async function runWakeSequence() {
    setOrbLayout("center");
    setAssistantState("listening", "wake:sequence_started");
    showPresence({
      mode: "center",
      eyebrow: "Wake phrase detected",
      title: buildWakeGreeting(),
      text: "I'm with you now. Tell me what you want handled next.",
    });
    setComposerStatus(buildWakeGreeting());
    updateWorkspaceSummary("AURA is awake, present, and listening for the next step.");
    await delay(220);
    setAssistantState("responding", "wake:greeting_ready");
    appendMessage({
      role: "assistant",
      text: buildWakeGreeting(),
      badge: "Wake",
      timestamp: new Date().toISOString(),
    });
    showPresence({
      mode: "center",
      eyebrow: "AURA awake",
      title: buildWakeGreeting(),
      text: "Tell me what you want handled next.",
      duration: 1800,
    });
    renderRightPanel();
  }

  async function handleInternalCommand(commandText, classification) {
    state.requestInFlight = true;
    state.currentExternal = null;
    setTaskScope("internal");
    state.currentTask = {
      scope: "internal",
      label: classification.label,
      kind: classification.taskKind,
      text: commandText,
    };
    state.panelVisible = true;
    state.panelMode = "context";
    setOrbLayout("left");
    setAssistantState("thinking", "api:request_started");
    setComposerStatus("Working on that now.");
    updateWorkspaceSummary("I can handle that inside AURA, so the workspace is staying focused.");
    showPresence({
      mode: "docked",
      eyebrow: "Workspace mode",
      title: "Working on that now.",
      text: "I can handle that inside AURA and keep the work close at hand.",
      duration: 1700,
    });
    renderRightPanel();
    renderConversation();

    try {
      const payload = await apiJson("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: commandText, mode: "hybrid" }),
      });

      const delivery = normalizeDocumentDeliveryPayload(payload);
      const replyText = String(payload.reply || payload.content || "").trim() || "Done.";
      appendMessage({
        role: "assistant",
        text: replyText,
        badge: humanizeBadge(payload.execution_mode || classification.taskKind || "Assistant"),
        timestamp: new Date().toISOString(),
        delivery,
      });

      if (delivery) {
        state.recentOutputs = [delivery, ...state.recentOutputs.filter((item) => item.downloadUrl !== delivery.downloadUrl)].slice(0, 6);
        state.panelVisible = true;
        state.panelMode = "outputs";
      }

      setAssistantState("responding", "api:response_received");
      setComposerStatus(delivery
        ? "Done. I've prepared it."
        : payload.degraded
          ? "I couldn't complete that cleanly, but I still got you the best available result."
          : "Done. I've handled that inside AURA.");
      updateWorkspaceSummary(delivery
        ? `${capitalize(delivery.documentType)} ready with a preview and direct downloads.`
        : payload.degraded
          ? "AURA stayed inside the workspace and finished with a fallback path."
          : "AURA handled the work inside the workspace.");
      showPresence({
        mode: "docked",
        eyebrow: delivery ? "Work completed" : payload.degraded ? "Fallback result" : "Work completed",
        title: delivery
          ? "Done. I've prepared it."
          : payload.degraded
            ? "I couldn't complete that cleanly."
            : "Done. I've handled that inside AURA.",
        text: delivery
          ? `Your ${delivery.documentType} is ready below with direct downloads and a preview.`
          : payload.degraded
            ? "I used the best available path and kept the work inside AURA."
            : "The result is ready here in the workspace.",
        duration: 2200,
      });
      await loadSessions();
      renderSidebarSessions();
      renderRightPanel();
    } catch (error) {
      setAssistantState("error", "api:request_failed");
      setComposerStatus("I couldn't complete that yet.");
      updateWorkspaceSummary("That task did not finish cleanly inside AURA.");
      showPresence({
        mode: "docked",
        eyebrow: "Need a retry",
        title: "I couldn't complete that yet.",
        text: "Please try again in a moment.",
        duration: 2200,
      });
      appendMessage({
        role: "assistant",
        text: error.message || "Something went wrong while processing that request.",
        badge: "Error",
        timestamp: new Date().toISOString(),
      });
    } finally {
      state.requestInFlight = false;
      renderConversation();
      renderRightPanel();
      resetToCalmIdle();
    }
  }

  function handleExternalCommand(commandText, classification) {
    setTaskScope("external");
    state.currentTask = {
      scope: "external",
      label: classification.label,
      kind: classification.taskKind,
      text: commandText,
    };
    state.currentExternal = classification;
    state.panelVisible = true;
    state.panelMode = "context";
    setOrbLayout("floating");
    setAssistantState("analyzing", "external:routing_started");
    setComposerStatus("Let me route that outside AURA.");
    updateWorkspaceSummary("AURA is routing this outside the workspace while staying present.");

    let replyText = "";
    if (classification.type === "web" && classification.url) {
      const popup = window.open(classification.url, "_blank");
      if (popup) {
        try {
          popup.opener = null;
        } catch (_error) {
          // Ignore cross-window restrictions after launch.
        }
      }
      if (popup) {
        replyText = `Opening ${classification.label} for you. AURA will stay here as your assistant presence.`;
        setAssistantState("responding", "external:launch_succeeded");
        setComposerStatus("Opening that for you.");
        updateWorkspaceSummary(`${classification.label} is opening outside AURA while the assistant stays nearby.`);
        showPresence({
          mode: "floating",
          eyebrow: "External action",
          title: "Opening that for you.",
          text: `${classification.label} is moving outside AURA while I stay present here.`,
          duration: 2200,
        });
      } else {
        replyText = `I couldn't open ${classification.label} because the browser blocked the new tab. Allow popups for this site and try again.`;
        setAssistantState("error", "external:popup_blocked");
        setComposerStatus("The browser blocked that new tab.");
        updateWorkspaceSummary(`${classification.label} could not open because the browser blocked it.`);
        showPresence({
          mode: "floating",
          eyebrow: "Browser blocked",
          title: "I couldn't complete that yet.",
          text: `Allow popups for this site, then try ${classification.label} again.`,
          duration: 2400,
        });
      }
    } else {
      replyText = `I can't launch ${classification.label} from the browser yet. AURA can still open supported websites here.`;
      setAssistantState("error", "external:desktop_launch_unsupported");
      setComposerStatus("I can't launch that from the browser yet.");
      updateWorkspaceSummary("Desktop app launches still need a native bridge outside this browser.");
      showPresence({
        mode: "floating",
        eyebrow: "Browser limitation",
        title: "I couldn't complete that yet.",
        text: "Desktop app launches still need a native bridge.",
        duration: 2400,
      });
    }

    appendMessage({
      role: "assistant",
      text: replyText,
      badge: "External action",
      timestamp: new Date().toISOString(),
    });
    renderConversation();
    renderRightPanel();
    resetToCalmIdle();
  }

  function classifyCommand(text) {
    const normalized = String(text || "").trim();
    const directUrlMatch = normalized.match(/\bhttps?:\/\/[^\s]+/i);
    if (directUrlMatch) {
      return {
        kind: "external",
        type: "web",
        label: "Website",
        url: directUrlMatch[0],
        taskKind: "external",
      };
    }

    for (const target of EXTERNAL_TARGETS) {
      if (target.pattern.test(normalized)) {
        return {
          kind: "external",
          type: target.type,
          label: target.label,
          url: target.url || "",
          taskKind: "external",
        };
      }
    }

    for (const hint of INTERNAL_HINTS) {
      if (hint.pattern.test(normalized)) {
        return {
          kind: "internal",
          label: hint.label,
          taskKind: hint.kind,
        };
      }
    }

    return {
      kind: "internal",
      label: "Chat task",
      taskKind: "chat",
    };
  }

  function normalizeHistoryMessage(message) {
    return {
      role: String(message.role || "assistant").toLowerCase() === "user" ? "user" : "assistant",
      text: String(message.message || "").trim(),
      badge: String(message.intent || message.mode || "").trim(),
      timestamp: message.timestamp || new Date().toISOString(),
    };
  }

  function appendMessage(message) {
    state.messages.push(message);
    renderConversation();
    scrollConversationToBottom();
    return message;
  }

  function renderConversation() {
    if (!el.conversationThread) {
      return;
    }

    el.conversationThread.innerHTML = "";
    state.messages.forEach((message) => {
      el.conversationThread.appendChild(buildMessageRow(message));
    });
  }

  function buildMessageRow(message) {
    const row = document.createElement("article");
    row.className = `message-row message-row--${message.role === "user" ? "user" : "assistant"}`;

    const card = document.createElement("div");
    card.className = "message-card";

    const meta = document.createElement("div");
    meta.className = "message-card__meta";

    const label = document.createElement("span");
    label.className = "message-card__label";
    label.textContent = message.role === "user" ? "You" : "AURA";

    const metaRight = document.createElement("div");
    metaRight.style.display = "inline-flex";
    metaRight.style.gap = "8px";
    metaRight.style.alignItems = "center";

    if (message.badge) {
      const badge = document.createElement("span");
      badge.className = "message-card__badge";
      badge.textContent = humanizeBadge(message.badge);
      metaRight.appendChild(badge);
    }

    const time = document.createElement("span");
    time.textContent = formatClock(message.timestamp);
    metaRight.appendChild(time);

    meta.append(label, metaRight);
    card.appendChild(meta);

    if (message.text) {
      card.appendChild(renderRichText(message.text));
    }

    if (message.delivery) {
      card.appendChild(buildDocumentCard(message.delivery));
    }

    row.appendChild(card);
    return row;
  }

  function renderRichText(text) {
    const container = document.createElement("div");
    container.className = "rich-text";

    const segments = String(text || "").split(/```/);
    segments.forEach((segment, index) => {
      if (!segment.trim()) {
        return;
      }
      if (index % 2 === 1) {
        const pre = document.createElement("pre");
        pre.textContent = segment.trim();
        container.appendChild(pre);
        return;
      }

      const blocks = segment
        .replace(/\r\n/g, "\n")
        .split(/\n{2,}/)
        .map((block) => block.trim())
        .filter(Boolean);

      blocks.forEach((block) => {
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        if (!lines.length) {
          return;
        }
        if (lines.every((line) => /^[-*]\s+/.test(line))) {
          const list = document.createElement("ul");
          lines.forEach((line) => {
            const item = document.createElement("li");
            item.textContent = line.replace(/^[-*]\s+/, "");
            list.appendChild(item);
          });
          container.appendChild(list);
          return;
        }
        if (lines.every((line) => /^\d+\.\s+/.test(line))) {
          const list = document.createElement("ol");
          lines.forEach((line) => {
            const item = document.createElement("li");
            item.textContent = line.replace(/^\d+\.\s+/, "");
            list.appendChild(item);
          });
          container.appendChild(list);
          return;
        }
        const paragraph = document.createElement("p");
        paragraph.textContent = lines.join(" ");
        container.appendChild(paragraph);
      });
    });

    return container;
  }

  function normalizeDocumentDeliveryPayload(payload) {
    const raw = payload && typeof payload.document_delivery === "object" ? payload.document_delivery : {};
    const primaryFormat = String(raw.format || payload.format || "txt").trim().toLowerCase();
    const downloadUrl = String(raw.download_url || payload.download_url || "").trim();
    const fileName = String(raw.file_name || payload.file_name || "").trim();
    if (!downloadUrl || !fileName) {
      return null;
    }

    const formatLinks = {
      ...(payload.format_links && typeof payload.format_links === "object" ? payload.format_links : {}),
      ...(raw.format_links && typeof raw.format_links === "object" ? raw.format_links : {}),
    };
    if (!formatLinks[primaryFormat]) {
      formatLinks[primaryFormat] = downloadUrl;
    }

    const alternateFormatLinks = {
      ...(payload.alternate_format_links && typeof payload.alternate_format_links === "object" ? payload.alternate_format_links : {}),
      ...(raw.alternate_format_links && typeof raw.alternate_format_links === "object" ? raw.alternate_format_links : {}),
    };

    const files = [];
    const pushFile = (file) => {
      const format = String(file?.format || "").trim().toLowerCase();
      const name = String(file?.file_name || file?.fileName || "").trim();
      const href = String(file?.download_url || file?.downloadUrl || "").trim();
      if (!format || !name || !href) {
        return;
      }
      if (files.some((entry) => entry.format === format && entry.downloadUrl === href)) {
        return;
      }
      files.push({
        format,
        fileName: name,
        downloadUrl: href,
        primary: Boolean(file?.primary),
      });
    };

    (Array.isArray(payload.files) ? payload.files : []).forEach(pushFile);
    (Array.isArray(raw.files) ? raw.files : []).forEach(pushFile);
    Object.entries(formatLinks).forEach(([format, href]) => {
      pushFile({
        format,
        file_name: `${fileName.replace(/\.[^.]+$/, "")}.${format}`,
        download_url: href,
        primary: format === primaryFormat,
      });
    });
    Object.entries(alternateFormatLinks).forEach(([format, href]) => {
      pushFile({
        format,
        file_name: `${fileName.replace(/\.[^.]+$/, "")}.${format}`,
        download_url: href,
        primary: false,
      });
    });
    if (!files.length) {
      files.push({
        format: primaryFormat,
        fileName,
        downloadUrl,
        primary: true,
      });
    }

    const requestedFormats = Array.from(new Set([
      ...(Array.isArray(payload.requested_formats) ? payload.requested_formats : []),
      ...(Array.isArray(raw.requested_formats) ? raw.requested_formats : []),
      ...files.map((file) => file.format),
    ].map((item) => String(item).trim().toLowerCase()).filter(Boolean)));

    return {
      kind: "document_delivery",
      deliveryMessage: String(raw.delivery_message || payload.reply || payload.content || "Done. Your document is ready.").trim(),
      title: String(raw.title || payload.title || humanizeDocumentTitle(payload.document_type || raw.document_type || "document")).trim(),
      subtitle: String(raw.subtitle || payload.subtitle || "").trim(),
      previewText: String(raw.preview_text || payload.preview_text || "").trim(),
      documentType: String(raw.document_type || payload.document_type || "document").trim().toLowerCase(),
      format: primaryFormat,
      primaryFormat,
      fileName,
      downloadUrl,
      topic: String(raw.topic || payload.topic || "").trim(),
      pageTarget: Number(raw.page_target || payload.page_target || 0) || null,
      style: String(raw.style || payload.style || "").trim(),
      includeReferences: Boolean(raw.include_references || payload.include_references),
      citationStyle: String(raw.citation_style || payload.citation_style || "").trim(),
      files,
      requestedFormats,
    };
  }

  function buildDocumentCard(delivery) {
    const card = document.createElement("section");
    card.className = "document-card";

    const eyebrow = document.createElement("p");
    eyebrow.className = "document-card__eyebrow";
    eyebrow.textContent = humanizeDocumentTitle(delivery.documentType);

    const title = document.createElement("p");
    title.className = "document-card__title";
    title.textContent = delivery.title || humanizeDocumentTitle(delivery.documentType);

    const subtitle = document.createElement("p");
    subtitle.className = "document-card__subtitle";
    subtitle.textContent = delivery.deliveryMessage || `${humanizeDocumentTitle(delivery.documentType)} ready.`;

    const meta = document.createElement("p");
    meta.className = "document-card__meta";
    const metaParts = [
      delivery.subtitle || "",
      delivery.topic ? `Topic: ${delivery.topic}` : "",
      delivery.files.length > 1 ? `${delivery.files.length} files ready` : "Single file ready",
    ].filter(Boolean);
    meta.textContent = metaParts.join(" • ");

    const chips = document.createElement("div");
    chips.className = "document-card__chips";
    [
      `${String(delivery.primaryFormat || delivery.format).toUpperCase()} primary`,
      delivery.files.length > 1 ? `${delivery.files.length} formats` : "",
      delivery.pageTarget ? `~${delivery.pageTarget} pages` : "",
      delivery.style ? `${capitalize(delivery.style)} style` : "",
      delivery.includeReferences ? `References${delivery.citationStyle ? ` • ${String(delivery.citationStyle).toUpperCase()}` : ""}` : "",
    ].filter(Boolean).forEach((value) => {
      const chip = document.createElement("span");
      chip.className = "document-chip";
      chip.textContent = value;
      chips.appendChild(chip);
    });

    card.append(eyebrow, title, subtitle, meta);
    if (chips.childElementCount) {
      card.appendChild(chips);
    }

    if (delivery.previewText) {
      const preview = document.createElement("p");
      preview.className = "document-card__preview";
      preview.textContent = delivery.previewText;
      card.appendChild(preview);
    }

    const linksLabel = document.createElement("p");
    linksLabel.className = "links-label";
    linksLabel.textContent = delivery.files.length > 1 ? "Ready to download" : "Download";
    card.appendChild(linksLabel);

    const links = document.createElement("div");
    links.className = "document-links";

    const row = document.createElement("div");
    row.className = "document-links__row";
    delivery.files.forEach((file, index) => {
      row.appendChild(buildDocumentLink(`Download ${String(file.format || delivery.format).toUpperCase()}`, file.downloadUrl, index === 0));
    });
    links.appendChild(row);
    card.appendChild(links);
    return card;
  }

  function buildDocumentLink(label, href, primary) {
    const link = document.createElement("a");
    link.className = `document-link${primary ? " document-link--primary" : ""}`;
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = label;
    return link;
  }

  function renderRightPanel() {
    if (!el.rightPanel || !el.rightPanelBody || !el.rightPanelTitle) {
      return;
    }

    const hasOutputs = state.recentOutputs.length > 0;
    const hasTaskContext = Boolean(state.currentTask);
    const shouldShowPanel = state.panelMode === "profile"
      || (state.panelVisible && (hasOutputs || hasTaskContext));

    if (!shouldShowPanel) {
      el.rightPanel.hidden = true;
      el.rightPanelBody.innerHTML = "";
      return;
    }

    el.rightPanel.hidden = false;
    el.rightPanelBody.innerHTML = "";

    if (state.panelMode === "profile") {
      el.rightPanelTitle.textContent = "Profile";
      el.rightPanelBody.appendChild(buildProfileCard());
      return;
    }

    if (state.panelMode === "outputs" && state.recentOutputs.length) {
      el.rightPanelTitle.textContent = "Recent outputs";
    } else if (state.currentTask) {
      el.rightPanelTitle.textContent = state.currentTask.scope === "external" ? "External action" : "Current task";
      el.rightPanelBody.appendChild(buildTaskCard());
    } else {
      el.rightPanelTitle.textContent = "AURA context";
    }

    if (state.recentOutputs.length) {
      el.rightPanelBody.appendChild(buildOutputsCard());
    }

    if (!state.currentTask && !state.recentOutputs.length) {
      el.rightPanelBody.appendChild(buildProfileCard(true));
    }
  }

  function buildProfileCard(compact) {
    const card = document.createElement("section");
    card.className = "panel-card";

    const title = document.createElement("p");
    title.className = "panel-card__title";
    title.textContent = compact ? "Account truth" : "Account and session";

    const body = document.createElement("p");
    body.className = "panel-card__body";
    body.textContent = state.auth?.authenticated
      ? "You're signed in. These are the real account and session details AURA has right now."
      : "You're using public mode. Protected account work stays unavailable until you sign in.";

    const grid = document.createElement("div");
    grid.className = "panel-card__grid";

    const user = state.auth?.user || {};
    const fields = [
      ["Access mode", state.auth?.authenticated ? "Authenticated" : "Public"],
      ["Name", currentUserName() || "Guest"],
      ["Username", user.username || "Available after sign in"],
      ["Email", user.email || "Available after sign in"],
      ["Session", formatSessionSummary(state.auth)],
      ["Account status", state.auth?.authenticated ? "Signed in" : "Not signed in"],
    ];

    fields.forEach(([label, value]) => {
      const field = document.createElement("div");
      field.className = "panel-field";
      const labelNode = document.createElement("span");
      labelNode.textContent = label;
      const valueNode = document.createElement("strong");
      valueNode.textContent = value;
      field.append(labelNode, valueNode);
      grid.appendChild(field);
    });

    const actions = document.createElement("div");
    actions.className = "panel-actions";
    if (state.auth?.authenticated) {
      const logoutLink = document.createElement("a");
      logoutLink.className = "link-button";
      logoutLink.href = "/logout";
      logoutLink.textContent = "Log out";
      actions.appendChild(logoutLink);
    } else {
      actions.appendChild(buildNavLink("Sign in", "/login"));
      actions.appendChild(buildNavLink("Create account", "/register"));
      actions.appendChild(buildNavLink("Forgot password", "/forgot-password"));
    }

    card.append(title, body, grid, actions);
    return card;
  }

  function buildTaskCard() {
    const card = document.createElement("section");
    card.className = "panel-card";

    const title = document.createElement("p");
    title.className = "panel-card__title";
    title.textContent = state.currentTask.scope === "external"
      ? "External routing"
      : "Active workspace task";

    const body = document.createElement("p");
    body.className = "panel-card__body";
    body.textContent = state.currentTask.scope === "external"
      ? "AURA routed this outside the workspace and stayed nearby in floating presence mode."
      : "AURA kept this inside the workspace so the work can stay focused here.";

    const grid = document.createElement("div");
    grid.className = "panel-card__grid";
    [
      ["Task label", state.currentTask.label],
      ["Scope", capitalize(state.currentTask.scope)],
      ["Request", state.currentTask.text],
      ["Orb layout", humanizeBadge(state.orbLayout)],
    ].forEach(([label, value]) => {
      const field = document.createElement("div");
      field.className = "panel-field";
      const labelNode = document.createElement("span");
      labelNode.textContent = label;
      const valueNode = document.createElement("strong");
      valueNode.textContent = value;
      field.append(labelNode, valueNode);
      grid.appendChild(field);
    });

    card.append(title, body, grid);
    return card;
  }

  function buildScreenShareCard() {
    const card = document.createElement("section");
    card.className = "panel-card";

    const title = document.createElement("p");
    title.className = "panel-card__title";
    title.textContent = "Screen share";

    const body = document.createElement("p");
    body.className = "panel-card__body";
    body.textContent = state.screenShareActive
      ? "Screen capture is active. AURA reflects that state clearly, but it still does not claim live visual understanding."
      : "Screen capture is off. If you start it, AURA will only reflect the capture state honestly.";

    const grid = document.createElement("div");
    grid.className = "panel-card__grid";
    [
      ["Status", state.screenShareActive ? "Active" : "Off"],
      ["Source", state.screenShareLabel || "Off"],
      ["Vision truth", "UI capture only - analysis not implemented"],
    ].forEach(([label, value]) => {
      const field = document.createElement("div");
      field.className = "panel-field";
      const labelNode = document.createElement("span");
      labelNode.textContent = label;
      const valueNode = document.createElement("strong");
      valueNode.textContent = value;
      field.append(labelNode, valueNode);
      grid.appendChild(field);
    });

    card.append(title, body, grid);
    return card;
  }

  function buildOutputsCard() {
    const card = document.createElement("section");
    card.className = "panel-card";

    const title = document.createElement("p");
    title.className = "panel-card__title";
    title.textContent = "Recent outputs";

    const body = document.createElement("p");
    body.className = "panel-card__body";
    body.textContent = "Finished work stays here with previews and direct downloads when you need it again.";

    const list = document.createElement("div");
    list.className = "panel-card__grid";
    state.recentOutputs.forEach((delivery) => {
      list.appendChild(buildDocumentCard(delivery));
    });

    card.append(title, body, list);
    return card;
  }

  function buildNavLink(label, href) {
    const link = document.createElement("a");
    link.className = "link-button";
    link.href = href;
    link.textContent = label;
    return link;
  }

  function renderSidebarSessions() {
    if (!el.chatList || !el.chatListEmpty || !el.historyMeta) {
      return;
    }

    const visibleSessions = buildVisibleSessions();
    const filtered = visibleSessions.filter((session) => {
      if (!state.sidebarSearch) {
        return true;
      }
      const haystack = `${session.session_id} ${session.title || ""}`.toLowerCase();
      return haystack.includes(state.sidebarSearch);
    });

    el.chatList.innerHTML = "";
    el.historyMeta.textContent = `${visibleSessions.length} session${visibleSessions.length === 1 ? "" : "s"}`;
    el.chatListEmpty.hidden = filtered.length > 0;

    filtered.forEach((session) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `session-item${session.session_id === state.sessionId ? " is-active" : ""}`;
      button.addEventListener("click", async () => {
        if (session.session_id === state.sessionId) {
          return;
        }
        state.sessionId = session.session_id;
        localStorage.setItem(STORAGE_KEYS.sessionId, state.sessionId);
        await loadConversation(state.sessionId);
        state.currentTask = null;
        state.currentExternal = null;
        setTaskScope("none");
        setOrbLayout("topbar");
        setAssistantState("idle", "session:conversation_loaded");
        hidePresence(true);
        setComposerStatus("Conversation loaded. I'm here.");
        updateWorkspaceSummary("This workspace is ready again.");
        renderSidebarSessions();
        renderConversation();
        renderRightPanel();
        updateWorkspaceChrome();
      });

      const title = document.createElement("span");
      title.className = "session-item__title";
      title.textContent = session.title || `Chat ${shortSessionId(session.session_id)}`;

      const meta = document.createElement("span");
      meta.className = "session-item__meta";
      meta.innerHTML = `<span>${session.message_count || 0} messages</span><span>${formatSessionStamp(session.last_timestamp || session.started_at)}</span>`;

      button.append(title, meta);
      el.chatList.appendChild(button);
    });
  }

  function buildVisibleSessions() {
    const sessions = (Array.isArray(state.sessions) ? state.sessions : []).map((session) => ({
      ...session,
      title: state.sessionTitles[session.session_id] || "",
    }));
    if (!sessions.some((session) => session.session_id === state.sessionId)) {
      sessions.unshift({
        session_id: state.sessionId,
        title: state.sessionTitles[state.sessionId] || "Current chat",
        started_at: new Date().toISOString(),
        last_timestamp: new Date().toISOString(),
        message_count: state.messages.length,
      });
    }
    return sessions;
  }

  function startNewChat() {
    state.sessionId = generateSessionId();
    localStorage.setItem(STORAGE_KEYS.sessionId, state.sessionId);
    state.messages = [];
    state.currentTask = null;
    state.currentExternal = null;
    setTaskScope("none");
    state.panelVisible = false;
    state.panelMode = "";
    state.screenShareLabel = state.screenShareActive ? state.screenShareLabel : "Off";
    setOrbLayout("topbar");
    setAssistantState("idle", "chat:new_session_started");
    hidePresence(true);
    setComposerStatus("New chat ready. I'm here when you are.");
    updateWorkspaceSummary("A fresh AURA workspace is ready for the next thing you want handled.");
    renderSidebarSessions();
    renderConversation();
    renderRightPanel();
    updateWorkspaceChrome();
  }

  async function toggleScreenShare() {
    state.screenShareActive = false;
    state.screenShareLabel = "Unavailable";
    setAssistantState("error", "ui:screen_capture_disabled");
    setComposerStatus("Screen capture is disabled in this shell.");
    updateWorkspaceSummary("This interface stays focused on chat, push-to-talk voice, and document generation.");
    showPresence({
      mode: state.currentTask?.scope === "external" ? "floating" : "docked",
      eyebrow: "Screen capture",
      title: "I couldn't complete that yet.",
      text: "Screen capture is hidden here until it becomes a real supported workflow.",
      duration: 2200,
    });
    renderRightPanel();
  }

  function stopScreenShare() {
    if (state.screenStream) {
      state.screenStream.getTracks().forEach((track) => track.stop());
    }
    state.screenStream = null;
    state.screenShareActive = false;
    state.screenShareLabel = "Off";
    el.screenShareButton?.classList.remove("is-active");
    setComposerStatus("Screen capture is off.");
    updateWorkspaceSummary("AURA is ready for chat, push-to-talk voice, and document generation.");
    showPresence({
      mode: state.currentTask?.scope === "external" ? "floating" : "docked",
      eyebrow: "Screen capture",
      title: "Screen capture is off.",
      text: "AURA is back to its normal workspace presence.",
      duration: 1500,
    });
    renderRightPanel();
    updateWorkspaceChrome();
  }

  async function processRecognizedTranscript(transcript, mode) {
    const spokenText = String(transcript || "").trim();
    if (!spokenText) {
      return;
    }

    if (mode === "wake") {
      const wakeMatch = detectWakePhrase(spokenText);
      if (!wakeMatch.detected) {
        state.wakeModeEnabled = false;
        syncVoiceControls();
        setComposerStatus('Wake beta listened once, but "Hey AURA" was not detected.');
        setAssistantState("idle", "wake:phrase_not_detected");
        showPresence({
          mode: "center",
          eyebrow: "Wake beta",
          title: "I didn't catch the wake phrase.",
          text: 'Try "Hey AURA" again when you want me.',
          duration: 1700,
        });
        settleToIdleLayout();
        return;
      }
      await runWakeSequence();
      state.wakeModeEnabled = false;
      syncVoiceControls();
      if (wakeMatch.remainingText) {
        appendMessage({
          role: "user",
          text: spokenText,
          badge: "Voice",
          timestamp: new Date().toISOString(),
        });
        rememberSessionTitle(spokenText);
        updateVoiceTranscript(wakeMatch.remainingText, { final: true });
        const classification = classifyCommand(wakeMatch.remainingText);
        if (classification.kind === "external") {
          handleExternalCommand(wakeMatch.remainingText, classification);
        } else {
          await handleInternalCommand(wakeMatch.remainingText, classification);
        }
      }
      return;
    }

    appendMessage({
      role: "user",
      text: spokenText,
      badge: "Voice",
      timestamp: new Date().toISOString(),
    });
    rememberSessionTitle(spokenText);
    updateVoiceTranscript(spokenText, { final: true });
    const commandText = spokenText;

    setAssistantState("analyzing", "voice:transcript_ready_for_chat");
    setComposerStatus(`Heard: "${commandText}". Sending it now.`);
    updateWorkspaceSummary("AURA captured your voice request and is sending it now.");

    const classification = classifyCommand(commandText);
    if (classification.kind === "external") {
      handleExternalCommand(commandText, classification);
      return;
    }

    await handleInternalCommand(commandText, classification);
  }

  async function startSpeechCapture(mode) {
    if (!RecognitionCtor || !state.voiceSupported) {
      logVoiceError("SpeechRecognition unavailable", {
        recognitionCtor: Boolean(RecognitionCtor),
        voiceSupported: state.voiceSupported,
        secureContext: window.isSecureContext,
        mode,
      });
      surfaceVoiceFailure(
        "SpeechRecognition is not available in this browser.",
        {
          event: "voice:unsupported_browser",
          workspaceSummary: "AURA can't start voice input in this browser.",
          title: "Voice input is unavailable.",
          resetMs: 1600,
        },
      );
      return;
    }

    if (state.requestInFlight) {
      const reason = "Talk is unavailable until the current request finishes.";
      logVoiceError("Talk blocked while request in flight", { mode });
      setComposerStatus(reason);
      updateWorkspaceSummary("AURA is still finishing the current request before it can listen again.");
      showPresence({
        mode: "docked",
        eyebrow: "Voice input",
        title: "I'm still working on the last request.",
        text: reason,
        duration: 1800,
      });
      return;
    }

    if (state.recognitionActive) {
      logVoiceError("Talk blocked because recognition is already active", {
        mode,
        recognitionMode: state.recognitionMode,
      });
      setComposerStatus("Voice capture is already active.");
      return;
    }

    clearVoiceTranscript();

    const micPermissionState = await getMicrophonePermissionState();
    if (micPermissionState === "denied") {
      logVoiceError("Microphone permission denied before recognition.start()", {
        mode,
        permissionState: micPermissionState,
      });
      surfaceVoiceFailure(
        "Mic permission denied.",
        {
          event: "voice:permission_denied",
          workspaceSummary: "AURA can't listen until microphone access is allowed.",
          title: "Mic permission denied.",
          resetMs: 1600,
        },
      );
      return;
    }

    setComposerStatus("Click accepted. Waiting for microphone access.");

    const recognition = new RecognitionCtor();
    if (!recognition) {
      logVoiceError("SpeechRecognition instance is null", { mode });
      surfaceVoiceFailure(
        "SpeechRecognition could not be created.",
        {
          event: "voice:recognition_instance_failed",
          workspaceSummary: "AURA could not create a browser recognition session.",
          title: "I couldn't start listening.",
          resetMs: 1600,
        },
      );
      return;
    }
    state.recognition = recognition;
    state.recognitionMode = mode;
    recognition.lang = state.voiceStatus?.settings?.language || "en-US";
    recognition.interimResults = mode === "talk";
    recognition.continuous = false;
    recognition.maxAlternatives = 1;
    let handledFinalResult = false;
    let heardSpeech = false;
    let startWatchdogId = 0;
    const clearStartWatchdog = () => {
      if (startWatchdogId) {
        window.clearTimeout(startWatchdogId);
        startWatchdogId = 0;
      }
    };
    logVoiceDebug("recognition.start() about to run", {
      mode,
      lang: recognition.lang,
      interimResults: recognition.interimResults,
      continuous: recognition.continuous,
      maxAlternatives: recognition.maxAlternatives,
      permissionState: micPermissionState,
    });

    recognition.onstart = () => {
      logVoiceDebug("recognition.onstart", { mode });
      clearStartWatchdog();
      state.recognitionStopReason = "";
      state.recognitionActive = true;
      setOrbLayout("center");
      setAssistantState("listening", "voice:recognition_started");
      if (mode === "talk") {
        setComposerStatus("I'm listening. Speak when you're ready.");
        updateWorkspaceSummary("Microphone is active. AURA is listening for your voice input.");
        showPresence({
          mode: "center",
          eyebrow: "Voice input",
          title: "I'm listening.",
          text: "Speak when you're ready.",
        });
      }
      syncVoiceControls();
    };

    recognition.onerror = (event) => {
      clearStartWatchdog();
      logVoiceError("recognition.onerror", {
        mode,
        error: event?.error || "",
        message: event?.message || "",
      });
      state.recognitionActive = false;
      state.recognition = null;
      state.recognitionMode = "";
      state.recognitionStopReason = "";
      state.speechCommandInFlight = false;
      if (mode === "wake") {
        state.wakeModeEnabled = false;
      }
      syncVoiceControls();
      surfaceVoiceFailure(
        formatSpeechErrorDetail(event),
        {
          event: "voice:recognition_error",
          workspaceSummary: "The browser voice path returned an explicit recognition error.",
          eyebrow: "Voice path",
          title: "I couldn't hear that cleanly.",
          resetMs: 1500,
        },
      );
    };

    recognition.onresult = async (event) => {
      let interimTranscript = "";
      let finalTranscript = "";
      for (let index = event.resultIndex || 0; index < (event.results?.length || 0); index += 1) {
        const result = event.results[index];
        const text = String(result?.[0]?.transcript || "").trim();
        if (!text) {
          continue;
        }
        if (result.isFinal) {
          finalTranscript += `${text} `;
        } else {
          interimTranscript += `${text} `;
        }
      }

      interimTranscript = interimTranscript.trim();
      finalTranscript = finalTranscript.trim();
      logVoiceDebug("recognition.onresult", {
        mode,
        interimTranscript,
        finalTranscript,
        resultCount: event.results?.length || 0,
      });

      if (mode === "talk" && interimTranscript) {
        heardSpeech = true;
        updateVoiceTranscript(interimTranscript, { final: false });
        setComposerStatus("I'm listening. Finish when you're ready.");
      }

      if (!finalTranscript || handledFinalResult) {
        return;
      }

      handledFinalResult = true;
      heardSpeech = true;
      updateVoiceTranscript(finalTranscript, { final: true });
      logVoiceDebug("Final transcript before chat", {
        mode,
        transcript: finalTranscript,
      });
      state.speechCommandInFlight = true;
      try {
        await processRecognizedTranscript(finalTranscript, mode);
      } catch (error) {
        logVoiceError("Voice transcript failed before chat completed", {
          mode,
          message: error?.message || String(error || ""),
          transcript: finalTranscript,
        });
        surfaceVoiceFailure(
          voiceFailureMessageFromError(error, "The voice request failed before chat completed."),
          {
            event: "api:voice_handoff_failed",
            workspaceSummary: "AURA captured your words, but the handoff to chat failed.",
            eyebrow: "Voice handoff",
            title: "I couldn't complete that yet.",
            keepTranscript: true,
            resetMs: 1800,
          },
        );
      } finally {
        state.speechCommandInFlight = false;
        window.setTimeout(() => {
          if (!state.recognitionActive) {
            clearVoiceTranscript();
          }
        }, 2200);
      }
    };

    recognition.onend = () => {
      clearStartWatchdog();
      logVoiceDebug("recognition.onend", {
        mode,
        heardSpeech,
        handledFinalResult,
        stopReason: state.recognitionStopReason,
        requestInFlight: state.requestInFlight,
        speechCommandInFlight: state.speechCommandInFlight,
      });
      const stopReason = state.recognitionStopReason;
      state.recognitionActive = false;
      state.recognition = null;
      state.recognitionMode = "";
      state.recognitionStopReason = "";
      syncVoiceControls();
      if (stopReason === "manual") {
        hidePresence();
        setAssistantState("idle", "voice:recognition_stopped_manually");
        settleToIdleLayout();
        return;
      }
      if (heardSpeech && !handledFinalResult && mode === "talk" && !state.requestInFlight && !state.speechCommandInFlight) {
        const reason = "The browser heard audio, but it never returned a final transcript.";
        logVoiceError("recognition.onend without final transcript", { mode, reason });
        surfaceVoiceFailure(
          reason,
          {
            event: "voice:no_final_transcript",
            workspaceSummary: "AURA heard audio, but the browser never delivered final speech text.",
            title: "I couldn't capture the full transcript.",
            keepTranscript: true,
            resetMs: 1700,
          },
        );
        return;
      }
      if (!heardSpeech && mode === "talk" && !state.requestInFlight && !state.speechCommandInFlight) {
        surfaceVoiceFailure(
          "I didn't catch any speech. Try Talk again.",
          {
            event: "voice:no_speech_detected",
            workspaceSummary: "The microphone opened, but no usable speech came through.",
            title: "I didn't catch anything.",
            resetMs: 1400,
          },
        );
        return;
      }
      if (!state.requestInFlight && !state.speechCommandInFlight) {
        clearVoiceTranscript();
        hidePresence();
        setAssistantState("idle", "voice:recognition_completed");
        settleToIdleLayout();
      }
    };

    try {
      logVoiceDebug("recognition.start() call", { mode });
      recognition.start();
      startWatchdogId = window.setTimeout(() => {
        if (state.recognition === recognition && !state.recognitionActive) {
          logVoiceError("recognition.onstart timeout", { mode });
          try {
            recognition.abort();
          } catch (_error) {
            // Ignore browser abort errors after timeout.
          }
          state.recognition = null;
          state.recognitionMode = "";
          state.recognitionStopReason = "";
          state.speechCommandInFlight = false;
          syncVoiceControls();
          surfaceVoiceFailure(
            "The microphone did not start in time.",
            {
              event: "voice:start_timeout",
              workspaceSummary: "AURA asked the browser to start listening, but the microphone session never became active.",
              title: "I couldn't start listening.",
              resetMs: 1700,
            },
          );
        }
      }, 4000);
    } catch (_error) {
      clearStartWatchdog();
      logVoiceError("recognition.start() threw", {
        mode,
        message: _error?.message || String(_error || ""),
      });
      state.recognitionActive = false;
      state.recognition = null;
      state.recognitionMode = "";
      state.recognitionStopReason = "";
      state.wakeModeEnabled = false;
      state.speechCommandInFlight = false;
      syncVoiceControls();
      surfaceVoiceFailure(
        voiceFailureMessageFromError(_error, "Speech recognition could not start in this browser."),
        {
          event: "voice:start_threw",
          workspaceSummary: "The browser rejected the SpeechRecognition start request.",
          eyebrow: "Voice path",
          title: "I couldn't start listening.",
          resetMs: false,
        },
      );
      settleToIdleLayout();
    }
  }

  function stopRecognition(statusMessage) {
    logVoiceDebug("stopRecognition()", {
      recognitionExists: Boolean(state.recognition),
      statusMessage: statusMessage || "",
    });
    state.recognitionStopReason = "manual";
    if (state.recognition) {
      try {
        state.recognition.stop();
      } catch (_error) {
        // Ignore browser stop errors.
      }
    }
    state.recognitionActive = false;
    state.recognitionMode = "";
    if (statusMessage) {
      setComposerStatus(statusMessage);
    }
    syncVoiceControls();
  }

  function setAssistantState(name, event = "system:unspecified") {
    const nextState = name in STATE_COPY ? name : "idle";
    const nextEvent = String(event || "system:unspecified");
    const shouldLog = state.assistantState !== nextState || state.assistantStateEvent !== nextEvent;

    state.assistantState = nextState;
    state.assistantStateEvent = nextEvent;
    el.body.dataset.assistantState = state.assistantState;
    const copy = STATE_COPY[state.assistantState];

    if (shouldLog) {
      logOrbState(nextState, nextEvent);
    }

    if (el.stateChipLabel) {
      el.stateChipLabel.textContent = copy.label;
    }
    if (el.sidebarState) {
      el.sidebarState.textContent = copy.sidebar;
    }
    if (el.orbStateLabel) {
      el.orbStateLabel.textContent = copy.label;
    }
    if (el.orbModeLabel) {
      el.orbModeLabel.textContent = orbModeLabel(state.orbLayout, copy.orb);
    }
  }

  function setOrbLayout(layout) {
    state.orbLayout = layout;
    el.body.dataset.orbLayout = layout;
    if (el.orbModeLabel) {
      el.orbModeLabel.textContent = orbModeLabel(layout, STATE_COPY[state.assistantState]?.orb);
    }
  }

  function settleToIdleLayout() {
    if (state.currentTask?.scope === "external") {
      setTaskScope("external");
      setOrbLayout("floating");
      return;
    }
    if (state.currentTask?.scope === "internal" && state.messages.length) {
      setTaskScope("internal");
      setOrbLayout("left");
      return;
    }
    setTaskScope("none");
    setOrbLayout("topbar");
  }

  function updateWorkspaceChrome() {
    if (el.accessChip) {
      el.accessChip.textContent = state.auth?.authenticated ? "Authenticated" : "Public";
    }
    if (el.profileEntryName) {
      el.profileEntryName.textContent = currentUserName() || "Guest";
    }
    if (el.profileEntryStatus) {
      el.profileEntryStatus.textContent = state.auth?.authenticated ? "Signed in" : "Public mode";
    }
    if (el.screenChipLabel) {
      el.screenChipLabel.textContent = state.screenShareActive ? "On" : "Off";
    }
    if (!el.workspaceSummary?.textContent) {
      updateWorkspaceSummary("AURA is ready for chat, push-to-talk voice, and document generation.");
    }
    if (el.composerStatus && !state.requestInFlight && !state.recognitionActive && !state.speechCommandInFlight) {
      el.composerStatus.textContent = state.auth?.authenticated
        ? "Type a message, click the orb, or use Talk beta."
        : "Type a message or click the orb. Talk is optional beta.";
    }
  }

  function updateWorkspaceSummary(message) {
    if (el.workspaceSummary) {
      el.workspaceSummary.textContent = message;
    }
  }

  function setComposerStatus(message) {
    if (el.composerStatus) {
      el.composerStatus.textContent = message;
    }
  }

  function autoResizeTextarea() {
    if (!el.messageInput) {
      return;
    }
    el.messageInput.style.height = "auto";
    el.messageInput.style.height = `${Math.min(el.messageInput.scrollHeight, 180)}px`;
  }

  function handleComposerKeydown(event) {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
      return;
    }
    event.preventDefault();
    if (state.requestInFlight) {
      return;
    }
    el.composerForm?.requestSubmit();
  }

  function handleOrbActivation() {
    if (state.requestInFlight || state.recognitionActive || state.speechCommandInFlight) {
      return;
    }
    void runWakeSequence().then(() => {
      resetToCalmIdle(1800);
      window.setTimeout(() => {
        el.messageInput?.focus();
      }, 120);
    });
  }

  function ensureSessionId() {
    const existing = localStorage.getItem(STORAGE_KEYS.sessionId);
    if (existing) {
      return existing;
    }
    const created = generateSessionId();
    localStorage.setItem(STORAGE_KEYS.sessionId, created);
    return created;
  }

  function generateSessionId() {
    return `v2-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  }

  function rememberSessionTitle(text) {
    if (!state.sessionTitles[state.sessionId]) {
      state.sessionTitles[state.sessionId] = buildTitleSnippet(text);
      persistSessionTitles();
      renderSidebarSessions();
    }
  }

  function deriveSessionTitle(messages) {
    const firstUser = (Array.isArray(messages) ? messages : []).find((message) => message.role === "user" && message.text);
    return firstUser ? buildTitleSnippet(firstUser.text) : "";
  }

  function buildTitleSnippet(text) {
    return String(text || "").replace(/\s+/g, " ").trim().slice(0, 46) || "Untitled chat";
  }

  function readSessionTitles() {
    try {
      const payload = JSON.parse(localStorage.getItem(STORAGE_KEYS.sessionTitles) || "{}");
      return payload && typeof payload === "object" ? payload : {};
    } catch (_error) {
      return {};
    }
  }

  function persistSessionTitles() {
    localStorage.setItem(STORAGE_KEYS.sessionTitles, JSON.stringify(state.sessionTitles));
  }

  async function apiJson(url, options) {
    const response = await fetch(url, {
      method: options?.method || "GET",
      credentials: "same-origin",
      headers: {
        "Content-Type": options?.body ? "application/json" : "application/json",
        "X-AURA-Session-Id": state.sessionId,
        ...(options?.headers || {}),
      },
      body: options?.body,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.error || payload.detail || `Request failed (${response.status})`);
    }
    return payload;
  }

  function currentUserName() {
    const user = state.auth?.user || {};
    return user.preferred_name || user.name || user.username || "";
  }

  function buildWakeGreeting() {
    const name = currentUserName();
    return name ? `Hey ${name}, I'm here.` : "Hey, I'm here.";
  }

  function normalizeWakeText(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[.,/#!$%^&*;:{}=_`~()?"']/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function detectWakePhrase(text) {
    const normalized = normalizeWakeText(text);
    const pattern = new RegExp(`^(?:${escapeRegex(WAKE_FALLBACK)})(?:\\s+|$)`);
    if (!pattern.test(normalized)) {
      return { detected: false, remainingText: normalized };
    }
    return {
      detected: true,
      remainingText: normalized.replace(pattern, "").trim(),
    };
  }

  function humanizeSpeechError(code) {
    const messages = {
      "no-speech": "I did not hear anything clearly enough to continue.",
      aborted: "Listening was stopped.",
      "audio-capture": "No microphone input is available.",
      "not-allowed": "Mic permission denied.",
      "service-not-allowed": "Mic permission denied.",
      network: "The browser speech service is unavailable right now.",
    };
    return messages[String(code || "").toLowerCase()] || "The voice path could not continue.";
  }

  function formatSpeechErrorDetail(event) {
    const code = String(event?.error || "").trim();
    const message = String(event?.message || "").trim();
    if (message && code) {
      return `${message} (${code})`;
    }
    if (message) {
      return message;
    }
    if (code) {
      return `${humanizeSpeechError(code)} (${code})`;
    }
    return "The voice path could not continue.";
  }

  function voiceFailureMessageFromError(error, fallback) {
    const message = String(error?.message || "").trim();
    return message || fallback || "The voice path could not continue.";
  }

  function surfaceVoiceFailure(message, options = {}) {
    const detail = String(message || "").trim() || "The voice path could not continue.";
    setAssistantState("error", options.event || "voice:failure");
    setComposerStatus(detail);
    if (options.workspaceSummary) {
      updateWorkspaceSummary(options.workspaceSummary);
    }
    showPresence({
      mode: options.mode || "center",
      eyebrow: options.eyebrow || "Voice input",
      title: options.title || "I couldn't complete that yet.",
      text: detail,
      duration: options.duration || 2200,
    });
    if (!options.keepTranscript) {
      clearVoiceTranscript();
    }
    if (options.resetMs !== false) {
      resetToCalmIdle(options.resetMs || 1600);
    }
  }

  function formatSessionSummary(authPayload) {
    const remaining = Number(authPayload?.session_remaining_seconds);
    if (authPayload?.session_valid && Number.isFinite(remaining) && remaining > 0) {
      if (remaining >= 3600) {
        return `Active for about ${Math.max(1, Math.round(remaining / 3600))}h more`;
      }
      return `Active for about ${Math.max(1, Math.round(remaining / 60))}m more`;
    }
    if (authPayload?.session_valid) {
      return "Active";
    }
    return authPayload?.authenticated ? "Signed in, session status unavailable" : "No active sign-in";
  }

  function humanizeDocumentTitle(type) {
    const normalized = String(type || "document").trim().toLowerCase();
    if (normalized === "assignment") {
      return "Assignment delivery";
    }
    if (normalized === "notes") {
      return "Notes delivery";
    }
    return `${capitalize(normalized)} delivery`;
  }

  function humanizeBadge(value) {
    const text = String(value || "").replace(/[_-]+/g, " ").trim();
    return text ? text.replace(/\b\w/g, (character) => character.toUpperCase()) : "Assistant";
  }

  function orbModeLabel(layout, fallback) {
    const labels = {
      topbar: "Header presence",
      center: "Wake focus",
      left: "Workspace active",
      floating: "External presence",
    };
    return labels[layout] || fallback || "Header presence";
  }

  function shortSessionId(sessionId) {
    const value = String(sessionId || "").trim();
    return value.length > 14 ? value.slice(-14) : value;
  }

  function formatSessionStamp(value) {
    if (!value) {
      return "Just now";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "Recent";
    }
    return new Intl.DateTimeFormat([], {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  }

  function formatClock(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "now";
    }
    return new Intl.DateTimeFormat([], {
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  }

  function scrollConversationToBottom() {
    window.requestAnimationFrame(() => {
      if (el.chatScroll) {
        el.chatScroll.scrollTop = el.chatScroll.scrollHeight;
      }
    });
  }

  function delay(ms) {
    return new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  }

  function capitalize(value) {
    const text = String(value || "").trim();
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
  }

  function escapeRegex(value) {
    return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }
})();
