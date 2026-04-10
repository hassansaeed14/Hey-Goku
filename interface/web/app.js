(() => {
  const STORAGE_KEYS = {
    mode: "aura_interface_mode",
    theme: "aura_interface_theme",
    language: "aura_interface_language",
    readResponses: "aura_read_responses",
    largeText: "aura_large_text",
    simplifiedUi: "aura_simplified_ui",
    highContrast: "aura_high_contrast",
    debugDetails: "aura_debug_details",
    autonomyVisible: "aura_autonomy_visible",
    voiceRate: "aura_voice_rate",
    railPinned: "aura_rail_pinned",
    currentSession: "aura_current_session_id",
  };

  const VIEW_META = {
    chat: { label: "AURA Operating Interface", title: "Chat" },
    memory: { label: "Memory Surface", title: "Memory" },
    intelligence: { label: "Reasoning and Routing", title: "Intelligence" },
    autonomy: { label: "Planning and Execution", title: "Autonomy" },
    tasks: { label: "Structured Follow Through", title: "Tasks and Reminders" },
    history: { label: "Conversation Record", title: "History" },
    settings: { label: "Preferences and Accessibility", title: "Settings" },
  };

  const MODE_META = {
    minimal: {
      name: "Minimal Mode",
      notes: ["Focused chat surface", "Low clutter", "Readable and calm"],
    },
    smart: {
      name: "Smart Mode",
      notes: ["Balanced layout", "Light intelligence hints", "Best everyday default"],
    },
    jarvis: {
      name: "Jarvis Mode",
      notes: ["Cinematic orb", "Voice-first feel", "Stronger presence states"],
    },
    developer: {
      name: "Developer Mode",
      notes: ["Intent and confidence", "Active agent", "Debug-friendly detail"],
    },
    autonomous: {
      name: "Autonomous Mode",
      notes: ["Plan visibility", "Execution focus", "Tool-selection emphasis"],
    },
  };

  const ORB_STATE_META = {
    idle: { title: "Idle", hint: "Standing by for text or voice.", color: "#62d4ff" },
    listening: { title: "Listening", hint: "Capturing your voice input.", color: "#b093ff" },
    thinking: { title: "Thinking", hint: "Understanding the request and routing it.", color: "#f3c66d" },
    speaking: { title: "Speaking", hint: "Reading the response aloud.", color: "#62d4ff" },
    executing: { title: "Executing", hint: "Running the selected plan or tools.", color: "#8f63ff" },
    success: { title: "Success", hint: "Latest action completed cleanly.", color: "#59d091" },
    error: { title: "Error", hint: "AURA hit friction and is surfacing it honestly.", color: "#f06a82" },
    locked: { title: "Locked", hint: "Session secured. Identity confirmation is required.", color: "#7d859a" },
  };

  const CAPABILITY_HIGHLIGHTS = [
    "Study",
    "Research",
    "Coding",
    "Weather",
    "News",
    "Translation",
    "Math",
    "Email",
    "Writing",
    "Quiz",
    "Jokes",
    "Quotes",
    "Passwords",
    "Tasks",
    "Resume",
    "Currency",
    "Dictionary",
    "Screenshot",
    "File Analysis",
    "Memory",
    "Reasoning",
    "Planning",
    "Execution",
    "Fitness",
    "Autonomy",
  ];

  const SUGGESTIONS = [
    "Research hybrid agents and summarize the tradeoffs.",
    "Add a task to review my project notes tomorrow.",
    "Explain my last request in simpler words, then translate it to Urdu.",
    "Plan a study session for AI agents and save the key steps.",
    "Analyze this file request and tell me what permission level it needs.",
    "Give me a workout plan and add reminders for three sessions.",
  ];

  const state = {
    currentView: "chat",
    mode: readStored(STORAGE_KEYS.mode, "smart"),
    theme: readStored(STORAGE_KEYS.theme, "dark"),
    language: readStored(STORAGE_KEYS.language, "auto"),
    settings: {
      readResponses: readBoolean(STORAGE_KEYS.readResponses, false),
      largeText: readBoolean(STORAGE_KEYS.largeText, false),
      simplifiedUi: readBoolean(STORAGE_KEYS.simplifiedUi, false),
      highContrast: readBoolean(STORAGE_KEYS.highContrast, false),
      debugDetails: readBoolean(STORAGE_KEYS.debugDetails, true),
      autonomyVisible: readBoolean(STORAGE_KEYS.autonomyVisible, true),
      voiceRate: readNumber(STORAGE_KEYS.voiceRate, 1),
      railPinned: readBoolean(STORAGE_KEYS.railPinned, true),
    },
    user: null,
    profile: null,
    confirmationStatus: null,
    systemState: "idle",
    lastResult: null,
    systemStatus: null,
    agents: [],
    history: [],
    sessions: [],
    currentSessionId: null,
    sessionMeta: [],
    tasks: [],
    reminders: [],
    taskEditingId: null,
    reminderEditingId: null,
    memoryInsights: null,
    intelligenceInsights: null,
    messages: [],
    historyFilter: "",
    sidebarOpen: false,
    railOpen: false,
    listening: false,
    speaking: false,
    voiceStatus: null,
    voiceProfiles: [],
    voiceInputMode: "unknown",
    voiceActiveSource: null,
    voiceAbortController: null,
    recognition: null,
    speechSupported: "speechSynthesis" in window,
    speechVoice: null,
  };

  const el = {};

  document.addEventListener("DOMContentLoaded", init);

  async function init() {
    cacheDom();
    state.currentSessionId = ensureCurrentSessionId();
    applySettings();
    bindEvents();
    renderStaticSurfaces();
    setSystemState("idle");
    syncVoiceButtons();
    switchView(state.currentView);
    initializeSpeechRecognition();
    seedWelcomeMessage();
    await bootstrapSession();
    await refreshAllData();
  }

  function cacheDom() {
    const ids = [
      "appOverlay", "sidebar", "sidebarCollapse", "brandHome", "modePill", "identityInitial",
      "identityName", "identitySubtitle", "sidebarRailButton", "logoutButton", "mobileNavToggle",
      "adminButton", "orbQuickMenu",
      "currentViewLabel", "currentViewTitle", "systemStateChip", "topbarStateDot", "topbarStateText",
      "topbarActiveAgent", "topbarConfidence", "modeSelect", "voiceToggle", "railToggle", "heroOrb",
      "heroStateText", "heroStateHint", "presenceAgent", "presenceConfidence", "presenceMode",
      "presenceMemory", "heroSignals", "chatFeed", "suggestionStrip", "composerForm", "composerInput",
      "composerHint", "voiceButton", "sendButton", "clearChatButton", "stopSpeechButton",
      "capabilityHighlights", "memoryInitial", "memoryName", "memoryGreetingPreview", "memoryStatusNote",
      "memoryPreferenceList", "memoryFactList", "memoryInterestList", "memoryTopIntents", "memoryInsights",
      "intelIntent", "intelConfidence", "intelAgent", "intelExecutionMode", "intelReasoningStatus",
      "intelPermissionStatus", "intelRecoveryNote", "intelImprovementSummary", "statusSubsystems",
      "capabilityGrid", "autonomyHeadline", "autonomyProgressBar", "autonomyProgressLabel",
      "autonomyTelemetryNote", "autonomyTools", "autonomyCompleted", "autonomyFailed", "autonomyRetries",
      "autonomyTimeline", "taskSummaryPending", "taskSummaryCompleted", "reminderSummaryActive",
      "reminderSummaryCompleted", "refreshTasksButton", "taskForm", "taskText", "taskPriority",
      "taskDueDate", "taskSubmitButton", "taskCancelEditButton", "taskList", "completedTaskList",
      "refreshRemindersButton", "reminderForm", "reminderText", "reminderDate", "reminderTime",
      "reminderSubmitButton", "reminderCancelEditButton", "reminderList", "completedReminderList",
      "historySearch", "historyMetaHint", "historyList", "historyCurrentSession", "historySessionList",
      "settingsMode", "settingsTheme",
      "settingsLanguage", "settingsPreferredName", "settingsTitle", "settingsVoiceProfile",
      "settingsVoiceRate", "settingsVoicePitch", "settingsVoiceVolume", "voicePreviewButton",
      "settingsConfirmCode", "settingsConfirmCodeRepeat", "settingsOldConfirmCode", "settingsNewConfirmCode",
      "settingsNewConfirmCodeRepeat", "setConfirmCodeButton", "changeConfirmCodeButton", "confirmationTriggers",
      "openAdminPanelButton", "toggleReadResponses", "toggleLargeText",
      "toggleSimplifiedUi", "toggleHighContrast", "toggleDebugDetails", "toggleAutonomyVisibility",
      "settingsModeNotes", "intelRail", "mobileRailClose", "railOrb", "railState", "railStateHint",
      "railActiveAgent", "railConfidence", "railPermission", "railUserInitial", "railUserName",
      "railGreeting", "railMemoryFacts", "railPlanList", "railExecutionList", "railImprovementList",
      "railSystemSummary", "navAutonomyCount", "navTaskCount", "navHistoryCount", "toastStack",
    ];

    ids.forEach((id) => {
      el[id] = document.getElementById(id);
    });

    el.body = document.body;
    el.navItems = [...document.querySelectorAll("[data-view-target]")];
    el.modeCards = [...document.querySelectorAll("[data-mode-choice]")];
    el.viewSections = [...document.querySelectorAll(".view-section")];
    el.toggleButtons = [
      el.toggleReadResponses,
      el.toggleLargeText,
      el.toggleSimplifiedUi,
      el.toggleHighContrast,
      el.toggleDebugDetails,
      el.toggleAutonomyVisibility,
    ];
    el.workspaceBody = document.querySelector(".workspace__body");
  }

  function bindEvents() {
    el.navItems.forEach((button) => button.addEventListener("click", () => switchView(button.dataset.viewTarget)));
    el.modeCards.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.modeChoice)));
    el.sidebarCollapse.addEventListener("click", toggleSidebar);
    el.mobileNavToggle.addEventListener("click", toggleSidebar);
    el.appOverlay.addEventListener("click", closeOverlays);
    el.brandHome.addEventListener("click", () => switchView("chat"));
    el.sidebarRailButton.addEventListener("click", () => toggleRail(true));
    el.railToggle.addEventListener("click", () => toggleRail());
    el.mobileRailClose.addEventListener("click", () => toggleRail(false));
    el.adminButton.addEventListener("click", openAdminPanel);
    el.modeSelect.addEventListener("change", (event) => setMode(event.target.value));
    el.settingsMode.addEventListener("change", (event) => setMode(event.target.value));
    el.settingsTheme.addEventListener("change", (event) => updateTheme(event.target.value));
    el.settingsLanguage.addEventListener("change", (event) => updateLanguage(event.target.value));
    el.settingsVoiceRate.addEventListener("input", (event) => updateVoiceRate(Number(event.target.value)));
    el.settingsVoicePitch.addEventListener("input", (event) => updateVoicePitch(Number(event.target.value)));
    el.settingsVoiceVolume.addEventListener("input", (event) => updateVoiceVolume(Number(event.target.value)));
    el.settingsVoiceProfile.addEventListener("change", (event) => updateVoiceProfile(event.target.value));
    el.settingsPreferredName.addEventListener("change", (event) => updateProfileField("preferred_name", event.target.value));
    el.settingsTitle.addEventListener("change", (event) => updateProfileField("title", event.target.value));
    el.toggleReadResponses.addEventListener("click", () => toggleSetting("readResponses"));
    el.toggleLargeText.addEventListener("click", () => toggleSetting("largeText"));
    el.toggleSimplifiedUi.addEventListener("click", () => toggleSetting("simplifiedUi"));
    el.toggleHighContrast.addEventListener("click", () => toggleSetting("highContrast"));
    el.toggleDebugDetails.addEventListener("click", () => toggleSetting("debugDetails"));
    el.toggleAutonomyVisibility.addEventListener("click", () => toggleSetting("autonomyVisible"));
    el.composerForm.addEventListener("submit", handleComposerSubmit);
    el.composerInput.addEventListener("keydown", handleComposerKeydown);
    el.voiceButton.addEventListener("click", handleVoiceToggle);
    el.voiceToggle.addEventListener("click", handleVoiceToggle);
    el.stopSpeechButton.addEventListener("click", stopSpeaking);
    el.clearChatButton.addEventListener("click", handleClearHistoryClick);
    el.historySearch.addEventListener("input", (event) => {
      state.historyFilter = event.target.value.trim().toLowerCase();
      renderHistory();
    });
    el.refreshTasksButton.addEventListener("click", () => loadTasks(true));
    el.refreshRemindersButton.addEventListener("click", () => loadReminders(true));
    el.taskForm.addEventListener("submit", handleTaskSubmit);
    el.reminderForm.addEventListener("submit", handleReminderSubmit);
    el.taskCancelEditButton.addEventListener("click", resetTaskEditor);
    el.reminderCancelEditButton.addEventListener("click", resetReminderEditor);
    el.chatFeed.addEventListener("click", handleMessageActions);
    el.historySessionList.addEventListener("click", handleSessionListClick);
    el.taskList.addEventListener("click", handleTaskListClick);
    el.completedTaskList.addEventListener("click", handleTaskListClick);
    el.reminderList.addEventListener("click", handleReminderListClick);
    el.completedReminderList.addEventListener("click", handleReminderListClick);
    el.logoutButton.addEventListener("click", logout);
    el.voicePreviewButton.addEventListener("click", previewVoice);
    el.setConfirmCodeButton.addEventListener("click", setConfirmationCode);
    el.changeConfirmCodeButton.addEventListener("click", changeConfirmationCode);
    el.openAdminPanelButton.addEventListener("click", openAdminPanel);
    el.heroOrb.addEventListener("click", handleOrbClick);
    el.heroOrb.addEventListener("dblclick", handleOrbDoubleClick);
    el.heroOrb.addEventListener("contextmenu", handleOrbContextMenu);
    el.orbQuickMenu.addEventListener("click", handleOrbMenuClick);
    document.addEventListener("click", handleDocumentClick);
    window.addEventListener("resize", applyResponsiveLayout);
  }

  function readStored(key, fallback) {
    const value = localStorage.getItem(key);
    return value === null ? fallback : value;
  }

  function readBoolean(key, fallback) {
    const value = localStorage.getItem(key);
    return value === null ? fallback : value === "true";
  }

  function readNumber(key, fallback) {
    const value = Number(localStorage.getItem(key));
    return Number.isFinite(value) ? value : fallback;
  }

  function ensureCurrentSessionId() {
    const existing = sanitizeSessionId(localStorage.getItem(STORAGE_KEYS.currentSession));
    if (existing) {
      return existing;
    }

    const created = `session-${new Date().toISOString().replace(/\D/g, "").slice(0, 14)}-${Math.random().toString(36).slice(2, 8)}`;
    localStorage.setItem(STORAGE_KEYS.currentSession, created);
    return created;
  }

  function sanitizeSessionId(value) {
    const cleaned = String(value || "").trim().replace(/[^A-Za-z0-9._:-]+/g, "-");
    return cleaned ? cleaned.slice(0, 120) : "";
  }

  function shortSessionId(sessionId) {
    const value = sanitizeSessionId(sessionId);
    if (!value) {
      return "current";
    }

    if (value.length <= 20) {
      return value;
    }

    return `${value.slice(0, 10)}...${value.slice(-6)}`;
  }

  function setCurrentSessionId(sessionId) {
    const nextId = sanitizeSessionId(sessionId) || ensureCurrentSessionId();
    state.currentSessionId = nextId;
    localStorage.setItem(STORAGE_KEYS.currentSession, nextId);
    renderSessionList();
    renderCurrentSessionBadge();
  }

  function safeJsonParse(value) {
    if (!value) {
      return null;
    }

    try {
      return JSON.parse(value);
    } catch (error) {
      return null;
    }
  }

  function applySettings() {
    el.body.dataset.mode = state.mode;
    el.body.dataset.theme = state.theme;
    el.body.classList.toggle("is-large-text", state.settings.largeText);
    el.body.classList.toggle("is-simple-ui", state.settings.simplifiedUi);
    el.body.classList.toggle("is-high-contrast", state.settings.highContrast);

    el.modeSelect.value = state.mode;
    el.settingsMode.value = state.mode;
    el.settingsTheme.value = state.theme;
    el.settingsLanguage.value = state.language;
    el.settingsVoiceRate.value = String(state.settings.voiceRate);
    el.settingsVoicePitch.value = String(state.profile?.voice_pitch || 1);
    el.settingsVoiceVolume.value = String(state.profile?.voice_volume ?? 1);
    el.settingsPreferredName.value = state.profile?.preferred_name || "";
    el.settingsTitle.value = state.profile?.title || "sir";
    el.modePill.textContent = MODE_META[state.mode].name;
    applyToggleState(el.toggleReadResponses, state.settings.readResponses);
    applyToggleState(el.toggleLargeText, state.settings.largeText);
    applyToggleState(el.toggleSimplifiedUi, state.settings.simplifiedUi);
    applyToggleState(el.toggleHighContrast, state.settings.highContrast);
    applyToggleState(el.toggleDebugDetails, state.settings.debugDetails);
    applyToggleState(el.toggleAutonomyVisibility, state.settings.autonomyVisible);
    syncModeControls();
    populateVoiceProfiles();
    applyResponsiveLayout();
  }

  function applyToggleState(button, value) {
    button.classList.toggle("is-on", value);
    button.setAttribute("aria-pressed", value ? "true" : "false");
  }

  function syncModeControls() {
    el.modeCards.forEach((button) => {
      button.classList.toggle("is-selected", button.dataset.modeChoice === state.mode);
    });

    el.navItems.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.viewTarget === state.currentView);
    });

    renderModeNotes();
    el.presenceMode.textContent = MODE_META[state.mode].name.replace(" Mode", "");
  }

  function renderModeNotes() {
    const notes = MODE_META[state.mode].notes
      .map((note) => `<span class="chip chip--mode">${escapeHtml(note)}</span>`)
      .join("");
    el.settingsModeNotes.innerHTML = notes;
  }

  function renderStaticSurfaces() {
    el.capabilityHighlights.innerHTML = CAPABILITY_HIGHLIGHTS
      .map((label, index) => {
        const variant = index % 5 === 0 ? "chip--mode" : index % 3 === 0 ? "chip--agent" : "";
        return `<span class="chip ${variant}">${escapeHtml(label)}</span>`;
      })
      .join("");

    el.suggestionStrip.innerHTML = SUGGESTIONS
      .map(
        (prompt) =>
          `<button class="suggestion-chip" type="button" data-suggestion="${escapeAttribute(prompt)}">${escapeHtml(prompt)}</button>`,
      )
      .join("");

    el.suggestionStrip.addEventListener("click", (event) => {
      const button = event.target.closest("[data-suggestion]");
      if (!button) {
        return;
      }

      el.composerInput.value = button.dataset.suggestion;
      el.composerInput.focus();
    });
  }

  function switchView(viewName) {
    if (!VIEW_META[viewName]) {
      return;
    }

    state.currentView = viewName;
    el.viewSections.forEach((section) => {
      section.classList.toggle("is-active", section.dataset.view === viewName);
    });

    el.currentViewLabel.textContent = VIEW_META[viewName].label;
    el.currentViewTitle.textContent = VIEW_META[viewName].title;
    syncModeControls();

    if (window.innerWidth <= 1180) {
      closeOverlays();
    }
  }

  function setMode(mode) {
    if (!MODE_META[mode]) {
      return;
    }

    state.mode = mode;
    localStorage.setItem(STORAGE_KEYS.mode, mode);
    applySettings();
    renderMessages();
    renderHistory();
    renderAutonomy();
    renderRail();
  }

  function updateTheme(theme) {
    state.theme = theme;
    localStorage.setItem(STORAGE_KEYS.theme, theme);
    el.body.dataset.theme = theme;
  }

  function updateLanguage(language) {
    state.language = language;
    localStorage.setItem(STORAGE_KEYS.language, language);
    if (state.recognition) {
      state.recognition.lang = language === "urdu" ? "ur-PK" : "en-US";
    }
    updateProfileField("language", language === "auto" ? "en-US" : language === "urdu" ? "ur-PK" : "en-US", { silent: true });
  }

  function updateVoiceRate(rate) {
    state.settings.voiceRate = rate;
    localStorage.setItem(STORAGE_KEYS.voiceRate, String(rate));
    updateProfileField("voice_rate", rate, { silent: true });
  }

  function updateVoicePitch(pitch) {
    updateProfileField("voice_pitch", pitch, { silent: true });
  }

  function updateVoiceVolume(volume) {
    updateProfileField("voice_volume", volume, { silent: true });
  }

  function updateVoiceProfile(profileId) {
    updateProfileField("voice_profile", profileId, { silent: false });
  }

  async function updateProfileField(key, value, options = {}) {
    state.profile = { ...(state.profile || {}), [key]: value };
    if (key === "language") {
      state.language = value;
    }
    if (key === "voice_rate") {
      state.settings.voiceRate = Number(value);
    }
    applySettings();

    try {
      await fetchJson("/api/settings/profile", {
        method: "PATCH",
        body: JSON.stringify({ [key]: value }),
      });
    } catch (error) {
      if (!options.silent) {
        showToast("Could not save settings", error.message, true);
      }
    }
  }

  function populateVoiceProfiles() {
    const profiles = state.voiceStatus?.personas || [];
    state.voiceProfiles = profiles;
    if (!el.settingsVoiceProfile) {
      return;
    }

    if (!profiles.length) {
      el.settingsVoiceProfile.innerHTML = `<option value="jarvis">Jarvis</option>`;
      el.settingsVoiceProfile.value = state.profile?.voice_profile || "jarvis";
      return;
    }

    el.settingsVoiceProfile.innerHTML = profiles
      .map((profile) => `<option value="${escapeAttribute(profile.id)}">${escapeHtml(profile.name)}</option>`)
      .join("");
    el.settingsVoiceProfile.value = state.profile?.voice_profile || state.voiceStatus?.settings?.profile_id || profiles[0].id;
  }

  function toggleSetting(key) {
    state.settings[key] = !state.settings[key];
    localStorage.setItem(STORAGE_KEYS[key], String(state.settings[key]));
    if (key === "readResponses") {
      updateProfileField("auto_speak", state.settings[key], { silent: true });
    }
    applySettings();
    renderMessages();
    renderHistory();
    renderRail();
  }

  function toggleSidebar(force) {
    const next = typeof force === "boolean" ? force : !state.sidebarOpen;
    state.sidebarOpen = next;
    el.body.classList.toggle("is-sidebar-open", next);
    syncOverlay();
  }

  function toggleRail(force) {
    const desktop = window.innerWidth > 1180;
    if (desktop) {
      const nextPinned = typeof force === "boolean" ? force : !state.settings.railPinned;
      state.settings.railPinned = nextPinned;
      localStorage.setItem(STORAGE_KEYS.railPinned, String(nextPinned));
      applyResponsiveLayout();
      return;
    }

    const next = typeof force === "boolean" ? force : !state.railOpen;
    state.railOpen = next;
    el.body.classList.toggle("is-rail-open", next);
    syncOverlay();
  }

  function closeOverlays() {
    state.sidebarOpen = false;
    state.railOpen = false;
    el.body.classList.remove("is-sidebar-open", "is-rail-open");
    syncOverlay();
  }

  function syncOverlay() {
    const shouldShow = state.sidebarOpen || state.railOpen;
    el.appOverlay.hidden = !shouldShow;
  }

  function applyResponsiveLayout() {
    const desktop = window.innerWidth > 1180;
    const modeAllowsRail = state.settings.autonomyVisible && state.mode !== "minimal";
    const showRail = desktop && modeAllowsRail && state.settings.railPinned;

    el.workspaceBody.style.gridTemplateColumns = showRail ? "minmax(0, 1fr) var(--rail-width)" : "minmax(0, 1fr)";
    el.intelRail.style.display = showRail || !desktop ? "" : "none";

    if (desktop) {
      state.sidebarOpen = false;
      state.railOpen = false;
      el.body.classList.remove("is-sidebar-open", "is-rail-open");
      el.appOverlay.hidden = true;
    }
  }

  function syncIdentity() {
    const rememberedName =
      state.profile?.preferred_name ||
      state.memoryInsights?.remembered_name ||
      state.user?.name ||
      state.user?.username ||
      "Guest";
    const initial = rememberedName.trim().charAt(0).toUpperCase() || "A";

    el.identityInitial.textContent = initial;
    el.memoryInitial.textContent = initial;
    el.railUserInitial.textContent = initial;
    el.identityName.textContent = rememberedName;
    el.memoryName.textContent = rememberedName;
    el.railUserName.textContent = rememberedName;
    el.identitySubtitle.textContent = state.user ? `Access: ${(state.user.owner ? "OWNER" : "APPROVED USER")}` : "AURA is ready";
    el.adminButton.hidden = !Boolean(state.user?.admin);
    el.openAdminPanelButton.hidden = !Boolean(state.user?.admin);
  }

  async function bootstrapSession() {
    try {
      const payload = await fetchJson("/api/auth/session");
      if (payload.setup_required) {
        window.location.href = "/setup";
        return;
      }
      if (!payload.authenticated) {
        window.location.href = "/login";
        return;
      }
      state.user = payload.user || null;
    } catch (error) {
      window.location.href = "/login";
    }
  }

  async function refreshAllData() {
    await Promise.allSettled([
      loadProfileSettings(),
      loadSystemStatus(),
      loadAgents(),
      loadSessions(),
      loadHistory(),
      loadMemoryInsights(),
      loadIntelligenceInsights(),
      loadVoiceRuntimeStatus(),
      loadConfirmationStatus(),
      loadTasks(),
      loadReminders(),
    ]);

    syncIdentity();
    renderMemory();
    renderIntelligence();
    renderAutonomy();
    renderTasks();
    renderHistory();
    renderRail();
    updateHeaderMetrics();
  }

  async function loadProfileSettings(silent = true) {
    try {
      const payload = await fetchJson("/api/settings/profile");
      state.profile = payload.profile || {};
      state.user = payload.user || state.user;
      if (typeof state.profile.auto_speak === "boolean") {
        state.settings.readResponses = state.profile.auto_speak;
      }
      if (Number.isFinite(Number(state.profile.voice_rate))) {
        state.settings.voiceRate = Number(state.profile.voice_rate);
      }
      applySettings();
      syncIdentity();
    } catch (error) {
      if (!silent) {
        showToast("Profile unavailable", error.message, true);
      }
    }
  }

  async function loadConfirmationStatus(silent = true) {
    try {
      state.confirmationStatus = await fetchJson("/api/confirmation-code/status");
      renderConfirmationStatus();
    } catch (error) {
      state.confirmationStatus = null;
      if (!silent) {
        showToast("Confirmation status unavailable", error.message, true);
      }
    }
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });

    if (!response.ok) {
      let message = `Request failed with status ${response.status}.`;
      try {
        const payload = await response.json();
        message = payload.detail || payload.message || message;
      } catch (error) {
        message = await response.text() || message;
      }
      if (response.status === 401) {
        window.location.href = "/login";
      }
      throw new Error(message);
    }

    return response.json();
  }

  async function loadSystemStatus(silent = true) {
    try {
      state.systemStatus = await fetchJson("/api/system/status");
      renderIntelligence();
      renderRail();
    } catch (error) {
      if (!silent) {
        showToast("System status unavailable", error.message, true);
      }
    }
  }

  async function loadAgents(silent = true) {
    try {
      const payload = await fetchJson("/api/agents");
      state.agents = payload.agents || [];
      renderCapabilityGrid();
    } catch (error) {
      if (!silent) {
        showToast("Agent registry unavailable", error.message, true);
      }
    }
  }

  async function loadSessions(silent = true) {
    try {
      const payload = await fetchJson("/api/sessions");
      state.sessions = Array.isArray(payload.sessions) ? payload.sessions : [];
      renderSessionList();
      renderCurrentSessionBadge();
    } catch (error) {
      state.sessions = [];
      renderSessionList();
      renderCurrentSessionBadge();
      if (!silent) {
        showToast("Sessions unavailable", error.message, true);
      }
    }
  }

  async function loadHistory(silent = true, sessionId = state.currentSessionId) {
    const targetSessionId = sanitizeSessionId(sessionId) || ensureCurrentSessionId();
    setCurrentSessionId(targetSessionId);

    try {
      const payload = await fetchJson(`/api/history?session_id=${encodeURIComponent(targetSessionId)}`);
      state.history = Array.isArray(payload.messages) ? payload.messages : [];
      hydrateChatFromHistory();
      renderHistory();
      renderCurrentSessionBadge();
      el.navHistoryCount.textContent = String(state.history.length);
    } catch (error) {
      state.history = [];
      if (!state.messages.length) {
        seedWelcomeMessage();
      }
      renderHistory();
      el.navHistoryCount.textContent = "0";
      if (!silent) {
        showToast("History unavailable", error.message, true);
      }
    }
  }

  async function loadMemoryInsights(silent = true) {
    const username = state.user?.username || "guest";
    try {
      state.memoryInsights = await fetchJson(`/api/memory/insights?username=${encodeURIComponent(username)}`);
      syncIdentity();
      renderMemory();
      renderRail();
    } catch (error) {
      if (!silent) {
        showToast("Memory insights unavailable", error.message, true);
      }
    }
  }

  async function loadIntelligenceInsights(silent = true) {
    try {
      state.intelligenceInsights = await fetchJson("/api/intelligence/insights");
      renderIntelligence();
      renderAutonomy();
      renderRail();
    } catch (error) {
      if (!silent) {
        showToast("Intelligence insights unavailable", error.message, true);
      }
    }
  }

  async function loadVoiceRuntimeStatus(silent = true) {
    try {
      state.voiceStatus = await fetchJson("/api/voice/status");
      if (state.voiceStatus?.user_profile) {
        state.profile = { ...(state.profile || {}), ...state.voiceStatus.user_profile };
      }
    } catch (error) {
      state.voiceStatus = null;
      if (!silent) {
        showToast("Voice status unavailable", error.message, true);
      }
    }

    state.voiceInputMode = getPreferredVoiceInputMode();
    populateVoiceProfiles();
    syncVoiceButtons();
  }

  async function loadTasks(showToastOnSuccess = false) {
    try {
      const payload = await fetchJson("/api/tasks");
      state.tasks = payload.items || [];
      renderTasks();
      if (showToastOnSuccess) {
        showToast("Tasks refreshed", `${state.tasks.length} task records loaded.`);
      }
    } catch (error) {
      showToast("Tasks unavailable", error.message, true);
    }
  }

  async function loadReminders(showToastOnSuccess = false) {
    try {
      const payload = await fetchJson("/api/reminders");
      state.reminders = payload.items || [];
      renderTasks();
      if (showToastOnSuccess) {
        showToast("Reminders refreshed", `${state.reminders.length} reminder records loaded.`);
      }
    } catch (error) {
      showToast("Reminders unavailable", error.message, true);
    }
  }

  function seedWelcomeMessage() {
    const welcome = state.user?.name
      ? `Welcome back, ${state.user.name}. AURA is ready for multi-step requests, memory-aware routing, and structured execution.`
      : "AURA is ready. You can speak naturally, mix requests together, and use short forms or typos without needing perfect phrasing.";

    state.messages = [
      {
        id: crypto.randomUUID(),
        role: "assistant",
        text: welcome,
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        meta: {
          intent: "system",
          activeAgent: "General",
          confidence: null,
          executionMode: "ready",
        },
      },
    ];

    renderMessages();
  }

  function hydrateChatFromHistory() {
    if (!state.history.length) {
      seedWelcomeMessage();
      return;
    }

    state.messages = state.history.map((entry) => ({
      id: `history-${entry.id}`,
      role: entry.role === "user" ? "user" : "assistant",
      text: entry.message || "",
      time: formatTimestamp(entry.timestamp),
      meta: {
        intent: entry.role === "user" ? "input" : (entry.intent || "general"),
        activeAgent: entry.role === "assistant" ? (entry.agent_used || "AURA") : null,
        executionMode: entry.mode || "history",
        loading: false,
        streaming: false,
      },
    }));

    renderMessages();
  }

  function updateHeaderMetrics() {
    const lastAgent = getPrimaryAgentLabel();
    const confidenceValue = getConfidenceText(state.lastResult?.confidence);
    el.topbarActiveAgent.textContent = lastAgent;
    el.topbarConfidence.textContent = confidenceValue;
    el.presenceAgent.textContent = lastAgent;
    el.presenceConfidence.textContent = confidenceValue;
    el.railActiveAgent.textContent = lastAgent;
    el.railConfidence.textContent = confidenceValue;
    el.presenceMemory.textContent = state.memoryInsights ? "Connected" : "Adaptive";
  }

  function handleComposerSubmit(event) {
    event.preventDefault();
    sendMessage();
  }

  function handleComposerKeydown(event) {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
      return;
    }

    event.preventDefault();
    sendMessage();
  }

  async function sendMessage(textOverride = null) {
    if (el.sendButton.disabled) {
      return;
    }

    const text = (typeof textOverride === "string" ? textOverride : el.composerInput.value).trim();
    if (!text) {
      showToast("Nothing to send yet", "Type or speak a request and AURA will handle the rest.", true);
      el.composerInput.focus();
      return;
    }

    pushMessage("user", text, { intent: "input" });
    el.composerInput.value = "";
    const replyId = pushMessage("assistant", "", {
      intent: "system",
      activeAgent: "AURA",
      executionMode: "thinking",
      loading: true,
      streaming: false,
    });
    setSystemState("thinking");
    setComposerBusy(true);

    try {
      const result = await requestChatResponse(text, replyId);

      setCurrentSessionId(result.session_id || state.currentSessionId);
      state.lastResult = { ...result, input: text };
      registerSessionMeta(text, result);
      setSystemState(result.plan?.length ? "executing" : "success");
      updateMessage(replyId, {
        text: result.response,
        meta: {
          ...buildMessageMeta(result),
          loading: false,
          streaming: false,
        },
      });
      updateComposerHint(result);
      updateHeaderMetrics();
      renderMemory();
      renderIntelligence();
      renderAutonomy();
      renderHistory();
      renderRail();

      if (result.history_status && result.history_status.saved === false) {
        showToast("History unavailable", result.history_status.error || "Chat history could not be saved locally.", true);
      }

      await Promise.allSettled([loadSessions(), loadHistory(), loadMemoryInsights(), loadIntelligenceInsights()]);

      if (state.settings.readResponses) {
        speakText(result.response);
      } else {
        window.setTimeout(() => setSystemState("idle"), 1200);
      }
    } catch (error) {
      setSystemState("error");
      updateMessage(replyId, {
        text: error.message,
        meta: {
          intent: "error",
          activeAgent: "System",
          permissionStatus: "Unavailable",
          confidence: null,
          executionMode: "error",
          loading: false,
          streaming: false,
        },
      });
      showToast("Command failed", error.message, true);
    } finally {
      setComposerBusy(false);
    }
  }

  async function requestChatResponse(text, messageId) {
    return requestChatResponsePost(text, messageId);
  }

  async function requestChatResponsePost(text, messageId) {
    updateMessage(messageId, {
      text: "thinking...",
      meta: {
        activeAgent: "AURA",
        executionMode: "thinking",
        loading: true,
        streaming: false,
      },
    });

    const apiResponse = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-AURA-Session-Id": state.currentSessionId,
      },
      body: JSON.stringify({ message: text, mode: "hybrid" }),
    });

    if (!apiResponse.ok) {
      let message = `Request failed with status ${apiResponse.status}.`;
      try {
        const payload = await apiResponse.json();
        message = payload.detail || payload.message || payload.error || message;
      } catch (error) {
        message = await apiResponse.text() || message;
      }
      throw new Error(message);
    }

    const payload = await apiResponse.json();
    return normalizeChatResult(payload, text);
  }

  function normalizeChatResult(payload, text) {
    const responseText =
      payload.response ||
      payload.reply ||
      payload.answer ||
      payload.output ||
      payload.result;

    if (payload.status === "error") {
      throw new Error(payload.error || payload.message || "The chat route returned an error.");
    }

    if (!responseText) {
      throw new Error("The chat route returned no reply.");
    }

    return {
      ...payload,
      input: payload.input || text,
      session_id: payload.session_id || state.currentSessionId,
      response: responseText,
      intent: payload.intent || payload.detected_intent || "general",
      detected_intent: payload.detected_intent || payload.intent || "general",
      confidence: payload.confidence ?? null,
      plan: Array.isArray(payload.plan) ? payload.plan : [],
      used_agents: Array.isArray(payload.used_agents)
        ? payload.used_agents
        : (payload.agent || payload.agent_used ? [payload.agent || payload.agent_used] : []),
      execution_mode: payload.execution_mode || payload.mode || "chat",
      decision: payload.decision || {},
      orchestration: payload.orchestration || {},
      permission_action: payload.permission_action || null,
      permission: payload.permission || {},
      agent_capabilities: Array.isArray(payload.agent_capabilities) ? payload.agent_capabilities : [],
    };
  }

  function setComposerBusy(isBusy) {
    el.sendButton.disabled = isBusy;
    el.voiceButton.disabled = isBusy;
    el.sendButton.textContent = isBusy ? "Routing..." : "Send to AURA";
  }

  function pushMessage(role, text, meta = {}) {
    const id = crypto.randomUUID();
    state.messages.push({
      id,
      role,
      text,
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      meta,
    });
    renderMessages();
    return id;
  }

  function updateMessage(messageId, updates = {}) {
    const index = state.messages.findIndex((message) => message.id === messageId);
    if (index === -1) {
      return null;
    }

    const current = state.messages[index];
    state.messages[index] = {
      ...current,
      ...(Object.prototype.hasOwnProperty.call(updates, "text") ? { text: updates.text } : {}),
      ...(updates.time ? { time: updates.time } : {}),
      meta: updates.meta ? { ...(current.meta || {}), ...updates.meta } : current.meta,
    };
    renderMessages();
    return state.messages[index];
  }

  function closeActiveChatStream() {}

  function removeMessage(messageId) {
    const nextMessages = state.messages.filter((message) => message.id !== messageId);
    if (nextMessages.length === state.messages.length) {
      return;
    }

    state.messages = nextMessages;
    renderMessages();
  }

  function renderMessages() {
    el.chatFeed.innerHTML = state.messages
      .map((message, index) => buildMessageCard(message, index))
      .join("");

    el.chatFeed.scrollTop = el.chatFeed.scrollHeight;
  }

  function buildMessageCard(message, index) {
    const isAssistant = message.role === "assistant";
    const meta = message.meta || {};
    const badges = [];

    if (meta.intent && meta.intent !== "input" && meta.intent !== "system") {
      badges.push(`<span class="message__badge message__badge--intent">${escapeHtml(meta.intent)}</span>`);
    }
    if (meta.activeAgent) {
      badges.push(`<span class="message__badge message__badge--agent">${escapeHtml(meta.activeAgent)}</span>`);
    }
    if (meta.confidence !== null && meta.confidence !== undefined) {
      const confidenceClass = meta.confidence < 0.4 ? "message__badge--warning" : "message__badge--success";
      badges.push(`<span class="message__badge ${confidenceClass}">confidence ${escapeHtml(getConfidenceText(meta.confidence))}</span>`);
    }
    if (meta.permissionStatus) {
      const permissionClass = /pin|blocked|denied|critical/i.test(meta.permissionStatus)
        ? "message__badge--error"
        : /ask|session|private|sensitive/i.test(meta.permissionStatus)
          ? "message__badge--warning"
          : "message__badge--success";
      badges.push(`<span class="message__badge ${permissionClass}">${escapeHtml(meta.permissionStatus)}</span>`);
    }

    const actionButtons = isAssistant && !meta.loading
      ? `
        <div class="message__actions">
          <button class="message__action" type="button" data-message-action="copy" data-message-index="${index}">Copy</button>
          <button class="message__action" type="button" data-message-action="read" data-message-index="${index}">Read</button>
          <button class="message__action" type="button" data-message-action="retry" data-message-index="${index}">Retry</button>
        </div>
      `
      : "";

    return `
      <article class="message message--${message.role}">
        <div class="message__shell">
          <div class="message__header">
            <div class="message__title">
              <span class="message__kicker">${message.role === "user" ? "User input" : "AURA response"}</span>
              <strong>${message.role === "user" ? "You" : "AURA"}</strong>
            </div>
            <span class="message__time">${escapeHtml(message.time)}</span>
          </div>
          <div class="message__body">
            ${badges.length ? `<div class="message__badges">${badges.join("")}</div>` : ""}
            <div class="message__text ${meta.streaming ? "message__text--streaming" : ""}">${formatMessageText(message.text)}</div>
            ${isAssistant && meta.activeAgent ? `<div class="message__subnote">Agent used: ${escapeHtml(meta.activeAgent)}</div>` : ""}
            ${isAssistant ? buildMessageSections(meta) : ""}
          </div>
          ${actionButtons}
        </div>
      </article>
    `;
  }

  function buildMessageSections(meta) {
    const sections = [];

    if (Array.isArray(meta.plan) && meta.plan.length) {
      sections.push(buildDetailsSection("Plan", `${meta.plan.length} steps`, meta.plan.map((step) => `<li class="segment-list__item">${escapeHtml(step)}</li>`).join(""), "ol"));
    }

    if (Array.isArray(meta.usedAgents) && meta.usedAgents.length > 1) {
      sections.push(buildDetailsSection("Agent route", `${meta.usedAgents.length} agents`, meta.usedAgents.map((agent) => `<li class="segment-list__item">${escapeHtml(agent)}</li>`).join(""), "ul"));
    }

    if (meta.executionMode || meta.permissionAction) {
      const items = [
        meta.executionMode ? `<li><strong>Execution</strong>: ${escapeHtml(meta.executionMode)}</li>` : "",
        meta.permissionAction ? `<li><strong>Permission action</strong>: ${escapeHtml(meta.permissionAction)}</li>` : "",
        meta.multiCommand ? `<li><strong>Multi-command</strong>: grouped and handled as separate routed actions.</li>` : "",
      ].filter(Boolean).join("");

      if (items) {
        sections.push(buildDetailsSection("Execution block", "runtime", items, "ul"));
      }
    }

    if (state.settings.debugDetails && (meta.decision || meta.orchestration)) {
      const debugItems = [
        meta.decision ? `<li>${escapeHtml(JSON.stringify(meta.decision))}</li>` : "",
        meta.orchestration ? `<li>${escapeHtml(JSON.stringify(meta.orchestration))}</li>` : "",
      ].filter(Boolean).join("");

      if (debugItems) {
        sections.push(buildDetailsSection("Developer details", "advanced", debugItems, "ul"));
      }
    }

    if (meta.reasoningTrace && (state.mode === "developer" || state.settings.debugDetails)) {
      const traceItems = [
        `<li><strong>Intent</strong>: ${escapeHtml(meta.reasoningTrace.intent_detected || "general")}</li>`,
        `<li><strong>Confidence</strong>: ${escapeHtml(String(meta.reasoningTrace.confidence_score ?? "--"))}</li>`,
        `<li><strong>Agents</strong>: ${escapeHtml((meta.reasoningTrace.agents_involved || []).join(", ") || "general")}</li>`,
        `<li><strong>Thinking result</strong>: ${escapeHtml(meta.reasoningTrace.critical_thinking_result || "ready")}</li>`,
        `<li><strong>Time</strong>: ${escapeHtml(String(meta.reasoningTrace.time_taken_ms || 0))} ms</li>`,
      ].join("");
      sections.push(buildDetailsSection("AURA's reasoning", "debug", traceItems, "ul"));
    }

    return sections.join("");
  }

  function buildDetailsSection(title, metaLabel, body, listTag) {
    return `
      <details class="message-section">
        <summary class="message-section__summary">
          <span>${escapeHtml(title)}</span>
          <span>${escapeHtml(metaLabel)}</span>
        </summary>
        <div class="message-section__content">
          <${listTag} class="${listTag === "ul" ? "metadata-list" : "segment-list"}">${body}</${listTag}>
        </div>
      </details>
    `;
  }

  function buildMessageMeta(result) {
    const permissionStatus =
      result.permission?.status ||
      result.permission?.permission?.reason ||
      result.permission?.permission?.level ||
      "Approved";

    return {
      intent: result.detected_intent || result.intent || "general",
      activeAgent: getAgentNameFromResult(result),
      confidence: result.confidence ?? null,
      usedAgents: result.used_agents || [],
      plan: result.plan || [],
      executionMode: result.execution_mode || "unknown",
      multiCommand: result.intent === "multi_command",
      permissionAction: result.permission_action || "general",
      permissionStatus,
      decision: result.decision || null,
      orchestration: result.orchestration || null,
      reasoningTrace: result.reasoning_trace || null,
    };
  }

  function updateComposerHint(result) {
    if ((result.confidence || 0) < 0.4) {
      el.composerHint.textContent = "AURA handled that with low confidence and surfaced the uncertainty instead of pretending certainty.";
      return;
    }

    if (result.intent === "multi_command") {
      el.composerHint.textContent = "AURA detected multiple requests and grouped them into routed actions.";
      return;
    }

    el.composerHint.textContent = "AURA supports messy input, split requests, memory-aware routing, and confidence-aware recovery.";
  }

  function registerSessionMeta(input, result) {
    state.sessionMeta.unshift({
      user: input,
      aura: result.response,
      meta: buildMessageMeta(result),
      time: new Date().toISOString(),
    });
  }

  function handleMessageActions(event) {
    const button = event.target.closest("[data-message-action]");
    if (!button) {
      return;
    }

    const index = Number(button.dataset.messageIndex);
    const message = state.messages[index];
    if (!message) {
      return;
    }

    if (button.dataset.messageAction === "copy") {
      navigator.clipboard.writeText(message.text).then(() => {
        showToast("Copied", "The response is on your clipboard.");
      });
      return;
    }

    if (button.dataset.messageAction === "read") {
      speakText(message.text);
      return;
    }

    if (button.dataset.messageAction === "retry") {
      const priorUser = [...state.messages.slice(0, index)].reverse().find((entry) => entry.role === "user");
      if (priorUser) {
        sendMessage(priorUser.text);
      }
    }
  }

  function clearChatSurface() {
    closeActiveChatStream();
    state.lastResult = null;
    seedWelcomeMessage();
    setSystemState("idle");
    renderIntelligence();
    renderAutonomy();
    renderRail();
    updateHeaderMetrics();
  }

  async function handleClearHistoryClick() {
    if (!state.currentSessionId) {
      return;
    }

    if (!window.confirm("Clear the stored history for this session from local AURA storage?")) {
      return;
    }

    try {
      await fetchJson(`/api/history?session_id=${encodeURIComponent(state.currentSessionId)}`, {
        method: "DELETE",
      });
      state.history = [];
      state.sessionMeta = [];
      clearChatSurface();
      renderHistory();
      await loadSessions();
      showToast("History cleared", "AURA removed this session from local SQLite history.");
    } catch (error) {
      showToast("Could not clear history", error.message, true);
    }
  }

  async function handleSessionListClick(event) {
    const button = event.target.closest("[data-session-id]");
    if (!button) {
      return;
    }

    const sessionId = sanitizeSessionId(button.dataset.sessionId);
    if (!sessionId) {
      return;
    }

    try {
      await loadHistory(true, sessionId);
      switchView("chat");
      showToast("Session loaded", "AURA loaded that stored session into the chat window.");
    } catch (error) {
      showToast("Could not load session", error.message, true);
    }
  }

  function browserSpeechRecognitionSupported() {
    return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  function isLocalHostConnection() {
    const hostname = (window.location.hostname || "").toLowerCase();
    return ["localhost", "127.0.0.1", "::1"].includes(hostname);
  }

  function microphoneRequiresSecureConnection() {
    if (window.isSecureContext) {
      return false;
    }

    return !isLocalHostConnection();
  }

  function getPreferredVoiceInputMode() {
    const backendReady = Boolean(
      state.voiceStatus?.web_input?.recommended_mode === "backend_host_microphone"
      || (
        state.voiceStatus?.stt?.supports_microphone
        && state.voiceStatus?.microphone?.available
      ),
    );

    if (backendReady && isLocalHostConnection()) {
      return "backend-host";
    }

    if (browserSpeechRecognitionSupported()) {
      return "browser-only";
    }

    return "unavailable";
  }

  async function ensureMicrophonePermission() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone not available");
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
  }

  function applyListeningVisualState(isListening) {
    [el.voiceButton, el.voiceToggle].forEach((button) => {
      if (!button) {
        return;
      }
      button.classList.toggle("is-on", isListening);
      button.setAttribute("aria-pressed", isListening ? "true" : "false");
    });
  }

  function resetVoiceCaptureState({ keepErrorState = false } = {}) {
    state.listening = false;
    state.voiceActiveSource = null;
    state.voiceAbortController = null;
    syncVoiceButtons();
    if (!state.speaking) {
      setSystemState(keepErrorState ? "error" : "idle");
    }
  }

  async function startBackendVoiceCapture() {
    state.voiceActiveSource = "backend";
    state.listening = true;
    setSystemState("listening");
    syncVoiceButtons();

    const controller = new AbortController();
    state.voiceAbortController = controller;

    try {
      const payload = await fetchJson("/api/voice/microphone", {
        method: "POST",
        body: JSON.stringify({ timeout: 6, phrase_time_limit: 10 }),
        signal: controller.signal,
      });

      if (!payload.success) {
        throw new Error(payload.message || "Microphone input could not be transcribed.");
      }

      const transcript = (payload.cleaned_text || payload.text || "").trim();
      if (!transcript) {
        throw new Error("No speech detected.");
      }

      el.composerInput.value = transcript;
      el.composerInput.focus();
      el.composerInput.setSelectionRange(transcript.length, transcript.length);
      showToast("Transcript ready", "AURA pasted the microphone transcript into the chat box.");
      resetVoiceCaptureState();
    } catch (error) {
      if (error.name === "AbortError") {
        resetVoiceCaptureState();
        return;
      }

      resetVoiceCaptureState({ keepErrorState: true });
      showToast("Voice input issue", error.message || "Microphone transcription failed.", true);
    }
  }

  function initializeSpeechRecognition() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      state.recognition = null;
      state.voiceInputMode = getPreferredVoiceInputMode();
      syncVoiceButtons();
      return;
    }

    state.recognition = new Recognition();
    state.recognition.lang = state.language === "urdu" ? "ur-PK" : "en-US";
    state.recognition.interimResults = false;
    state.recognition.maxAlternatives = 1;

    state.recognition.addEventListener("start", () => {
      state.voiceActiveSource = "browser";
      state.listening = true;
      setSystemState("listening");
      syncVoiceButtons();
    });

    state.recognition.addEventListener("end", () => {
      resetVoiceCaptureState();
    });

    state.recognition.addEventListener("result", (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript?.trim();
      if (!transcript) {
        return;
      }
      el.composerInput.value = transcript;
      el.composerInput.focus();
      el.composerInput.setSelectionRange(transcript.length, transcript.length);
      showToast("Transcript ready", "AURA pasted the microphone transcript into the chat box.");
    });

    state.recognition.addEventListener("error", (event) => {
      resetVoiceCaptureState({ keepErrorState: true });
      showToast("Voice input issue", event.error || "Speech recognition failed.", true);
    });

    state.voiceInputMode = getPreferredVoiceInputMode();
    syncVoiceButtons();
  }

  async function handleVoiceToggle() {
    if (state.listening) {
      if (state.voiceActiveSource === "backend" && state.voiceAbortController) {
        state.voiceAbortController.abort();
      } else if (state.voiceActiveSource === "browser" && state.recognition) {
        state.recognition.stop();
      } else {
        resetVoiceCaptureState();
      }
      return;
    }

    if (microphoneRequiresSecureConnection()) {
      showToast("Secure connection required", "Microphone requires HTTPS or localhost.", true);
      el.composerHint.textContent = "Microphone requires HTTPS or localhost before AURA can listen.";
      return;
    }

    try {
      await ensureMicrophonePermission();
    } catch (error) {
      showToast("Microphone not available", error.message || "Microphone not available", true);
      state.voiceInputMode = getPreferredVoiceInputMode();
      syncVoiceButtons();
      return;
    }

    const preferredMode = getPreferredVoiceInputMode();
    state.voiceInputMode = preferredMode;
    if (preferredMode === "backend-host") {
      await startBackendVoiceCapture();
      return;
    }

    if (!state.recognition) {
      showToast("Microphone not available", "Microphone not available", true);
      state.voiceInputMode = "unavailable";
      syncVoiceButtons();
      return;
    }

    state.recognition.lang = state.language === "urdu" ? "ur-PK" : "en-US";
    try {
      state.recognition.start();
    } catch (error) {
      resetVoiceCaptureState({ keepErrorState: true });
      showToast("Voice input issue", error.message || "Speech recognition could not start.", true);
    }
  }

  function selectSpeechVoice(gender, language) {
    const voices = window.speechSynthesis.getVoices();

    if (voices.length === 0) {
      window.speechSynthesis.onvoiceschanged = () => selectSpeechVoice(gender, language);
      return null;
    }

    let selectedVoice = null;
    const normalizedLanguage = String(language || "en-US").toLowerCase();
    const normalizedGender = String(gender || "female").toLowerCase();

    if (normalizedGender === "male") {
      selectedVoice = voices.find((voice) => {
        const name = voice.name.toLowerCase();
        return (
          name.includes("male") ||
          name.includes("david") ||
          name.includes("mark") ||
          name.includes("james") ||
          (voice.lang.toLowerCase().startsWith(normalizedLanguage) && !name.includes("female"))
        );
      });
    } else {
      selectedVoice = voices.find((voice) => {
        const name = voice.name.toLowerCase();
        return (
          name.includes("female") ||
          name.includes("zira") ||
          name.includes("susan") ||
          name.includes("hazel") ||
          voice.lang.toLowerCase().startsWith(normalizedLanguage)
        );
      });
    }

    if (!selectedVoice) {
      selectedVoice = voices.find((voice) => voice.lang.toLowerCase().startsWith(normalizedLanguage)) || voices[0];
    }

    return selectedVoice || null;
  }

  function speakText(text) {
    if (!state.speechSupported) {
      showToast("Speech unavailable", "This browser cannot read responses aloud.", true);
      return;
    }

    stopSpeaking();

    const language = state.profile?.language || (state.language === "urdu" ? "ur-PK" : "en-US");
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = Number(state.profile?.voice_rate || state.settings.voiceRate || 1);
    utterance.pitch = Number(state.profile?.voice_pitch || 1);
    utterance.volume = Number(state.profile?.voice_volume ?? 1);
    utterance.lang = language;
    const selectedVoice = selectSpeechVoice(state.profile?.voice_gender || "female", language);
    if (selectedVoice) {
      utterance.voice = selectedVoice;
    }

    utterance.addEventListener("start", () => {
      state.speaking = true;
      setSystemState("speaking");
      syncVoiceButtons();
    });

    utterance.addEventListener("end", () => {
      state.speaking = false;
      syncVoiceButtons();
      setSystemState("idle");
    });

    utterance.addEventListener("error", () => {
      state.speaking = false;
      syncVoiceButtons();
      setSystemState("error");
    });

    window.speechSynthesis.speak(utterance);
  }

  function stopSpeaking() {
    if (!state.speechSupported) {
      return;
    }

    window.speechSynthesis.cancel();
    state.speaking = false;
    syncVoiceButtons();
    if (!state.listening) {
      setSystemState("idle");
    }
  }

  function syncVoiceButtons() {
    if (state.listening) {
      el.voiceButton.disabled = false;
      el.voiceToggle.disabled = false;
      el.voiceButton.textContent = state.voiceActiveSource === "backend" ? "Stop host mic" : "Stop mic";
      el.voiceToggle.textContent = "Listening";
      applyListeningVisualState(true);
      return;
    }

    applyListeningVisualState(false);

    if (state.voiceInputMode === "backend-host") {
      el.voiceButton.disabled = false;
      el.voiceToggle.disabled = false;
      el.voiceButton.textContent = "Start host mic";
      el.voiceButton.title = "Uses backend STT on this machine.";
      el.voiceToggle.textContent = state.speaking ? "Speaking" : "Host mic";
      return;
    }

    if (state.voiceInputMode === "browser-only") {
      el.voiceButton.disabled = false;
      el.voiceToggle.disabled = false;
      el.voiceButton.textContent = "Start mic";
      el.voiceButton.title = "Browser-only mode.";
      el.voiceToggle.textContent = state.speaking ? "Speaking" : "Browser-only";
      return;
    }

    el.voiceButton.disabled = true;
    el.voiceToggle.disabled = true;
    el.voiceButton.textContent = "Microphone not available";
    el.voiceButton.title = "Microphone not available";
    el.voiceToggle.textContent = "Mic unavailable";
  }

  function renderConfirmationStatus() {
    const items = state.confirmationStatus?.critical_actions || [];
    el.confirmationTriggers.innerHTML = items.length
      ? items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
      : renderEmptyState("No confirmation data", "Critical action protection status will appear here.", true);
  }

  async function previewVoice() {
    try {
      await fetchJson("/api/voice/speak", {
        method: "POST",
        body: JSON.stringify({ text: "AURA online and ready." }),
      });
      speakText("AURA online and ready.");
    } catch (error) {
      showToast("Voice preview failed", error.message, true);
    }
  }

  async function setConfirmationCode() {
    const code = el.settingsConfirmCode.value.trim();
    const confirmCode = el.settingsConfirmCodeRepeat.value.trim();
    if (!code || !confirmCode) {
      showToast("Confirmation code missing", "Enter the code twice before saving it.", true);
      return;
    }
    try {
      await fetchJson("/api/confirmation-code/set", {
        method: "POST",
        body: JSON.stringify({ code, confirm_code: confirmCode }),
      });
      el.settingsConfirmCode.value = "";
      el.settingsConfirmCodeRepeat.value = "";
      await loadConfirmationStatus();
      showToast("Confirmation code saved", "Critical actions now require your confirmation code.");
    } catch (error) {
      showToast("Could not save confirmation code", error.message, true);
    }
  }

  async function changeConfirmationCode() {
    const oldCode = el.settingsOldConfirmCode.value.trim();
    const newCode = el.settingsNewConfirmCode.value.trim();
    const confirmCode = el.settingsNewConfirmCodeRepeat.value.trim();
    if (!oldCode || !newCode || !confirmCode) {
      showToast("Change code incomplete", "Fill all confirmation code fields before updating.", true);
      return;
    }
    try {
      await fetchJson("/api/confirmation-code/change", {
        method: "POST",
        body: JSON.stringify({ old_code: oldCode, new_code: newCode, confirm_code: confirmCode }),
      });
      el.settingsOldConfirmCode.value = "";
      el.settingsNewConfirmCode.value = "";
      el.settingsNewConfirmCodeRepeat.value = "";
      await loadConfirmationStatus();
      showToast("Confirmation code updated", "AURA will use the new code for critical actions.");
    } catch (error) {
      showToast("Could not update confirmation code", error.message, true);
    }
  }

  function openAdminPanel() {
    if (!state.user?.admin) {
      showToast("Admin only", "Only the owner or an approved admin can open the admin panel.", true);
      return;
    }
    window.location.href = "/admin";
  }

  function handleOrbClick() {
    handleVoiceToggle();
  }

  function handleOrbDoubleClick(event) {
    event.preventDefault();
    stopSpeaking();
  }

  function handleOrbContextMenu(event) {
    event.preventDefault();
    el.orbQuickMenu.hidden = !el.orbQuickMenu.hidden;
  }

  function handleOrbMenuClick(event) {
    const button = event.target.closest("[data-orb-action]");
    if (!button) {
      return;
    }

    const action = button.dataset.orbAction;
    el.orbQuickMenu.hidden = true;

    if (action === "new-chat") {
      handleClearHistoryClick();
      return;
    }

    if (action === "lock") {
      lockAura();
      return;
    }

    if (action === "settings") {
      switchView("settings");
      return;
    }

    if (action === "switch-mode") {
      const order = ["minimal", "smart", "jarvis", "developer", "autonomous"];
      const nextMode = order[(order.indexOf(state.mode) + 1) % order.length];
      setMode(nextMode);
    }
  }

  function handleDocumentClick(event) {
    if (!event.target.closest("#orbQuickMenu") && !event.target.closest("#heroOrb")) {
      el.orbQuickMenu.hidden = true;
    }
  }

  async function lockAura() {
    try {
      await fetchJson("/api/security/lock", {
        method: "POST",
        body: JSON.stringify({ resource_id: "session", owner: state.user?.username || "owner" }),
      });
      setSystemState("locked");
      showToast("Session secured", "AURA locked the current session surface.");
    } catch (error) {
      showToast("Lock failed", error.message, true);
    }
  }

  function renderMemory() {
    const memory = state.memoryInsights;
    const profile = memory?.profile || {};
    const preferences = memory?.preferences || {};
    const interests = (memory?.interests && memory.interests.length ? memory.interests : deriveInterestFallback()).slice(0, 8);
    const facts = dedupeArray([
      ...(memory?.learned_facts || []),
      profile.city ? `Lives in ${profile.city}` : "",
      profile.age ? `Age ${profile.age}` : "",
    ]).slice(0, 8);
    const topIntents = memory?.top_intents || [];
    const insights = dedupeArray(memory?.insights || []);

    el.memoryGreetingPreview.textContent = memory?.greeting_preview || "Hello. AURA is ready.";
    el.memoryStatusNote.textContent =
      memory?.sources ? `Backed by ${memory.sources.explicit_memory} and ${memory.sources.learning}.` : "Memory surfaces are waiting for connected data.";

    el.memoryPreferenceList.innerHTML = renderChipList(
      Object.entries(preferences).map(([key, value]) => `${key}: ${value}`),
      "No explicit preferences stored yet.",
    );

    el.memoryFactList.innerHTML = renderStackList(facts, "No learned facts are available yet.");
    el.memoryInterestList.innerHTML = renderChipList(interests, "AURA will surface recurring interests after more interaction.");
    el.memoryTopIntents.innerHTML = renderBarList(topIntents, "AURA has not built an intent profile yet.");
    el.memoryInsights.innerHTML = renderStackList(insights, "Adaptive observations will appear once more interactions accumulate.");
  }

  function renderIntelligence() {
    const latest = state.lastResult;
    const intelligence = state.intelligenceInsights;
    const recentFailure = intelligence?.recent_failures?.[intelligence.recent_failures.length - 1];
    const recentLowConfidence = intelligence?.recent_low_confidence?.[intelligence.recent_low_confidence.length - 1];

    el.intelIntent.textContent = latest?.detected_intent || "general";
    el.intelConfidence.textContent = getConfidenceText(latest?.confidence);
    el.intelAgent.textContent = getPrimaryAgentLabel();
    el.intelExecutionMode.textContent = latest?.execution_mode || "idle";
    el.intelReasoningStatus.textContent = intelligence?.reasoning_status || state.systemStatus?.reasoning || "available";
    el.intelPermissionStatus.textContent = latest?.permission?.status || formatPermissionRules(intelligence?.permissions?.action_rules) || "Approved";
    el.intelRecoveryNote.textContent = recentLowConfidence
      ? `Recovered from "${recentLowConfidence.command}" at ${getConfidenceText(recentLowConfidence.confidence)} confidence.`
      : "No recent low-confidence recovery needed.";
    el.intelImprovementSummary.textContent = recentFailure
      ? `Latest friction: ${recentFailure.reason}`
      : "No recent runtime failures logged.";

    renderSubsystems();
    renderCapabilityGrid();
    updateHeaderMetrics();
  }

  function renderSubsystems() {
    const subsystems = state.systemStatus?.subsystems || {};
    const html = Object.entries(subsystems)
      .map(([name, info]) => {
        const badges = [
          `<span class="chip ${info.status === "degraded" ? "chip--warning" : "chip--success"}">${escapeHtml(info.status || "available")}</span>`,
          info.mode ? `<span class="chip chip--mode">${escapeHtml(info.mode)}</span>` : "",
        ].join("");
        return `
          <article class="subsystem-card">
            <strong>${escapeHtml(name)}</strong>
            <div class="subsystem-card__meta">${badges}</div>
          </article>
        `;
      })
      .join("");

    const empty = renderEmptyState("No subsystem data yet", "System status will appear here once the backend responds.");
    el.statusSubsystems.innerHTML = html || empty;
    el.railSystemSummary.innerHTML = html || empty;
  }

  function renderCapabilityGrid() {
    const cards = state.agents
      .map((agent) => {
        const modeClass =
          agent.capability_mode === "real" ? "chip--success" : agent.capability_mode === "placeholder" ? "chip--warning" : "chip--agent";
        return `
          <article class="capability-card">
            <div class="item-card__top">
              <div>
                <p class="item-card__title">${escapeHtml(agent.name)}</p>
                <div class="capability-card__meta">
                  <span class="chip ${modeClass}">${escapeHtml(agent.capability_mode)}</span>
                  <span class="chip chip--mode">${escapeHtml(agent.trust_level)}</span>
                  <span class="chip">${escapeHtml(agent.category)}</span>
                </div>
              </div>
              <span class="chip">${escapeHtml(agent.icon || "AI")}</span>
            </div>
            <p class="support-copy">${escapeHtml(agent.description)}</p>
            <p class="item-card__meta">${escapeHtml(agent.integration_path || agent.backend || "")}</p>
          </article>
        `;
      })
      .join("");

    el.capabilityGrid.innerHTML = cards || renderEmptyState("No registered agents", "Agent cards will appear once the registry is available.");
  }

  function renderAutonomy() {
    const latest = state.lastResult;
    const plan = latest?.plan || [];
    const usedAgents = dedupeArray([...(latest?.used_agents || []), ...((latest?.orchestration?.execution_order) || [])]);
    const isFailure = latest?.execution_mode === "permission_blocked" || latest?.execution_mode === "error" || latest?.intent === "error";
    const completed = plan.length && !isFailure ? plan.length : 0;
    const failed = isFailure ? Math.max(1, plan.length || 1) : 0;
    const retries = latest?.response ? (latest.response.match(/retry/gi) || []).length : 0;
    const progress = plan.length ? (isFailure ? 12 : 100) : 0;

    el.autonomyHeadline.textContent = plan.length
      ? `${plan.length} planned step${plan.length === 1 ? "" : "s"} in the latest observed flow`
      : "No active plan yet";
    el.autonomyProgressBar.style.width = `${progress}%`;
    el.autonomyProgressLabel.textContent = plan.length
      ? isFailure
        ? "AURA surfaced a blocked or failed path instead of hiding it."
        : "Latest visible plan completed from the backend's current metadata."
      : "Progress will appear when AURA generates or executes a plan.";
    el.autonomyTelemetryNote.textContent = latest
      ? "Detailed step completion is inferred only from the backend metadata currently exposed."
      : "Telemetry is honest: this view only shows executor data that the backend currently exposes.";

    el.autonomyTools.innerHTML = renderChipList(usedAgents, "No tools or agents observed yet.");
    el.autonomyCompleted.textContent = String(completed);
    el.autonomyFailed.textContent = String(failed);
    el.autonomyRetries.textContent = String(retries);
    el.navAutonomyCount.textContent = String(plan.length);

    if (!plan.length) {
      el.autonomyTimeline.innerHTML = renderEmptyState("No recent plan", "Send a multi-step or tool-using request to populate the autonomy timeline.");
      return;
    }

    el.autonomyTimeline.innerHTML = plan
      .map((step, index) => {
        const statusClass = isFailure ? (index === 0 ? "is-error" : "is-pending") : "is-complete";
        const caption = isFailure
          ? index === 0
            ? "Blocked or failed"
            : "Planned but not confirmed"
          : "Observed in latest result";
        return `
          <article class="timeline__item ${statusClass}">
            <span class="timeline__marker" aria-hidden="true"></span>
            <div class="timeline__content">
              <span class="timeline__eyebrow">Step ${index + 1}</span>
              <strong>${escapeHtml(step)}</strong>
              <span class="support-copy">${escapeHtml(caption)}</span>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderTasks() {
    const pendingTasks = state.tasks.filter((item) => item.status !== "completed");
    const completedTasks = state.tasks.filter((item) => item.status === "completed");
    const activeReminders = state.reminders.filter((item) => item.status !== "completed");
    const completedReminders = state.reminders.filter((item) => item.status === "completed");

    el.taskSummaryPending.textContent = String(pendingTasks.length);
    el.taskSummaryCompleted.textContent = String(completedTasks.length);
    el.reminderSummaryActive.textContent = String(activeReminders.length);
    el.reminderSummaryCompleted.textContent = String(completedReminders.length);
    el.navTaskCount.textContent = String(pendingTasks.length + activeReminders.length);

    el.taskList.innerHTML = renderTaskCards(pendingTasks, false, "No active tasks", "Add a task above and AURA will track it locally.");
    el.completedTaskList.innerHTML = renderTaskCards(completedTasks, true, "No completed tasks", "Completed tasks will stay visible here.");
    el.reminderList.innerHTML = renderReminderCards(activeReminders, false, "No active reminders", "Create a reminder to keep timed follow-through visible.");
    el.completedReminderList.innerHTML = renderReminderCards(completedReminders, true, "No completed reminders", "Resolved reminders will stay visible here.");
  }

  async function handleTaskSubmit(event) {
    event.preventDefault();
    const text = el.taskText.value.trim();
    if (!text) {
      showToast("Task needs text", "Write the task first so AURA can store it.", true);
      return;
    }

    try {
      const isEditing = Boolean(state.taskEditingId);
      if (state.taskEditingId) {
        await fetchJson(`/api/tasks/${state.taskEditingId}`, {
          method: "PATCH",
          body: JSON.stringify({
            text,
            priority: el.taskPriority.value,
            due_date: el.taskDueDate.value || null,
          }),
        });
      } else {
        await fetchJson("/api/tasks", {
          method: "POST",
          body: JSON.stringify({
            text,
            priority: el.taskPriority.value,
            due_date: el.taskDueDate.value || null,
          }),
        });
      }
      resetTaskEditor();
      await loadTasks();
      showToast(isEditing ? "Task updated" : "Task stored", isEditing ? "AURA updated the task in local storage." : "AURA added the task to real local storage.");
    } catch (error) {
      showToast("Could not save task", error.message, true);
    }
  }

  async function handleReminderSubmit(event) {
    event.preventDefault();
    const text = el.reminderText.value.trim();
    if (!text) {
      showToast("Reminder needs text", "Write the reminder first so AURA can save it.", true);
      return;
    }

    try {
      const isEditing = Boolean(state.reminderEditingId);
      if (state.reminderEditingId) {
        await fetchJson(`/api/reminders/${state.reminderEditingId}`, {
          method: "PATCH",
          body: JSON.stringify({
            text,
            date: el.reminderDate.value || null,
            time: el.reminderTime.value || null,
          }),
        });
      } else {
        await fetchJson("/api/reminders", {
          method: "POST",
          body: JSON.stringify({
            text,
            date: el.reminderDate.value || null,
            time: el.reminderTime.value || null,
          }),
        });
      }
      resetReminderEditor();
      await loadReminders();
      showToast(isEditing ? "Reminder updated" : "Reminder stored", isEditing ? "AURA updated the reminder in local storage." : "AURA added the reminder to real local storage.");
    } catch (error) {
      showToast("Could not save reminder", error.message, true);
    }
  }

  async function handleTaskListClick(event) {
    const button = event.target.closest("[data-task-action]");
    if (!button) {
      return;
    }

    const id = Number(button.dataset.taskId);
    const task = state.tasks.find((entry) => Number(entry.id) === id);
    if (!task) {
      return;
    }

    try {
      if (button.dataset.taskAction === "toggle") {
        await fetchJson(`/api/tasks/${id}`, {
          method: "PATCH",
          body: JSON.stringify({ done: task.status !== "completed" }),
        });
      } else if (button.dataset.taskAction === "edit") {
        state.taskEditingId = id;
        el.taskText.value = task.task || "";
        el.taskPriority.value = task.priority || "medium";
        el.taskDueDate.value = task.due_date || "";
        el.taskSubmitButton.textContent = "Save task";
        el.taskCancelEditButton.hidden = false;
        el.taskText.focus();
        el.taskText.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      } else if (button.dataset.taskAction === "delete") {
        if (!window.confirm("Delete this task from AURA storage?")) {
          return;
        }
        await fetchJson(`/api/tasks/${id}`, { method: "DELETE" });
      }

      if (state.taskEditingId === id) {
        resetTaskEditor();
      }
      await loadTasks();
    } catch (error) {
      showToast("Task update failed", error.message, true);
    }
  }

  async function handleReminderListClick(event) {
    const button = event.target.closest("[data-reminder-action]");
    if (!button) {
      return;
    }

    const id = Number(button.dataset.reminderId);
    const reminder = state.reminders.find((entry) => Number(entry.id) === id);
    if (!reminder) {
      return;
    }

    try {
      if (button.dataset.reminderAction === "toggle") {
        await fetchJson(`/api/reminders/${id}`, {
          method: "PATCH",
          body: JSON.stringify({ status: reminder.status === "completed" ? "active" : "completed" }),
        });
      } else if (button.dataset.reminderAction === "edit") {
        state.reminderEditingId = id;
        el.reminderText.value = reminder.text || "";
        el.reminderDate.value = reminder.date || "";
        el.reminderTime.value = reminder.time || "";
        el.reminderSubmitButton.textContent = "Save reminder";
        el.reminderCancelEditButton.hidden = false;
        el.reminderText.focus();
        el.reminderText.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      } else if (button.dataset.reminderAction === "delete") {
        if (!window.confirm("Delete this reminder from AURA storage?")) {
          return;
        }
        await fetchJson(`/api/reminders/${id}`, { method: "DELETE" });
      }

      if (state.reminderEditingId === id) {
        resetReminderEditor();
      }
      await loadReminders();
    } catch (error) {
      showToast("Reminder update failed", error.message, true);
    }
  }

  function resetTaskEditor() {
    state.taskEditingId = null;
    el.taskForm.reset();
    el.taskPriority.value = "medium";
    el.taskSubmitButton.textContent = "Add task";
    el.taskCancelEditButton.hidden = true;
  }

  function resetReminderEditor() {
    state.reminderEditingId = null;
    el.reminderForm.reset();
    el.reminderSubmitButton.textContent = "Add reminder";
    el.reminderCancelEditButton.hidden = true;
  }

  function renderHistory() {
    const showAdvancedMeta = state.mode === "developer" || state.mode === "autonomous" || state.settings.debugDetails;
    const records = buildHistoryTurns(state.history)
      .filter((entry) => {
        if (!state.historyFilter) {
          return true;
        }
        const haystack = [entry.user, entry.aura, entry.intent, entry.agent_used, entry.mode].join(" ").toLowerCase();
        return haystack.includes(state.historyFilter);
      });

    el.historyMetaHint.textContent = showAdvancedMeta
      ? "Advanced mode is showing intent, agent, and execution hints where metadata is available."
      : "Switch to Developer or Autonomous mode to see richer routing metadata.";

    if (!records.length) {
      el.historyList.innerHTML = renderEmptyState("No conversation history", "History cards will appear here once AURA has logged interactions.");
      return;
    }

    el.historyList.innerHTML = records
      .slice()
      .reverse()
      .map((entry) => {
        const metaChips = showAdvancedMeta
          ? `
            <div class="chip-cloud">
              <span class="chip chip--mode">${escapeHtml(entry.intent || "general")}</span>
              <span class="chip chip--agent">${escapeHtml(entry.agent_used || "AURA")}</span>
              ${entry.mode ? `<span class="chip">${escapeHtml(entry.mode)}</span>` : ""}
            </div>
          `
          : "";

        return `
          <article class="history-card">
            <div class="history-card__head">
              <div class="history-card__meta">
                <span>${escapeHtml(formatTimestamp(entry.time || ""))}</span>
                <span>${escapeHtml(shortSessionId(entry.session_id || state.currentSessionId))}</span>
              </div>
            </div>
            <p class="history-card__input"><strong>You:</strong> ${escapeHtml(entry.user || "")}</p>
            <p class="history-card__response"><strong>AURA:</strong> ${escapeHtml(entry.aura || "")}</p>
            ${metaChips}
          </article>
        `;
      })
      .join("");
  }

  function renderSessionList() {
    renderCurrentSessionBadge();

    if (!state.sessions.length) {
      el.historySessionList.innerHTML = renderEmptyState(
        "No saved sessions yet",
        "AURA will list local SQLite sessions here after you chat.",
        true,
      );
      return;
    }

    el.historySessionList.innerHTML = state.sessions
      .map((session) => {
        const isActive = session.session_id === state.currentSessionId;
        return `
          <button class="session-card ${isActive ? "is-active" : ""}" type="button" data-session-id="${escapeAttribute(session.session_id)}">
            <strong>${escapeHtml(shortSessionId(session.session_id))}</strong>
            <span>${escapeHtml(formatTimestamp(session.last_timestamp || session.started_at || ""))}</span>
            <small>${escapeHtml(`${session.message_count || 0} stored messages`)}</small>
          </button>
        `;
      })
      .join("");
  }

  function renderCurrentSessionBadge() {
    if (!el.historyCurrentSession) {
      return;
    }

    el.historyCurrentSession.textContent = `Current: ${shortSessionId(state.currentSessionId)}`;
  }

  function buildHistoryTurns(messages) {
    const turns = [];
    let pendingUser = null;

    messages.forEach((entry) => {
      if (entry.role === "user") {
        if (pendingUser) {
          turns.push({
            session_id: pendingUser.session_id,
            user: pendingUser.message,
            aura: "",
            time: pendingUser.timestamp,
            intent: pendingUser.intent || "input",
            agent_used: "",
            mode: pendingUser.mode || "hybrid",
          });
        }
        pendingUser = entry;
        return;
      }

      if (pendingUser) {
        turns.push({
          session_id: entry.session_id || pendingUser.session_id,
          user: pendingUser.message,
          aura: entry.message,
          time: entry.timestamp || pendingUser.timestamp,
          intent: entry.intent || pendingUser.intent || "general",
          agent_used: entry.agent_used || "AURA",
          mode: entry.mode || pendingUser.mode || "hybrid",
        });
        pendingUser = null;
        return;
      }

      turns.push({
        session_id: entry.session_id,
        user: "",
        aura: entry.message,
        time: entry.timestamp,
        intent: entry.intent || "general",
        agent_used: entry.agent_used || "AURA",
        mode: entry.mode || "hybrid",
      });
    });

    if (pendingUser) {
      turns.push({
        session_id: pendingUser.session_id,
        user: pendingUser.message,
        aura: "",
        time: pendingUser.timestamp,
        intent: pendingUser.intent || "input",
        agent_used: "",
        mode: pendingUser.mode || "hybrid",
      });
    }

    return turns;
  }

  function renderRail() {
    const latest = state.lastResult;
    const permissionStatus =
      latest?.permission?.status ||
      formatPermissionRules(state.intelligenceInsights?.permissions?.action_rules) ||
      "Approved";
    const memoryFacts = dedupeArray([
      ...(state.memoryInsights?.learned_facts || []).slice(0, 4),
      state.memoryInsights?.profile?.city ? `City: ${state.memoryInsights.profile.city}` : "",
      state.memoryInsights?.profile?.age ? `Age: ${state.memoryInsights.profile.age}` : "",
    ]);
    const plan = latest?.plan || [];
    const executionEntries = dedupeArray([
      latest?.execution_mode ? `Execution mode: ${latest.execution_mode}` : "",
      ...(latest?.used_agents || []).map((agent) => `Agent: ${agent}`),
    ]);
    const improvementEntries = dedupeArray([
      ...(state.intelligenceInsights?.recent_failures || []).slice(-2).map((item) => item.reason),
      ...(state.intelligenceInsights?.recent_low_confidence || []).slice(-2).map((item) => `Low confidence: ${item.command}`),
    ]);

    el.railPermission.textContent = permissionStatus;
    el.railGreeting.textContent = state.memoryInsights?.greeting_preview || "Waiting for your next request";
    el.railMemoryFacts.innerHTML = renderStackList(memoryFacts, "No explicit memory facts are visible yet.");
    el.railPlanList.innerHTML = renderMiniTimeline(plan, "No recent plan", "Latest planned steps will appear here.");
    el.railExecutionList.innerHTML = renderMiniTimeline(executionEntries, "No execution signals", "Execution markers will appear after AURA handles a request.");
    el.railImprovementList.innerHTML = renderStackList(improvementEntries, "No recent friction was logged.");
  }

  function setSystemState(nextState) {
    const meta = ORB_STATE_META[nextState] || ORB_STATE_META.idle;
    state.systemState = nextState;
    el.heroOrb.dataset.state = nextState;
    el.railOrb.dataset.state = nextState;
    el.heroStateText.textContent = meta.title;
    el.heroStateHint.textContent = meta.hint;
    el.railState.textContent = meta.title;
    el.railStateHint.textContent = meta.hint;
    el.topbarStateText.textContent = meta.title;
    el.topbarStateDot.style.background = meta.color;
    el.topbarStateDot.style.boxShadow = `0 0 14px ${meta.color}`;
  }

  function getPrimaryAgentLabel() {
    return getAgentNameFromResult(state.lastResult) || "General";
  }

  function getAgentNameFromResult(result) {
    if (!result) {
      return "General";
    }

    const firstCapability = result.agent_capabilities?.[0]?.name;
    return firstCapability || result.used_agents?.[0] || result.orchestration?.primary_agent || "General";
  }

  function getStreamAgentLabel(payload, streamMeta) {
    return payload.agent_used || payload.agent || streamMeta?.agent_used || streamMeta?.agent || "AURA";
  }

  function formatTimestamp(value) {
    if (!value) {
      return "";
    }

    const normalized = typeof value === "string" ? value.replace(" ", "T") : value;
    const parsed = new Date(normalized);
    if (Number.isNaN(parsed.getTime())) {
      return String(value);
    }

    return parsed.toLocaleString([], {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function getConfidenceText(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "--";
    }
    return `${Math.round(Number(value) * 100)}%`;
  }

  function formatPermissionRules(actionRules) {
    if (!actionRules) {
      return "";
    }
    const entries = Object.entries(actionRules);
    if (!entries.length) {
      return "";
    }
    return entries.map(([level, action]) => `${level}:${action}`).join(" ");
  }

  function renderChipList(items, emptyText) {
    const values = dedupeArray(items).filter(Boolean);
    if (!values.length) {
      return renderEmptyState("No items yet", emptyText, true);
    }
    return values.map((value) => `<span class="chip">${escapeHtml(String(value))}</span>`).join("");
  }

  function renderStackList(items, emptyText) {
    const values = dedupeArray(items).filter(Boolean);
    if (!values.length) {
      return renderEmptyState("Nothing to show yet", emptyText, true);
    }
    return values.map((value) => `<li>${escapeHtml(String(value))}</li>`).join("");
  }

  function renderBarList(items, emptyText) {
    if (!items.length) {
      return renderEmptyState("No intent profile yet", emptyText, true);
    }

    const maxCount = Math.max(...items.map((item) => Number(item.count) || 0), 1);
    return items
      .map((item) => {
        const width = Math.max(8, Math.round(((Number(item.count) || 0) / maxCount) * 100));
        return `
          <li class="bar-list__row">
            <div class="bar-list__head">
              <strong>${escapeHtml(item.intent)}</strong>
              <span>${escapeHtml(String(item.count))}</span>
            </div>
            <div class="bar-list__track"><div class="bar-list__bar" style="width:${width}%"></div></div>
          </li>
        `;
      })
      .join("");
  }

  function renderMiniTimeline(items, title, body) {
    const values = items.filter(Boolean);
    if (!values.length) {
      return renderEmptyState(title, body, true);
    }

    return values
      .map(
        (item, index) => `
          <article class="mini-timeline__item is-complete">
            <span class="mini-timeline__marker" aria-hidden="true"></span>
            <div class="mini-timeline__content">
              <strong>${escapeHtml(`Signal ${index + 1}`)}</strong>
              <span class="support-copy">${escapeHtml(String(item))}</span>
            </div>
          </article>
        `,
      )
      .join("");
  }

  function renderTaskCards(items, isCompleted, emptyTitle, emptyBody) {
    if (!items.length) {
      return renderEmptyState(emptyTitle, emptyBody, true);
    }

    return items
      .map((item) => `
        <article class="item-card">
          <div class="item-card__top">
            <div>
              <p class="item-card__title">${escapeHtml(item.task || "")}</p>
              <div class="item-card__meta">
                <span>${escapeHtml((item.priority || "medium").toUpperCase())}</span>
                ${item.due_date ? `<span>${escapeHtml(item.due_date)}</span>` : ""}
                <span>${escapeHtml(item.status || "pending")}</span>
              </div>
            </div>
          </div>
          <div class="item-card__actions">
            <button class="item-card__button" type="button" data-task-action="toggle" data-task-id="${item.id}">${isCompleted ? "Restore" : "Complete"}</button>
            <button class="item-card__button" type="button" data-task-action="edit" data-task-id="${item.id}">Edit</button>
            <button class="item-card__button" type="button" data-task-action="delete" data-task-id="${item.id}">Delete</button>
          </div>
        </article>
      `)
      .join("");
  }

  function renderReminderCards(items, isCompleted, emptyTitle, emptyBody) {
    if (!items.length) {
      return renderEmptyState(emptyTitle, emptyBody, true);
    }

    return items
      .map((item) => `
        <article class="item-card">
          <div class="item-card__top">
            <div>
              <p class="item-card__title">${escapeHtml(item.text || "")}</p>
              <div class="item-card__meta">
                ${item.date ? `<span>${escapeHtml(item.date)}</span>` : ""}
                ${item.time ? `<span>${escapeHtml(item.time)}</span>` : ""}
                <span>${escapeHtml(item.status || "active")}</span>
              </div>
            </div>
          </div>
          <div class="item-card__actions">
            <button class="item-card__button" type="button" data-reminder-action="toggle" data-reminder-id="${item.id}">${isCompleted ? "Restore" : "Complete"}</button>
            <button class="item-card__button" type="button" data-reminder-action="edit" data-reminder-id="${item.id}">Edit</button>
            <button class="item-card__button" type="button" data-reminder-action="delete" data-reminder-id="${item.id}">Delete</button>
          </div>
        </article>
      `)
      .join("");
  }

  function renderEmptyState(title, body, compact = false) {
    return `
      <div class="empty-state ${compact ? "empty-state--compact" : ""}">
        <span class="empty-state__badge">AURA</span>
        <h4>${escapeHtml(title)}</h4>
        <p>${escapeHtml(body)}</p>
      </div>
    `;
  }

  function findHistoryMeta(entry) {
    return state.sessionMeta.find((item) => item.user === entry.user && item.aura === entry.aura)?.meta || null;
  }

  function deriveInterestFallback() {
    const items = state.memoryInsights?.top_intents || [];
    return items
      .map((item) => item.intent)
      .filter((intent) => !["general", "greeting", "memory"].includes(intent));
  }

  function dedupeArray(items) {
    return [...new Set(items.filter(Boolean))];
  }

  function formatMessageText(text) {
    return escapeHtml(text).replace(/\n/g, "<br>");
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function escapeAttribute(value) {
    return escapeHtml(value).replaceAll("`", "&#96;");
  }

  function showToast(title, body, isError = false) {
    const toast = document.createElement("div");
    toast.className = `toast ${isError ? "toast--error" : ""}`;
    toast.innerHTML = `<strong>${escapeHtml(title)}</strong><p>${escapeHtml(body)}</p>`;
    el.toastStack.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3600);
  }

  async function logout() {
    try {
      await fetchJson("/api/logout", { method: "POST" });
    } catch (error) {
      // Redirect anyway to avoid leaving the UI stranded.
    }
    window.location.href = "/login";
  }

  window.sendMessage = sendMessage;
})();
