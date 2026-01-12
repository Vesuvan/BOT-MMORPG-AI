// State
const __TAURI__ = window.__TAURI__;
const { invoke } = __TAURI__.tauri;
const { Command } = __TAURI__.shell;

let backendPort = null;
let isRecording = false;
let isRunning = false;

// --- TAB NAVIGATION ---
window.showTab = function(tabId) {
  const titles = {
    'dashboard': 'Dashboard',
    'teach': 'Teach Mode (Data Collection)',
    'train': 'Neural Network Training',
    'run': 'Run Bot',
    'strategist': 'AI Strategist'
  };

  const pageTitle = document.getElementById('page-title');
  if (pageTitle) {
    pageTitle.textContent = titles[tabId] || 'Dashboard';
  }

  // Hide all tabs
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));

  // Show selected tab
  const selectedTab = document.getElementById('tab-' + tabId);
  if (selectedTab) {
    selectedTab.classList.add('active');
  }

  // Update nav buttons
  document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
  const selectedBtn = document.getElementById('btn-' + tabId);
  if (selectedBtn) {
    selectedBtn.classList.add('active');
  }
};

// --- LOGGING FUNCTIONS ---
function logToTerminal(msg, type = 'info') {
  const terminal = document.getElementById('terminal');
  if (!terminal) return;

  const timestamp = new Date().toLocaleTimeString();
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = `<span class="log-time">[${timestamp}]</span> ${msg}`;

  terminal.appendChild(entry);
  terminal.scrollTop = terminal.scrollHeight;

  // Keep last 100 entries
  const entries = terminal.querySelectorAll('.log-entry');
  if (entries.length > 100) {
    entries[0].remove();
  }
}

function updateBackendStatus(status, message) {
  const backendStatus = document.getElementById('backend-status');
  const backendStatusBadge = document.getElementById('backend-status-badge');
  const backendStatusText = document.getElementById('backend-status-text');

  if (backendStatus) backendStatus.textContent = message;
  if (backendStatusBadge) backendStatusBadge.textContent = status;
  if (backendStatusText) backendStatusText.textContent = message;
}

function updateDriversStatus(status, message) {
  const driversStatus = document.getElementById('drivers-status');
  if (driversStatus) driversStatus.textContent = message;
}

// --- BACKEND MANAGEMENT ---
async function startBackend() {
  try {
    logToTerminal('Starting backend server...', 'info');
    updateBackendStatus('starting', 'Starting...');

    const cmd = Command.sidecar('binaries/main-backend');

    cmd.on('close', data => {
      logToTerminal(`Backend exited: code=${data.code}`, 'error');
      updateBackendStatus('Stopped', 'Backend stopped');
    });

    cmd.on('error', err => {
      logToTerminal(`Backend error: ${JSON.stringify(err)}`, 'error');
      updateBackendStatus('Error', 'Backend error');
    });

    cmd.stdout.on('data', line => {
      try {
        const j = JSON.parse(line);
        if (j.port) {
          backendPort = j.port;
          logToTerminal(`Backend running on port ${backendPort}`, 'success');
          updateBackendStatus('Running', `Backend ready on :${backendPort}`);
        }
      } catch {
        logToTerminal(`[backend] ${line}`, 'info');
      }
    });

    cmd.stderr.on('data', line => {
      logToTerminal(`[backend:stderr] ${line}`, 'error');
    });

    await cmd.spawn();

  } catch (error) {
    logToTerminal(`Failed to start backend: ${error.message}`, 'error');
    updateBackendStatus('Failed', 'Failed to start');
  }
}

// --- HTTP API CALLS ---
async function fetchJSON(path, opts = {}) {
  if (!backendPort) {
    throw new Error('Backend not ready. Please wait for backend to start.');
  }

  const url = `http://127.0.0.1:${backendPort}${path}`;
  logToTerminal(`→ ${opts.method || 'GET'} ${path}`, 'info');

  try {
    const res = await fetch(url, opts);
    const j = await res.json();

    if (!res.ok) {
      throw new Error(j.error || j.stderr || `HTTP ${res.status}: Request failed`);
    }

    logToTerminal(`← ${path} completed successfully`, 'success');
    return j;
  } catch (error) {
    logToTerminal(`← ${path} failed: ${error.message}`, 'error');
    throw error;
  }
}

