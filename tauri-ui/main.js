// tauri-ui/main.js
// ------------------------------------------------------------
// BOT-MMORPG-AI (Tauri UI) - UPDATED v0.1.9
// - Fixed Settings: Loads/Saves API Keys correctly via Rust
// - Adds ModelHub commands wiring
// - Adds AI Chat wiring
// ------------------------------------------------------------

// State & Tauri Globals
const invoke = window.__TAURI__ ? window.__TAURI__.invoke : null;
const listen = window.__TAURI__ ? window.__TAURI__.event.listen : null;

// Global State
let isRecording = false;
let isBotRunning = false;

// ModelHub UI State
const DEFAULT_GAME_ID = "genshin_impact";
let modelhubAvailable = false;
let selectedGameId = DEFAULT_GAME_ID;
let selectedDatasetId = "";
let selectedBuiltinModelPath = "";
let selectedModelRegistryId = "";
let selectedLocalModelPath = "";

// Cache catalog payload
let currentCatalog = {
  builtin_models: [],
  datasets: [],
  models: [],
  local_models: [],
  active: null,
};

// --- TAB NAVIGATION ---
window.showTab = function (tabId) {
  const titles = {
    dashboard: "Dashboard",
    teach: "Teach Mode (Data Collection)",
    train: "Neural Network Training",
    run: "Run Bot",
    strategist: "AI Strategist",
    models: "ModelHub",
  };

  const pageTitle = document.getElementById("page-title");
  if (pageTitle) pageTitle.textContent = titles[tabId] || "Dashboard";

  document.querySelectorAll(".tab-content").forEach((el) => {
    el.classList.remove("active");
    el.style.display = "";
  });

  const selectedTab = document.getElementById("tab-" + tabId);
  if (selectedTab) {
    selectedTab.classList.add("active");
    if (tabId === "teach" || tabId === "train") selectedTab.style.display = "flex";
    else selectedTab.style.display = "block";
  }

  document.querySelectorAll(".nav-btn").forEach((el) => el.classList.remove("active"));
  const selectedBtn =
    document.getElementById("btn-" + tabId) || document.querySelector(`button[data-tab="${tabId}"]`);
  if (selectedBtn) selectedBtn.classList.add("active");
};

// --- LOGGING ---
function logToTerminal(msg, type = "info") {
  const terminal = document.getElementById("terminal");
  if (!terminal) return;

  const timestamp = new Date().toLocaleTimeString();
  const entry = document.createElement("div");
  entry.className = `log-entry log-${type}`;
  entry.innerHTML = `<span class="log-time">[${timestamp}]</span> ${msg}`;

  terminal.appendChild(entry);
  terminal.scrollTop = terminal.scrollHeight;

  // Keep log size manageable
  const entries = terminal.querySelectorAll(".log-entry");
  if (entries.length > 200) entries[0].remove();
}

// Backward-compat global hook
window.update_terminal = function (line) {
  logToTerminal(line, "info");

  // Parse progress for Training
  if (line.includes("Epoch")) {
    const match = line.match(/Epoch (\d+)\/(\d+)/);
    if (match) {
      const current = parseInt(match[1], 10);
      const total = parseInt(match[2], 10);
      const percent = Math.round((current / total) * 100);

      const progressBar = document.getElementById("progress-bar");
      const pctDisplay = document.getElementById("train-pct");

      if (progressBar) progressBar.style.width = percent + "%";
      if (pctDisplay) pctDisplay.textContent = percent + "%";
    }
  }
};

// --- BACKEND STATUS ---
function updateBackendStatus(status, message) {
  const statusText = document.getElementById("backend-status");
  const statusBadge = document.getElementById("backend-status-badge");
  const footerText = document.getElementById("backend-status-text");

  if (statusText) statusText.textContent = message;
  if (statusBadge) statusBadge.textContent = status;
  if (footerText) footerText.textContent = status === "Running" ? "System Online" : "System Offline";

  const dot = document.querySelector(".status-dot");
  if (dot) dot.style.backgroundColor = status === "Running" ? "var(--success)" : "var(--accent)";
}

// ============================================================
// ✅ NEW: SETTINGS MANAGEMENT (Fixes API Key Error)
// ============================================================

