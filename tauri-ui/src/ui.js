import { listen } from "@tauri-apps/api/event";
import { api } from "./tauri.js";

// -------------------------
// Global Config / State
// -------------------------
export let aiConfig = { provider: "gemini", gemini_key: "", openai_key: "" };
export const DEFAULT_GAME = "genshin_impact";
export let activeGameId = DEFAULT_GAME;
export let mhSelected = null; 
export let mhCache = null;
export let isRecording = false;
export let isBotRunning = false;
export let twStep = 1;

// -------------------------
// Toast helpers
// -------------------------
export function toast(title, msg, kind = "ok") {
  const wrap = document.getElementById("toast-wrap");
  if (!wrap) return;
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<div class="t-title">${escapeHtml(title)}</div><div class="t-msg">${escapeHtml(msg)}</div>`;
  wrap.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateY(8px)"; }, 2600);
  setTimeout(() => { try { wrap.removeChild(el); } catch (_) {} }, 3200);
}

// -------------------------
// Settings Modal
// -------------------------
export function openSettings() {
  document.getElementById("settings-modal-overlay")?.classList.add("open");
  updateModalInput();
}

export function closeSettings() {
  document.getElementById("settings-modal-overlay")?.classList.remove("open");
}

export function togglePasswordVis() {
  const input = document.getElementById("settings-api-key");
  if (!input) return;
  input.type = input.type === "password" ? "text" : "password";
}

export function updateModalInput() {
  const provider = document.getElementById("settings-provider")?.value || "gemini";
  const input = document.getElementById("settings-api-key");
  if (!input) return;

  if (provider === "gemini") {
    input.value = aiConfig.gemini_key || "";
    input.placeholder = "Paste Gemini API Key (starts with AIza...)";
  } else {
    input.value = aiConfig.openai_key || "";
    input.placeholder = "Paste OpenAI API Key (starts with sk-...)";
  }
}

export async function saveSettings() {
  const provider = document.getElementById("settings-provider")?.value || "gemini";
  const apiKey = (document.getElementById("settings-api-key")?.value || "").trim();
  const btn = document.getElementById("btn-save-settings");

  if (!apiKey) { alert("Please enter an API Key."); return; }
  if (btn) btn.innerText = "Saving...";

  try {
    await api.saveConfiguration(provider, apiKey);
    aiConfig.provider = provider;
    if (provider === "gemini") aiConfig.gemini_key = apiKey;
    if (provider === "openai") aiConfig.openai_key = apiKey;

    if (btn) {
      btn.innerText = "Saved!";
      btn.style.background = "var(--success)";
    }
    toast("Saved", `Switched provider to ${provider.toUpperCase()}`, "ok");
    setTimeout(() => {
      closeSettings();
      if (btn) {
        btn.innerText = "Save Configuration";
        btn.style.background = "var(--primary)";
      }
    }, 900);
  } catch (e) {
    console.error(e);
    toast("Error", "Failed to save settings.", "err");
    if (btn) {
      btn.innerText = "Error Saving";
      btn.style.background = "var(--accent)";
    }
  }
}

// -------------------------
// Logging / Terminal
// -------------------------
export function logSystem(msg) {
  const term = document.getElementById("terminal");
  if (!term) return;
  const time = new Date().toLocaleTimeString();
  term.innerHTML += `<div class="log-entry"><span class="log-time">[${escapeHtml(time)}]</span> ${escapeHtml(msg)}</div>`;
  term.scrollTop = term.scrollHeight;
}

export function update_terminal(line) {
  const text = typeof line === "string" ? line : JSON.stringify(line);
  logSystem(text);
  if (text.toLowerCase().includes("epoch")) {
    const match = text.match(/Epoch\s+(\d+)\s*\/\s*(\d+)/i);
    if (match) {
      const cur = parseInt(match[1], 10);
      const tot = parseInt(match[2], 10);
      if (tot > 0) {
        const percent = (cur / tot) * 100;
        const bar = document.getElementById("progress-bar");
        const pct = document.getElementById("train-pct");
        if (bar) bar.style.width = `${percent}%`;
        if (pct) pct.innerText = `${Math.round(percent)}%`;
      }
    }
  }
}

// -------------------------
// Tabs
// -------------------------
export function showTab(tabId) {
  const titles = {
    dashboard: "Dashboard", teach: "Teach Mode", train: "Neural Training",
    run: "Run Bot", models: "Model Catalog", strategist: "AI Strategist",
  };
  const titleEl = document.getElementById("page-title");
  if (titleEl) titleEl.innerText = titles[tabId] || tabId;

  document.querySelectorAll(".tab-content").forEach((el) => {
    el.classList.remove("active");
    el.style.display = "";
  });

  const activeTab = document.getElementById("tab-" + tabId);
  if (activeTab) {
    activeTab.classList.add("active");
    if (tabId === "teach" || tabId === "train") activeTab.style.display = "flex";
    else activeTab.style.display = "block";
  }

  document.querySelectorAll(".nav-btn").forEach((el) => el.classList.remove("active"));
  const btn = document.getElementById("btn-" + tabId);
  if (btn) btn.classList.add("active");
}

// -------------------------
// AI Calls
// -------------------------
export async function callAI(prompt, systemInstruction = "") {
  const provider = aiConfig.provider || "gemini";
  const activeKey = provider === "openai" ? aiConfig.openai_key : aiConfig.gemini_key;

  if (!activeKey) {
    logSystem(`❌ Error: No API Key found for ${provider.toUpperCase()}. Check Settings.`);
    return "⚠️ Error: API Key missing. Please configure settings.";
  }
  logSystem(`🚀 Sending request to ${provider.toUpperCase()}...`);

  try {
    let responseText = "";
    if (provider === "gemini") {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${activeKey}`;
      const payload = {
        contents: [{ parts: [{ text: prompt }] }],
        systemInstruction: { parts: [{ text: systemInstruction }] },
      };
      const response = await fetch(url, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const errText = await response.text();
        if (response.status === 429) throw new Error("Quota Exceeded (429). Free Tier limit reached.");
        throw new Error(`Gemini API Error (${response.status}): ${errText}`);
      }
      const data = await response.json();
      responseText = data?.candidates?.[0]?.content?.parts?.[0]?.text || "No response.";
    }
    if (provider === "openai") {
      const url = "https://api.openai.com/v1/chat/completions";
      const payload = {
        model: "gpt-4o",
        messages: [{ role: "system", content: systemInstruction }, { role: "user", content: prompt }],
      };
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${activeKey}` },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`OpenAI API Error (${response.status}): ${errText}`);
      }
      const data = await response.json();
      responseText = data?.choices?.[0]?.message?.content || "No response.";
    }
    logSystem(`✅ Response received from ${provider.toUpperCase()}.`);
    return responseText;
  } catch (e) {
    console.error(e);
    logSystem(`❌ CONNECTION ERROR: ${e.message}`);
    return `Error: ${e.message}`;
  }
}

export async function analyzeLogs() {
  const term = document.getElementById("terminal");
  if (!term) return;
  const logs = term.innerText || "";
  if (logs.length < 20) { alert("Not enough logs."); return; }

  const box = document.getElementById("log-analysis-result");
  const out = document.getElementById("analysis-text");
  if (box) box.style.display = "block";
  if (out) out.innerText = "Analyzing...";

  const ans = await callAI(`Analyze these logs concisely:\n\n${logs}`, "You are a concise ML training log analyst.");
  if (out) out.innerHTML = escapeHtml(ans).replace(/\*\*(.*?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>");
}

// -------------------------
// Teach / Recording
// -------------------------
export async function toggleRecord(btn) {
  isRecording = !isRecording;
  const status = document.getElementById("record-status");
  const dsName = (document.getElementById("dataset-name")?.value || "").trim() || "Untitled";

  if (isRecording) {
    try { await api.startRecording(activeGameId, dsName); } catch (e) {
      console.error(e); isRecording = false; toast("Recording", "Failed to start recording.", "err"); return;
    }
    if (btn) { btn.innerHTML = "<span>■</span> Stop"; btn.classList.remove("btn-danger"); btn.classList.add("btn-secondary"); }
    if (status) { status.innerText = "🔴 Recording... Stop to archive dataset into catalog."; status.style.color = "#FF5252"; }
    toast("Recording", `Dataset: ${dsName}`, "warn");
  } else {
    try { await api.stopProcess(); } catch (e) { console.error(e); }
    if (btn) { btn.innerHTML = "<span>●</span> Start Recording"; btn.classList.remove("btn-secondary"); btn.classList.add("btn-danger"); }
    if (status) { status.innerText = "✅ Stopped. If new data was detected, it was archived into datasets/."; status.style.color = "var(--success)"; }
    toast("Saved", "Recording session finalized.", "ok");
    await refreshCatalog();
  }
}

// -------------------------
// Bot Run
// -------------------------
export async function toggleBot(btn) {
  isBotRunning = !isBotRunning;
  const stateEl = document.getElementById("bot-state");
  if (isBotRunning) {
    try { await api.startBot(); } catch (e) {
      console.error(e); isBotRunning = false; toast("Bot", "Failed to start bot.", "err"); return;
    }
    if (btn) { btn.innerText = "■ STOP BOT"; btn.style.background = "var(--accent)"; btn.style.color = "white"; }
    if (stateEl) stateEl.innerText = "RUNNING";
    toast("Bot", "Bot started.", "ok");
  } else {
    try { await api.stopProcess(); } catch (e) { console.error(e); }
    if (btn) { btn.innerText = "▶ START BOT"; btn.style.background = "var(--success)"; btn.style.color = "black"; }
    if (stateEl) stateEl.innerText = "IDLE";
    toast("Bot", "Bot stopped.", "warn");
  }
}

// -------------------------
// ModelHub
// -------------------------
export async function mhInit() {
  const status = document.getElementById("mh-status");
  try {
    const ok = await api.modelhubIsAvailable();
    if (!ok) { if (status) status.innerText = "ModelHub missing"; toast("ModelHub", "Python bridge missing", "err"); return; }
  } catch (e) { console.error(e); if (status) status.innerText = "ModelHub error"; return; }

  if (status) status.innerText = "Local-only ready";
  let gamesPayload;
  try { gamesPayload = await api.modelhubListGames(); } catch (e) { console.error(e); return; }

  const games = Array.isArray(gamesPayload) ? gamesPayload : gamesPayload?.games || [];
  const selCatalog = document.getElementById("mh-game");
  const selTwGame = document.getElementById("tw-game");

  if (selCatalog) selCatalog.innerHTML = `<option value="">Select game…</option>`;
  if (selTwGame) selTwGame.innerHTML = ``;

  for (const g of games) {
    const id = g.id || g.game_id || "";
    const name = g.display_name || id;
    if (!id) continue;
    if (selCatalog) selCatalog.innerHTML += `<option value="${escapeHtmlAttr(id)}">${escapeHtml(name)}</option>`;
    if (selTwGame) selTwGame.innerHTML += `<option value="${escapeHtmlAttr(id)}">${escapeHtml(name)}</option>`;
  }

  activeGameId = DEFAULT_GAME;
  if (selCatalog) selCatalog.value = activeGameId;
  if (selTwGame) selTwGame.value = activeGameId;
  setActiveGamePills(activeGameId);
  await refreshCatalog();
}

function setActiveGamePills(gid) {
  const pill = document.getElementById("active-game-pill");
  const teach = document.getElementById("teach-game");
  if (pill) pill.innerText = gid;
  if (teach) teach.innerText = gid;
}

function _setStatsFromCatalog(payload) {
  const dsCount = payload?.datasets?.length ?? 0;
  const mCount = (payload?.models?.length ?? 0) + (payload?.builtin_models?.length ?? 0);
  const dsEl = document.getElementById("stat-datasets");
  const mEl = document.getElementById("stat-models");
  if (dsEl) dsEl.innerText = dsCount;
  if (mEl) mEl.innerText = mCount;

  const active = payload?.active || null;
  const activeName = active?.model_id || "—";
  const sActive = document.getElementById("stat-active");
  const rActive = document.getElementById("run-active-model");
  const mhActive = document.getElementById("mh-active-pill");
  if (sActive) sActive.innerText = activeName;
  if (rActive) rActive.innerText = activeName;
  if (mhActive) mhActive.innerText = activeName;
}

export async function refreshCatalog() {
  const sel = document.getElementById("mh-game");
  const gid = (sel?.value || "").trim() || DEFAULT_GAME;
  activeGameId = gid;
  setActiveGamePills(activeGameId);
  mhSelected = null;
  const details = document.getElementById("mh-details-pre");
  if (details) details.innerText = "(none)";
  setDisabled("mh-validate", true); setDisabled("mh-eval", true);
  setDisabled("mh-set-active", true); setDisabled("mh-run", true);

  const list = document.getElementById("mh-models-list");
  if (list) list.innerHTML = `<div class="log-entry" style="padding:10px;"><span class="log-time">[ModelHub]</span> Loading…</div>`;

  try {
    const payload = await api.mhGetCatalogData(gid);
    mhCache = payload;
    _setStatsFromCatalog(payload);
    const activeId = payload?.active?.model_id || null;
    const builtins = payload?.builtin_models || [];
    const managed = payload?.models || [];

    if (list) list.innerHTML = "";
    if (builtins.length > 0 && list) {
      list.innerHTML += `<div class="log-entry" style="padding:10px; color:#d1d5db;"><span class="log-time">[Built-in]</span> Testing models</div>`;
      for (const m of builtins) list.appendChild(renderModelItem(gid, m, "builtin", activeId));
    }
    if (list) {
      const sep = document.createElement('div');
      sep.className = 'log-entry'; sep.style.padding='10px'; sep.style.color='#d1d5db';
      sep.innerHTML = '<span class="log-time">[Trained]</span> Archived models';
      list.appendChild(sep);
      if (managed.length === 0) list.innerHTML += `<div class="log-entry" style="padding:10px; color:var(--text-dim);">[None] Use Train Wizard</div>`;
      else for (const m of managed) list.appendChild(renderModelItem(gid, m, "managed", activeId));
    }
    await twRefreshDatasets(true);
    toast("Catalog", "Updated catalog.", "ok");
  } catch (e) {
    console.error(e);
    if (list) list.innerHTML = `<div class="log-entry" style="padding:10px;">[Error] Failed to load catalog.</div>`;
    toast("Catalog Error", "Backend failed.", "err");
  }
}

function renderModelItem(gameId, model, kind, activeId) {
  const item = document.createElement("div");
  item.className = "m-item";
  const id = model.id || model.model_id || model.name || "unknown";
  const name = model.name || model.profile_name || id;
  const arch = model.architecture || model.profile?.architecture || "unknown";
  const path = model.path || model.paths?.dir || model.dir || "";
  const isActive = activeId && id === activeId;
  if (isActive) item.classList.add("active");
  const topRight = kind === "builtin" ? `<span class="tag built">BUILT-IN</span>` : `<span class="tag good">TRAINED</span>`;

  item.innerHTML = `
    <div class="top"><div><div class="m-name">${escapeHtml(name)}</div><div class="m-sub">${escapeHtml(id)}</div></div>
    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:6px;">${topRight}${isActive ? `<span class="tag active">ACTIVE</span>` : ``}</div></div>
    <div class="m-tags"><span class="tag">🎮 ${escapeHtml(gameId)}</span><span class="tag">🧬 ${escapeHtml(arch)}</span></div>
  `;
  item.onclick = () => mhSelectModel(gameId, model, kind, item);
  return item;
}

export function mhSelectModel(gameId, model, kind, el) {
  document.querySelectorAll(".m-item").forEach((x) => x.classList.remove("active"));
  el?.classList.add("active");
  mhSelected = { gameId, model, kind, _el: el };
  const pre = document.getElementById("mh-details-pre");
  if (pre) pre.innerText = JSON.stringify({ kind, ...model }, null, 2);
  setDisabled("mh-validate", false); setDisabled("mh-eval", false);
  setDisabled("mh-set-active", false); setDisabled("mh-run", false);
}

export async function mhValidate() {
  if (!mhSelected) return;
  const { gameId, model, kind } = mhSelected;
  const modelDir = kind === "builtin" ? model.paths?.dir || model.dir : model.path || model.dir;
  const res = await api.mhValidate(gameId, modelDir || "");
  if (res?.ok) toast("Validate", "Model profile OK.", "ok");
  else toast("Validate", res?.message || "Invalid.", "warn");
  logSystem(res?.ok ? `✅ Model valid.` : `⚠️ Model invalid: ${res?.message || ""}`);
}

export async function mhEval() {
  if (!mhSelected) return;
  const ds = (document.getElementById("mh-dataset")?.value || "").trim();
  if (!ds) { alert("Please set a dataset folder."); return; }
  const { model, kind } = mhSelected;
  const modelDir = kind === "builtin" ? model.paths?.dir || model.dir : model.path || model.dir;
  const res = await api.mhOfflineEval(modelDir || "", ds);
  logSystem(res?.ok ? `▶ Eval started.` : `❌ Eval failed: ${res?.message || ""}`);
}

export async function mhSetActive() {
  if (!mhSelected) return;
  const { gameId, model, kind } = mhSelected;
  const modelId = model.id || model.model_id || "unknown";
  const modelPath = kind === "builtin" ? model.paths?.dir || model.dir : model.path || model.dir;
  const res = await api.mhSetActive(gameId, modelId, modelPath || "");
  if (res?.ok === false) { toast("Active Model", res?.error || "Failed.", "err"); return; }
  toast("Active Model", `Set active: ${modelId}`, "ok");
  await refreshCatalog();
  showTab("run");
}

export async function mhRunSelected() {
  await mhSetActive();
  if (!isBotRunning) { const btn = document.getElementById("btn-bot"); await toggleBot(btn); }
}

// -------------------------
// Train Wizard
// -------------------------
export function openTrainWizard() {
  document.getElementById("train-wizard-overlay")?.classList.add("open");
  twStep = 1; twRender();
  const nameInput = document.getElementById("tw-model-name");
  if (nameInput && !nameInput.value) nameInput.value = "model_" + new Date().toISOString().slice(0, 10).replaceAll("-", "");
  twRefreshDatasets(true);
}

export function closeTrainWizard() { document.getElementById("train-wizard-overlay")?.classList.remove("open"); }
export function twBack() { if (twStep > 1) { twStep -= 1; twRender(); } }

export async function twNext() {
  if (twStep === 1) {
    const name = (document.getElementById("tw-model-name")?.value || "").trim();
    if (!name) { toast("Train Wizard", "Please enter a model name.", "warn"); return; }
    const game = document.getElementById("tw-game")?.value || DEFAULT_GAME;
    activeGameId = game;
    setActiveGamePills(activeGameId);
    twStep = 2; twRender(); await twRefreshDatasets(); return;
  }
  if (twStep === 2) {
    if (!document.getElementById("tw-dataset")?.value) { toast("Wizard", "Pick a dataset.", "warn"); return; }
    twStep = 3; twRender(); return;
  }
  const modelName = document.getElementById("tw-model-name")?.value || "Untitled";
  const gameId = document.getElementById("tw-game")?.value || DEFAULT_GAME;
  const datasetId = document.getElementById("tw-dataset")?.value || "";
  const arch = document.getElementById("tw-arch")?.value || "custom";
  closeTrainWizard(); showTab("train");
  logSystem(`🧠 Training: ${modelName} (${arch})`);
  try { await api.startTraining(gameId, modelName, datasetId, arch); } catch (e) { console.error(e); }
}

export async function twRefreshDatasets(silent = false) {
  const gameId = document.getElementById("tw-game")?.value || activeGameId || DEFAULT_GAME;
  const dsSel = document.getElementById("tw-dataset");
  if (!dsSel) return;
  try {
    const payload = await api.mhGetCatalogData(gameId);
    const ds = payload?.datasets || [];
    dsSel.innerHTML = ds.length === 0 ? `<option value="">(No datasets)</option>` : `<option value="">Select dataset…</option>`;
    for (const d of ds) {
      const did = d.id || d.dataset_id || "";
      if (!did) continue;
      dsSel.innerHTML += `<option value="${escapeHtmlAttr(did)}">${escapeHtml(d.name || did)}</option>`;
    }
  } catch (e) { if (!silent) toast("Datasets", "Failed to load.", "err"); }
}

function twRender() {
  const d1 = document.getElementById("tw-dot-1"), d2 = document.getElementById("tw-dot-2"), d3 = document.getElementById("tw-dot-3");
  const l1 = document.getElementById("tw-line-1"), l2 = document.getElementById("tw-line-2");
  [d1, d2, d3].forEach((d) => d?.classList.remove("active", "done"));
  l1.style.width = "0%"; l2.style.width = "0%";
  if (twStep === 1) d1?.classList.add("active");
  else if (twStep === 2) { d1?.classList.add("done"); l1.style.width = "100%"; d2?.classList.add("active"); }
  else { d1?.classList.add("done"); l1.style.width = "100%"; d2?.classList.add("done"); l2.style.width = "100%"; d3?.classList.add("active"); }
  document.querySelectorAll(".wizard-page").forEach((p) => p.classList.remove("active"));
  document.getElementById("tw-step-" + twStep)?.classList.add("active");
  const btn = document.getElementById("tw-next");
  if(btn) btn.innerText = twStep === 3 ? "Start Training" : "Next";
  if (twStep === 3) {
    const sum = document.getElementById("tw-summary");
    if (sum) sum.innerHTML = `<div>Model: <b>${escapeHtml(document.getElementById("tw-model-name")?.value)}</b></div>`;
  }
}

// -------------------------
// Chat
// -------------------------
export function handleChatEnter(e) { if (e.key === "Enter") sendChatMessage(); }
export async function sendChatMessage() {
  const input = document.getElementById("chat-input"), history = document.getElementById("chat-history"), spinner = document.getElementById("chat-spinner");
  const msg = (input?.value || "").trim();
  if (!msg) return;
  history.innerHTML += `<div class="chat-bubble bubble-user">${escapeHtml(msg)}</div>`;
  history.scrollTop = history.scrollHeight;
  input.value = ""; spinner.style.display = "block";
  const response = await callAI(msg, "You are a hardcore MMORPG gaming assistant.");
  spinner.style.display = "none";
  history.innerHTML += `<div class="chat-bubble bubble-ai">${escapeHtml(response).replace(/\*\*(.*?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>")}</div>`;
  history.scrollTop = history.scrollHeight;
}

// -------------------------
// Init
// -------------------------
export async function initUI() {
  const p = document.getElementById("settings-provider");
  if (p) p.addEventListener("change", updateModalInput);
  try {
    const saved = await api.getAiConfig();
    if (saved) { aiConfig = saved; logSystem(`System Initialized. Provider: ${(saved.provider || "gemini").toUpperCase()}`); if(p) p.value = saved.provider; updateModalInput(); }
  } catch (e) { console.error(e); }
  try { await listen("terminal_update", (e) => update_terminal(e.payload)); } catch (e) { console.error(e); }
  await mhInit();
  showTab("dashboard");
}

// Helpers
function setDisabled(id, v) { const el = document.getElementById(id); if (el) el.disabled = !!v; }
export function escapeHtml(str) { return (str ?? "").toString().replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"); }
export function escapeHtmlAttr(str) { return escapeHtml(str).replaceAll("`", "&#096;"); }