// --- DRIVER STATUS CHECK ---
async function refreshDrivers() {
  try {
    logToTerminal('Checking driver status...', 'info');
    const d = await fetchJSON('/drivers');

    if (!d.windows) {
      updateDriversStatus('N/A', 'Windows only');
      logToTerminal('Drivers are Windows-only', 'warning');
      return;
    }

    const interceptionOk = d.interception === true;
    const vjoyOk = d.vjoy === true;
    const allOk = interceptionOk && vjoyOk;

    if (allOk) {
      updateDriversStatus('OK ✓', 'All OK ✓');
      logToTerminal('✓ All drivers installed', 'success');
    } else {
      const missing = [];
      if (!interceptionOk) missing.push('Interception');
      if (!vjoyOk) missing.push('vJoy');

      updateDriversStatus('Missing', `Missing: ${missing.join(', ')}`);
      logToTerminal(`⚠ Missing drivers: ${missing.join(', ')}`, 'warning');
    }

  } catch (error) {
    updateDriversStatus('Unknown', 'Check failed');
    logToTerminal(`Driver check failed: ${error.message}`, 'warning');
  }
}

// --- BUTTON HANDLERS ---

// TEACH: Toggle Recording
window.toggleRecord = async function(btn) {
  isRecording = !isRecording;
  const status = document.getElementById('record-status');

  if (isRecording) {
    try {
      logToTerminal('Starting data collection...', 'info');
      btn.disabled = true;

      const result = await fetchJSON('/action/collect', { method: 'POST' });

      btn.innerHTML = "<span>■</span> Stop Recording";
      btn.style.background = "#333";
      if (status) {
        status.innerText = "🔴 Recording... Switch to game window!";
        status.style.color = "#FF5252";
      }
      logToTerminal('✓ Recording started', 'success');
      btn.disabled = false;
    } catch (error) {
      logToTerminal(`Failed to start recording: ${error.message}`, 'error');
      isRecording = false;
      btn.disabled = false;
    }
  } else {
    try {
      btn.disabled = true;
      const result = await fetchJSON('/stop', { method: 'POST' });

      btn.innerHTML = "<span>●</span> Start Recording";
      btn.style.background = "var(--accent)";
      if (status) {
        status.innerText = "✓ Recording saved to /data";
        status.style.color = "var(--success)";
      }
      logToTerminal('✓ Recording stopped and saved', 'success');
      btn.disabled = false;
    } catch (error) {
      logToTerminal(`Failed to stop recording: ${error.message}`, 'error');
      btn.disabled = false;
    }
  }
};