// 1. Load Settings from Rust -> UI Modal
window.loadSettingsIntoModal = async function() {
  if (!invoke) return;
  try {
    const config = await invoke("get_ai_config");
    
    // Select Provider
    const providerSel = document.getElementById("settings-provider");
    if (providerSel) {
        providerSel.value = (config.provider || "gemini").trim().toLowerCase();
    }

    // Populate Key based on provider
    const keyInput = document.getElementById("settings-api-key");
    if (keyInput) {
      const p = (config.provider || "").trim().toLowerCase();
      if (p === "openai") {
        keyInput.value = config.openai_key || "";
      } else {
        keyInput.value = config.gemini_key || "";
      }
    }
  } catch (e) {
    console.warn("Failed to load settings:", e);
    logToTerminal("Error loading settings: " + e, "warning");
  }
}

// 2. Save Settings from UI Modal -> Rust
async function saveSettingsFromModal() {
  if (!invoke) return alert("Tauri backend not found.");

  const provider = document.getElementById("settings-provider")?.value || "gemini";
  const api_key = (document.getElementById("settings-api-key")?.value || "").trim();
  
  if (!api_key) return alert("Please enter an API Key.");

  const btn = document.getElementById("btn-save-settings");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Saving...";
  }

  try {
    // Call the Rust command
    await invoke("save_configuration", { provider, api_key });

    if (btn) btn.textContent = "Saved!";
    logToTerminal(`Configuration saved. Provider: ${provider}`, "success");

    // Close modal after delay
    setTimeout(() => {
      if (btn) { 
        btn.textContent = "Save Configuration"; 
        btn.disabled = false; 
      }
      document.getElementById("settings-modal-overlay")?.classList.remove("open");
    }, 800);
  } catch (e) {
    if (btn) {
        btn.disabled = false;
        btn.textContent = "Save Configuration";
    }
    alert("Save failed: " + e);
    logToTerminal("Save failed: " + e, "error");
  }
}

// ============================================================
// MODELHUB UI HELPERS
// ============================================================

function getEl(id) {
  return document.getElementById(id);
}

function setSelectOptions(selectEl, items, getLabel, getValue, placeholder = "Select...") {
  if (!selectEl) return;
  selectEl.innerHTML = "";
  const opt0 = document.createElement("option");
  opt0.value = "";
  opt0.textContent = placeholder;
  selectEl.appendChild(opt0);

  for (const it of items) {
    const opt = document.createElement("option");
    opt.value = getValue(it);
    opt.textContent = getLabel(it);
    selectEl.appendChild(opt);
  }
}

function labelForGame(g) {
  if (typeof g === "string") return g;
  return g.name || g.title || g.id || JSON.stringify(g);
}
function valueForGame(g) {
  if (typeof g === "string") return g;
  return g.id || g.game_id || g.slug || g.name || "";
}

function labelForDataset(d) {
  return d.name || d.title || d.id || d.dataset_id || d.path || "dataset";
}
function valueForDataset(d) {
  return d.id || d.dataset_id || d.path || "";
}

function labelForModel(m) {
  return m.name || m.title || m.id || m.model_id || m.path || "model";
}
function valueForModel(m) {
  return m.id || m.model_id || m.path || "";
}

function labelForBuiltin(b) {
  return b.name || b.id || b.path || "builtin";
}
function valueForBuiltin(b) {
  return b.path || b.id || "";
}

function labelForLocalModel(m) {
  return m.name || m.id || m.path || "local";
}
function valueForLocalModel(m) {
  return m.path || m.id || "";
}

async function refreshModelhubAvailability() {
  if (!invoke) return;

  try {
    const res = await invoke("modelhub_is_available");
    modelhubAvailable = !!(res && (res.available === true || res.available === "true" || res.ok === true && res.available));
    logToTerminal(`ModelHub: ${modelhubAvailable ? "Available" : "Unavailable"}`, modelhubAvailable ? "success" : "warning");
    const badge = getEl("modelhub-status");
    if (badge) badge.textContent = modelhubAvailable ? "Available" : "Unavailable";
  } catch (e) {
    modelhubAvailable = false;
    logToTerminal(`ModelHub availability check failed: ${e}`, "warning");
  }
}

async function loadGamesIntoUI() {
  if (!invoke) return;

  try {
    const res = await invoke("modelhub_list_games");
    const games = (res && res.games) ? res.games : (Array.isArray(res) ? res : []);
    const sel = getEl("game-select");
    setSelectOptions(sel, games, labelForGame, valueForGame, "Choose game...");
    if (sel && !sel.value) {
      sel.value = selectedGameId;
    }
  } catch (e) {
    logToTerminal(`Failed to load games: ${e}`, "warning");
  }
}

async function loadCatalog(gameId) {
  if (!invoke) return;
  const gid = (gameId || "").trim() || DEFAULT_GAME_ID;
  selectedGameId = gid;

  try {
    const res = await invoke("mh_get_catalog_data", { game_id: gid });
    const payload = res && res.ok === true ? res : res;
    currentCatalog = {
      builtin_models: payload.builtin_models || [],
      datasets: payload.datasets || [],
      models: payload.models || [],
      local_models: payload.local_models || [],
      active: payload.active || null,
    };

    logToTerminal(`Catalog loaded for game: ${gid}`, "success");

    const dsSel = getEl("dataset-select");
    setSelectOptions(dsSel, currentCatalog.datasets, labelForDataset, valueForDataset, "Choose dataset...");
    if (dsSel) dsSel.value = selectedDatasetId || "";

    const builtinSel = getEl("builtin-model-select");
    setSelectOptions(builtinSel, currentCatalog.builtin_models, labelForBuiltin, valueForBuiltin, "Choose builtin model...");
    if (builtinSel) builtinSel.value = selectedBuiltinModelPath || "";

    const regSel = getEl("registry-model-select");
    setSelectOptions(regSel, currentCatalog.models, labelForModel, valueForModel, "Choose registry model...");
    if (regSel) regSel.value = selectedModelRegistryId || "";

    const localSel = getEl("local-model-select");
    setSelectOptions(localSel, currentCatalog.local_models, labelForLocalModel, valueForLocalModel, "Choose local model...");
    if (localSel) localSel.value = selectedLocalModelPath || "";

    const activeBox = getEl("active-model");
    if (activeBox) {
      activeBox.textContent = currentCatalog.active ? JSON.stringify(currentCatalog.active) : "None";
    }
  } catch (e) {
    logToTerminal(`Failed to load catalog: ${e}`, "error");
  }
}

async function setActiveModelFromUI() {
  if (!invoke) return;
  const gid = selectedGameId || DEFAULT_GAME_ID;
  let model_id = "";
  let path = "";

  if (selectedLocalModelPath) {
    model_id = "local";
    path = selectedLocalModelPath;
  } else if (selectedBuiltinModelPath) {
    model_id = "builtin";
    path = selectedBuiltinModelPath;
  } else if (selectedModelRegistryId) {
    model_id = selectedModelRegistryId;
    const found = (currentCatalog.models || []).find((m) => valueForModel(m) === selectedModelRegistryId);
    path = found ? (found.path || "") : "";
    if (!path) path = selectedModelRegistryId;
  }

  if (!path) {
    alert("Select a model (local/builtin/registry) first.");
    return;
  }

  try {
    const res = await invoke("mh_set_active", { game_id: gid, model_id, path });
    logToTerminal(`Active model set: ${path}`, "success");
    await loadCatalog(gid);
    return res;
  } catch (e) {
    logToTerminal(`Failed to set active model: ${e}`, "error");
  }
}

async function deleteSelectedModel() {
  if (!invoke) return;
  const gid = selectedGameId || DEFAULT_GAME_ID;

  if (!selectedLocalModelPath) {
    alert("Deletion is only allowed for local trained models. Select a local model first.");
    return;
  }

  const ok = confirm(`Delete model folder?\n\n${selectedLocalModelPath}\n\nThis cannot be undone.`);
  if (!ok) return;

  try {
    const res = await invoke("mh_delete_model", {
      game_id: gid,
      model_id: "local",
      path: selectedLocalModelPath,
    });
    logToTerminal(`Deleted model: ${selectedLocalModelPath}`, "success");
    selectedLocalModelPath = "";
    await loadCatalog(gid);
    return res;
  } catch (e) {
    logToTerminal(`Delete failed: ${e}`, "error");
  }
}

async function validateSelectedModel() {
  if (!invoke) return;
  const gid = selectedGameId || DEFAULT_GAME_ID;
  const modelDir = selectedLocalModelPath || selectedBuiltinModelPath || "";

  if (!modelDir) {
    alert("Select a model folder (local/builtin) to validate.");
    return;
  }

  try {
    const res = await invoke("modelhub_validate_model", { game_id: gid, model_dir: modelDir });
    const result = res && res.result ? res.result : res;
    const msg = result && result.message ? result.message : JSON.stringify(result);
    logToTerminal(`Validate: ${msg}`, (result && result.ok) ? "success" : "warning");
    const box = getEl("model-validate-result");
    if (box) box.textContent = msg;
    return res;
  } catch (e) {
    logToTerminal(`Validation failed: ${e}`, "error");
  }
}