// TRAIN: Start Training
window.startTraining = async function() {
  const terminal = document.getElementById('terminal');
  const progressBar = document.getElementById('progress-bar');
  const pctDisplay = document.getElementById('train-pct');
  const btn = document.getElementById('btnStartTraining');

  try {
    logToTerminal('===========================================', 'info');
    logToTerminal('Starting neural network training...', 'info');
    logToTerminal('===========================================', 'info');

    if (btn) btn.disabled = true;
    if (progressBar) progressBar.style.width = "0%";
    if (pctDisplay) pctDisplay.textContent = "0%";

    const result = await fetchJSON('/action/train', { method: 'POST' });

    if (result.stdout) {
      const lines = result.stdout.split('\n');
      lines.forEach(line => {
        if (line.trim()) {
          logToTerminal(line, 'info');

          // Update progress if we detect epoch info
          const epochMatch = line.match(/Epoch (\d+)\/(\d+)/);
          if (epochMatch && progressBar && pctDisplay) {
            const current = parseInt(epochMatch[1]);
            const total = parseInt(epochMatch[2]);
            const percent = Math.round((current / total) * 100);
            progressBar.style.width = percent + '%';
            pctDisplay.textContent = percent + '%';
          }
        }
      });
    }

    if (progressBar) progressBar.style.width = "100%";
    if (pctDisplay) pctDisplay.textContent = "100%";

    logToTerminal('===========================================', 'success');
    logToTerminal('✓ Training completed successfully!', 'success');
    logToTerminal('===========================================', 'success');

  } catch (error) {
    logToTerminal(`✗ Training failed: ${error.message}`, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
};

// TRAIN: Analyze Logs
window.analyzeLogs = async function() {
  const terminal = document.getElementById('terminal');
  const resultBox = document.getElementById('log-analysis-result');
  const resultText = document.getElementById('analysis-text');
  const btn = document.getElementById('btnAnalyzeLogs');

  if (!terminal) return;

  const logs = terminal.innerText;
  if (logs.length < 20) {
    alert("Not enough logs to analyze! Run training first.");
    return;
  }

  try {
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = "Analyzing...";
    }

    // Simple analysis based on logs
    let analysis = "Analysis: ";

    if (logs.includes('completed successfully')) {
      analysis += "Training completed successfully! ✓ ";
    }

    if (logs.includes('100%')) {
      analysis += "Model training reached 100%. ";
    }

    if (logs.includes('error') || logs.includes('failed')) {
      analysis += "⚠ Some errors detected in logs. Review carefully. ";
    }

    const epochMatches = logs.match(/Epoch \d+\/\d+/g);
    if (epochMatches && epochMatches.length > 0) {
      analysis += `Found ${epochMatches.length} training epochs. `;
    }

    if (analysis === "Analysis: ") {
      analysis = "Logs appear normal. Continue monitoring for any issues.";
    }

    if (resultBox && resultText) {
      resultText.textContent = analysis;
      resultBox.style.display = "block";
    }

    logToTerminal('Log analysis completed', 'info');

  } catch (error) {
    logToTerminal(`Analysis failed: ${error.message}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span>✨</span> Analyze Logs';
    }
  }
};

// RUN: Toggle Bot
window.toggleBot = async function(btn) {
  isRunning = !isRunning;

  if (isRunning) {
    try {
      logToTerminal('Starting bot automation...', 'info');
      btn.disabled = true;

      const result = await fetchJSON('/action/play', { method: 'POST' });

      btn.innerText = "■ STOP BOT";
      btn.style.background = "var(--accent)";
      btn.style.color = "white";
      logToTerminal('✓ Bot started successfully', 'success');
      btn.disabled = false;
    } catch (error) {
      logToTerminal(`Failed to start bot: ${error.message}`, 'error');
      isRunning = false;
      btn.disabled = false;
    }
  } else {
    try {
      btn.disabled = true;
      const result = await fetchJSON('/stop', { method: 'POST' });

      btn.innerText = "▶ START BOT";
      btn.style.background = "var(--success)";
      btn.style.color = "black";
      logToTerminal('✓ Bot stopped', 'success');
      btn.disabled = false;
    } catch (error) {
      logToTerminal(`Failed to stop bot: ${error.message}`, 'error');
      btn.disabled = false;
    }
  }
};

// RUN: Install Drivers
window.installDrivers = async function() {
  const btn = document.getElementById('btnInstallDrivers');

  try {
    logToTerminal('Installing/checking drivers...', 'info');
    if (btn) btn.disabled = true;

    const result = await fetchJSON('/install', { method: 'POST' });

    if (result.stdout) {
      const lines = result.stdout.split('\n');
      lines.forEach(line => {
        if (line.trim()) logToTerminal(line, 'info');
      });
    }

    logToTerminal('✓ Driver installation completed', 'success');

    // Refresh driver status
    await refreshDrivers();

  } catch (error) {
    logToTerminal(`Driver installation failed: ${error.message}`, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
};

// AI STRATEGIST: Send Chat Message
window.sendChatMessage = async function() {
  const input = document.getElementById('chat-input');
  const history = document.getElementById('chat-history');
  const spinner = document.getElementById('chat-spinner');
  const btn = document.getElementById('btnSendChat');

  if (!input || !history) return;

  const msg = input.value.trim();
  if (!msg) return;

  // User bubble
  const userBubble = document.createElement('div');
  userBubble.className = 'chat-bubble bubble-user';
  userBubble.textContent = msg;
  history.appendChild(userBubble);

  input.value = "";
  history.scrollTop = history.scrollHeight;

  if (spinner) spinner.style.display = "block";
  if (btn) btn.disabled = true;

  try {
    // Note: In Tauri, we don't have direct Gemini API access like in the Launcher
    // This is a simplified response. You could enhance this by:
    // 1. Adding Gemini API key to backend and proxying requests
    // 2. Using a local AI model
    // 3. Creating predefined responses

    const response = await generateAIResponse(msg);

    const aiBubble = document.createElement('div');
    aiBubble.className = 'chat-bubble bubble-ai';
    aiBubble.innerHTML = response;
    history.appendChild(aiBubble);

    history.scrollTop = history.scrollHeight;

  } catch (error) {
    const errorBubble = document.createElement('div');
    errorBubble.className = 'chat-bubble bubble-ai';
    errorBubble.textContent = `Error: ${error.message}`;
    history.appendChild(errorBubble);

    logToTerminal(`Chat error: ${error.message}`, 'error');
  } finally {
    if (spinner) spinner.style.display = "none";
    if (btn) btn.disabled = false;
  }
};

// Simple AI response generator (placeholder - replace with actual API call)
async function generateAIResponse(message) {
  const lowerMsg = message.toLowerCase();

  // Predefined responses for common questions
  if (lowerMsg.includes('farming') || lowerMsg.includes('route')) {
    return "For optimal farming routes, I recommend:\n• Start by recording a simple route in the <b>Teach</b> tab\n• Train the model with at least 1000 frames\n• Test on easier content first before moving to harder dungeons\n• Always monitor the first few runs manually";
  }

  if (lowerMsg.includes('train') || lowerMsg.includes('model')) {
    return "Training tips:\n• Collect diverse gameplay data (different times of day, angles)\n• Aim for 5000+ frames for good results\n• Use the <b>Analyze Logs</b> button to check training quality\n• More data = better bot performance";
  }

  if (lowerMsg.includes('driver') || lowerMsg.includes('install')) {
    return "Driver installation:\n• Click <b>🔧 Drivers</b> button in the Run tab\n• Interception driver allows keyboard/mouse control\n• vJoy driver enables virtual gamepad\n• Both are required for full bot functionality\n• Restart may be needed after installation";
  }

  if (lowerMsg.includes('safe') || lowerMsg.includes('ban')) {
    return "Safety considerations:\n• Enable HP check and auto-eat in safety settings\n• Start with short sessions (30 min) and monitor\n• Avoid obvious patterns (randomize actions slightly)\n• Never leave completely unattended\n• Use at your own risk - this is for educational purposes";
  }

  if (lowerMsg.includes('start') || lowerMsg.includes('begin') || lowerMsg.includes('how')) {
    return "Getting started:\n1. <b>Dashboard</b>: Check backend and drivers status\n2. <b>Teach</b>: Record your gameplay (collect data)\n3. <b>Train</b>: Train AI model on collected data\n4. <b>Run</b>: Start the bot with trained model\n5. Monitor the first runs carefully!";
  }

  // Default response
  return "I'm here to help with bot configuration and strategy! You can ask me about:\n• Farming routes and optimization\n• Training your AI model\n• Driver installation\n• Safety settings\n• Getting started\n\n<i>Note: AI features are limited in the desktop app. For full AI capabilities including Gemini integration, use the Launcher (launcher.py)</i>";
}

// AI STRATEGIST: Handle Enter Key
window.handleChatEnter = function(e) {
  if (e.key === 'Enter') {
    sendChatMessage();
  }
};

// --- INITIALIZATION ---
async function init() {
  logToTerminal('═══════════════════════════════════════', 'info');
  logToTerminal('BOT MMORPG AI v0.1.5', 'info');
  logToTerminal('Intelligent Game Automation System', 'info');
  logToTerminal('═══════════════════════════════════════', 'info');

  // Start backend
  await startBackend();

  // Wait for backend to initialize
  await new Promise(r => setTimeout(r, 1000));

  // Check if backend is ready
  if (!backendPort) {
    logToTerminal('⚠ Backend did not start properly', 'error');
    logToTerminal('Troubleshooting:', 'warning');
    logToTerminal('  1. Check if another instance is running', 'warning');
    logToTerminal('  2. Check if Python is installed correctly', 'warning');
    logToTerminal('  3. Try restarting the application', 'warning');
    updateBackendStatus('Failed', 'Backend failed to start');
    return;
  }

  // Initial driver status check
  await refreshDrivers();

  logToTerminal('═══════════════════════════════════════', 'info');
  logToTerminal('✓ Application ready!', 'success');
  logToTerminal('Use the sidebar to navigate between tabs', 'info');
  logToTerminal('═══════════════════════════════════════', 'info');
}

// Start the application
init().catch(error => {
  logToTerminal(`Initialization failed: ${error.message}`, 'error');
  updateBackendStatus('Failed', 'Init failed');
});

/* Patch override: installDrivers via Tauri invoke */
function installDrivers() {
  const log = document.getElementById("logOutput");
  if (log) log.textContent += "\n[Drivers] Starting driver installation...";
  return invoke("install_drivers")
    .then((res) => {
      if (log) log.textContent += "\n[Drivers] " + (res?.message || JSON.stringify(res));
      return res;
    })
    .catch((err) => {
      if (log) log.textContent += "\n[Drivers][ERROR] " + (err?.toString?.() || JSON.stringify(err));
      throw err;
    });
}