async function runOfflineEvaluation() {
  if (!invoke) return;
  const modelDir = selectedLocalModelPath || selectedBuiltinModelPath || "";
  const datasetDir = getEl("offline-dataset-dir")?.value?.trim() || "";

  if (!modelDir || !datasetDir) {
    alert("Provide model_dir and dataset_dir for offline evaluation.");
    return;
  }

  try {
    const res = await invoke("modelhub_run_offline_evaluation", { model_dir: modelDir, dataset_dir: datasetDir });
    logToTerminal("Offline evaluation started.", "success");
    return res;
  } catch (e) {
    logToTerminal(`Offline eval failed: ${e}`, "error");
  }
}

// ------------------------------------------------------------
// BUTTON HANDLERS (Rust Commands)
// ------------------------------------------------------------

// TEACH: Toggle Recording
window.toggleRecord = async function (btn) {
  if (!invoke) return alert("Tauri backend not found.");
  isRecording = !isRecording;
  const status = document.getElementById("record-status");

  if (isRecording) {
    try {
      logToTerminal("Requesting recording start...", "info");
      btn.disabled = true;
      const game_id = (getEl("teach-game-id")?.value || selectedGameId || DEFAULT_GAME_ID).trim();
      const dataset_name = (getEl("teach-dataset-name")?.value || "Untitled").trim();

      const res = await invoke("start_recording", { game_id, dataset_name });
      logToTerminal(res, "success");
      btn.innerHTML = "<span>■</span> Stop Recording";
      btn.style.background = "#333";
      if (status) {
        status.innerText = "🔴 Recording... Switch to game window!";
        status.style.color = "#FF5252";
      }
    } catch (err) {
      logToTerminal(`Error starting recording: ${err}`, "error");
      isRecording = false;
    } finally {
      btn.disabled = false;
    }
  } else {
    try {
      btn.disabled = true;
      const res = await invoke("stop_process");
      logToTerminal(res, "success");
      btn.innerHTML = "<span>●</span> Start Recording";
      btn.style.background = "var(--accent)";
      if (status) {
        status.innerText = "✓ Recording saved.";
        status.style.color = "var(--success)";
      }
    } catch (err) {
      logToTerminal(`Error stopping recording: ${err}`, "error");
    } finally {
      btn.disabled = false;
    }
  }
};

// TRAIN: Start Training
window.startTraining = async function () {
  if (!invoke) return alert("Tauri backend not found.");
  const progressBar = document.getElementById("progress-bar");
  const pctDisplay = document.getElementById("train-pct");
  const btn = document.getElementById("btnStartTraining");

  try {
    logToTerminal("-------------------------------------------", "info");
    logToTerminal("Initializing Neural Network Training...", "info");
    if (btn) btn.disabled = true;
    if (progressBar) progressBar.style.width = "0%";
    if (pctDisplay) pctDisplay.textContent = "0%";

    const game_id = (getEl("train-game-id")?.value || selectedGameId || DEFAULT_GAME_ID).trim();
    const model_name = (getEl("train-model-name")?.value || "New Model").trim();
    const dataset_id = (getEl("train-dataset-id")?.value || selectedDatasetId || "").trim();
    const arch = (getEl("train-arch")?.value || "custom").trim();

    const res = await invoke("start_training", { game_id, model_name, dataset_id, arch });
    logToTerminal(res, "success");
  } catch (err) {
    logToTerminal(`Training failed to start: ${err}`, "error");
    if (btn) btn.disabled = false;
  }
};

// TRAIN: Analyze Logs
window.analyzeLogs = async function () {
  const terminal = document.getElementById("terminal");
  const resultBox = document.getElementById("log-analysis-result");
  const resultText = document.getElementById("analysis-text");
  if (!terminal) return;
  const logs = terminal.innerText;
  if (logs.length < 50) {
    alert("Not enough logs to analyze. Please run training first.");
    return;
  }
  if (resultText) resultText.textContent = "Analyzing local logs...";
  if (resultBox) resultBox.style.display = "block";
  setTimeout(() => {
    let analysis = "Log Analysis: \n";
    const epochCount = (logs.match(/Epoch/g) || []).length;
    if (epochCount > 0) analysis += `• Found ${epochCount} training epochs.\n`;
    else analysis += "• No training epochs detected yet.\n";
    if (logs.includes("Error") || logs.includes("Exception")) analysis += "• ⚠️ Errors detected in logs.\n";
    else analysis += "• System appears stable.\n";
    if (resultText) resultText.textContent = analysis;
  }, 800);
};

// RUN: Toggle Bot
window.toggleBot = async function (btn) {
  if (!invoke) return alert("Tauri backend not found.");
  isBotRunning = !isBotRunning;
  if (isBotRunning) {
    try {
      logToTerminal("Initializing autonomous bot...", "info");
      btn.disabled = true;
      const res = await invoke("start_bot");
      logToTerminal(res, "success");
      btn.innerText = "■ STOP BOT";
      btn.style.background = "var(--accent)";
      btn.style.color = "white";
    } catch (err) {
      logToTerminal(`Failed to start bot: ${err}`, "error");
      isBotRunning = false;
    } finally {
      btn.disabled = false;
    }
  } else {
    try {
      btn.disabled = true;
      const res = await invoke("stop_process");
      logToTerminal(res, "success");
      btn.innerText = "▶ START BOT";
      btn.style.background = "var(--success)";
      btn.style.color = "black";
    } catch (err) {
      logToTerminal(`Failed to stop bot: ${err}`, "error");
    } finally {
      btn.disabled = false;
    }
  }
};

// RUN: Install Drivers
window.installDrivers = async function () {
  if (!invoke) return alert("Tauri backend not found.");
  logToTerminal("Installing drivers (admin)...", "info");
  try {
    const res = await invoke("install_drivers");
    if (res && res.ok) {
      logToTerminal("Driver installer launched.", "success");
      const st = getEl("drivers-status");
      if (st) st.textContent = "Installer launched";
    } else {
      logToTerminal(`Driver install failed: ${JSON.stringify(res)}`, "warning");
    }
  } catch (e) {
    logToTerminal(`Driver install error: ${e}`, "error");
  }
};

// AI STRATEGIST: Chat
window.sendChatMessage = async function () {
  if (!invoke) return alert("Tauri backend not found.");
  const input = document.getElementById("chat-input");
  const history = document.getElementById("chat-history");
  const spinner = document.getElementById("chat-spinner");
  const sendBtn = document.getElementById("btnSendChat");
  if (!input || !history) return;
  const msg = input.value.trim();
  if (!msg) return;

  const userBubble = document.createElement("div");
  userBubble.className = "chat-bubble bubble-user";
  userBubble.textContent = msg;
  history.appendChild(userBubble);
  input.value = "";
  history.scrollTop = history.scrollHeight;

  if (spinner) spinner.style.display = "block";
  if (sendBtn) sendBtn.disabled = true;

  try {
    const reply = await invoke("ai_chat", { message: msg });
    const aiBubble = document.createElement("div");
    aiBubble.className = "chat-bubble bubble-ai";
    aiBubble.textContent = reply;
    history.appendChild(aiBubble);
  } catch (e) {
    const aiBubble = document.createElement("div");
    aiBubble.className = "chat-bubble bubble-ai";
    aiBubble.textContent = `⚠️ AI error: ${e}`;
    history.appendChild(aiBubble);
  } finally {
    if (spinner) spinner.style.display = "none";
    if (sendBtn) sendBtn.disabled = false;
    history.scrollTop = history.scrollHeight;
  }
};

// ------------------------------------------------------------
// EVENTS FROM RUST
// ------------------------------------------------------------
async function wireBackendEvents() {
  if (!listen) return;

  await listen("terminal_update", (event) => {
    const line = typeof event.payload === "string" ? event.payload : JSON.stringify(event.payload);
    window.update_terminal(line);
  });

  await listen("process_finished", (event) => {
    const msg = typeof event.payload === "string" ? event.payload : JSON.stringify(event.payload);
    logToTerminal(`[System] Process finished: ${msg}`, "info");
    const btn = getEl("btnStartTraining");
    if (btn) btn.disabled = false;
    isRecording = false;
    isBotRunning = false;
  });
}

// ------------------------------------------------------------
// INITIALIZATION + UI WIRING
// ------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  logToTerminal("═══════════════════════════════════════", "info");
  logToTerminal("BOT MMORPG AI (Tauri Edition)", "info");
  logToTerminal("Initializing Rust Core...", "info");

  if (invoke) {
    updateBackendStatus("Running", "Rust Backend Active");
    logToTerminal("✓ Tauri Backend Connected", "success");

    await wireBackendEvents();

    // Initial Config Log (just for user confidence)
    invoke("get_ai_config").then((config) => {
      if(config.provider) {
        logToTerminal(`Loaded Config: ${config.provider}`, "info");
      }
    }).catch((err) => logToTerminal(`Config Load Warning: ${err}`, "warning"));

    await refreshModelhubAvailability();
    if (modelhubAvailable) {
      await loadGamesIntoUI();
      await loadCatalog(selectedGameId);
    }
  } else {
    updateBackendStatus("Error", "Tauri Not Found");
    logToTerminal("⚠ Tauri API not detected. Is this running in a browser?", "error");
  }

  wireEvents();
});

function wireEvents() {
  // Tabs
  document.querySelectorAll("button[data-tab], a[data-tab]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const tab = btn.getAttribute("data-tab");
      if (tab) window.showTab(tab);
    });
  });

  // Buttons
  const bind = (id, func) => {
    const el = getEl(id);
    if (el) el.addEventListener("click", () => func(el));
  };

  bind("btnRecord", window.toggleRecord);
  bind("btnStartTraining", () => window.startTraining());
  bind("btnAnalyzeLogs", () => window.analyzeLogs());
  bind("btnStartBot", window.toggleBot);
  bind("btnInstallDrivers", () => window.installDrivers());
  bind("btnSendChat", () => window.sendChatMessage());
  
  // Settings Modal Buttons
  // Note: HTML might have them; ensure they exist before binding
  const btnOpenSettings = getEl("btn-open-settings");
  if (btnOpenSettings) {
    btnOpenSettings.addEventListener("click", () => {
        window.loadSettingsIntoModal();
        const overlay = getEl("settings-modal-overlay");
        if(overlay) overlay.classList.add("open");
    });
  }
  
  const btnSaveSettings = getEl("btn-save-settings");
  if (btnSaveSettings) {
      btnSaveSettings.addEventListener("click", saveSettingsFromModal);
  }

  // When provider changes in modal, clear the key input (UX safety)
  const settingsProvider = getEl("settings-provider");
  if(settingsProvider) {
      settingsProvider.addEventListener("change", () => {
          const keyInput = getEl("settings-api-key");
          if(keyInput) keyInput.value = "";
      });
  }

  // Chat Input
  const chatInput = getEl("chat-input");
  if (chatInput) {
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") window.sendChatMessage();
    });
  }

  // ModelHub UI wiring
  const gameSel = getEl("game-select");
  if (gameSel) {
    gameSel.addEventListener("change", async () => {
      selectedGameId = gameSel.value || DEFAULT_GAME_ID;
      await loadCatalog(selectedGameId);
    });
  }

  const dsSel = getEl("dataset-select");
  if (dsSel) {
    dsSel.addEventListener("change", () => {
      selectedDatasetId = dsSel.value || "";
      const t = getEl("train-dataset-id");
      if (t && !t.value) t.value = selectedDatasetId;
    });
  }

  const builtinSel = getEl("builtin-model-select");
  if (builtinSel) {
    builtinSel.addEventListener("change", () => {
      selectedBuiltinModelPath = builtinSel.value || "";
      selectedModelRegistryId = "";
      selectedLocalModelPath = "";
      getEl("registry-model-select").value = "";
      getEl("local-model-select").value = "";
    });
  }

  const regSel = getEl("registry-model-select");
  if (regSel) {
    regSel.addEventListener("change", () => {
      selectedModelRegistryId = regSel.value || "";
      selectedBuiltinModelPath = "";
      selectedLocalModelPath = "";
      getEl("builtin-model-select").value = "";
      getEl("local-model-select").value = "";
    });
  }

  const localSel = getEl("local-model-select");
  if (localSel) {
    localSel.addEventListener("change", () => {
      selectedLocalModelPath = localSel.value || "";
      selectedBuiltinModelPath = "";
      selectedModelRegistryId = "";
      getEl("builtin-model-select").value = "";
      getEl("registry-model-select").value = "";
    });
  }

  const btnSetActive = getEl("btnSetActiveModel");
  if (btnSetActive) btnSetActive.addEventListener("click", () => setActiveModelFromUI());

  const btnDelete = getEl("btnDeleteModel");
  if (btnDelete) btnDelete.addEventListener("click", () => deleteSelectedModel());

  const btnValidate = getEl("btnValidateModel");
  if (btnValidate) btnValidate.addEventListener("click", () => validateSelectedModel());

  const btnOfflineEval = getEl("btnOfflineEval");
  if (btnOfflineEval) btnOfflineEval.addEventListener("click", () => runOfflineEvaluation());
}