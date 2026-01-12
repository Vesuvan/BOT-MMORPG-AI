// State & Tauri Globals
const invoke = window.__TAURI__ ? window.__TAURI__.invoke : null;
const listen = window.__TAURI__ ? window.__TAURI__.event.listen : null;

// Global State
let isRecording = false;
let isBotRunning = false;

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
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.remove('active');
        el.style.display = ''; // Clear inline display style
    });

    // Show selected tab
    const selectedTab = document.getElementById('tab-' + tabId);
    if (selectedTab) {
        selectedTab.classList.add('active');
        // Handle flex layouts for specific tabs
        if(tabId === 'teach' || tabId === 'train') {
            selectedTab.style.display = 'flex';
        } else {
            selectedTab.style.display = 'block';
        }
    }

    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
    const selectedBtn = document.getElementById('btn-' + tabId) || 
                        document.querySelector(`button[data-tab="${tabId}"]`);
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
    entry.className = `log-entry log-${type}`;
    entry.innerHTML = `<span class="log-time">[${timestamp}]</span> ${msg}`;

    terminal.appendChild(entry);
    terminal.scrollTop = terminal.scrollHeight;

    // Keep last 100 entries to prevent memory bloat
    const entries = terminal.querySelectorAll('.log-entry');
    if (entries.length > 200) {
        entries[0].remove();
    }
}

// Global hook for terminal updates from Rust
window.update_terminal = function(line) {
    logToTerminal(line, 'info');
    
    // Parse progress for Training
    if (line.includes('Epoch')) {
        const match = line.match(/Epoch (\d+)\/(\d+)/);
        if (match) {
            const current = parseInt(match[1]);
            const total = parseInt(match[2]);
            const percent = Math.round((current / total) * 100);
            
            const progressBar = document.getElementById('progress-bar');
            const pctDisplay = document.getElementById('train-pct');
            
            if(progressBar) progressBar.style.width = percent + '%';
            if(pctDisplay) pctDisplay.textContent = percent + '%';
        }
    }
};

// --- BACKEND STATUS ---
function updateBackendStatus(status, message) {
    const statusText = document.getElementById('backend-status');
    const statusBadge = document.getElementById('backend-status-badge');
    const footerText = document.getElementById('backend-status-text');

    if (statusText) statusText.textContent = message;
    if (statusBadge) statusBadge.textContent = status;
    if (footerText) footerText.textContent = status === 'Running' ? 'System Online' : 'System Offline';
    
    // Update dot color in footer
    const dot = document.querySelector('.status-dot');
    if(dot) dot.style.backgroundColor = status === 'Running' ? 'var(--success)' : 'var(--accent)';
}

// --- BUTTON HANDLERS (Linked to Rust Commands) ---

// TEACH: Toggle Recording
window.toggleRecord = async function(btn) {
    if (!invoke) return alert("Tauri backend not found.");
    
    isRecording = !isRecording;
    const status = document.getElementById('record-status');

    if (isRecording) {
        try {
            logToTerminal('Requesting recording start...', 'info');
            btn.disabled = true;
            
            const res = await invoke('start_recording');
            logToTerminal(res, 'success');

            btn.innerHTML = "<span>■</span> Stop Recording";
            btn.style.background = "#333";
            if (status) {
                status.innerText = "🔴 Recording... Switch to game window!";
                status.style.color = "#FF5252";
            }
        } catch (err) {
            logToTerminal(`Error starting recording: ${err}`, 'error');
            isRecording = false;
        } finally {
            btn.disabled = false;
        }
    } else {
        try {
            btn.disabled = true;
            const res = await invoke('stop_process');
            logToTerminal(res, 'success');

            btn.innerHTML = "<span>●</span> Start Recording";
            btn.style.background = "var(--accent)";
            if (status) {
                status.innerText = "✓ Recording saved.";
                status.style.color = "var(--success)";
            }
        } catch (err) {
            logToTerminal(`Error stopping recording: ${err}`, 'error');
        } finally {
            btn.disabled = false;
        }
    }
};

// TRAIN: Start Training
window.startTraining = async function() {
    if (!invoke) return alert("Tauri backend not found.");
    
    const progressBar = document.getElementById('progress-bar');
    const pctDisplay = document.getElementById('train-pct');
    const btn = document.getElementById('btnStartTraining');

    try {
        logToTerminal('-------------------------------------------', 'info');
        logToTerminal('Initializing Neural Network Training...', 'info');
        
        if (btn) btn.disabled = true;
        if (progressBar) progressBar.style.width = "0%";
        if (pctDisplay) pctDisplay.textContent = "0%";

        const res = await invoke('start_training');
        logToTerminal(res, 'success'); // "Training initialized..."

    } catch (err) {
        logToTerminal(`Training failed to start: ${err}`, 'error');
        if (btn) btn.disabled = false;
    }
};

// TRAIN: Analyze Logs (Mock / Local Logic)
window.analyzeLogs = async function() {
    const terminal = document.getElementById('terminal');
    const resultBox = document.getElementById('log-analysis-result');
    const resultText = document.getElementById('analysis-text');
    
    if (!terminal) return;
    const logs = terminal.innerText;
    
    if (logs.length < 50) {
        alert("Not enough logs to analyze. Please run training first.");
        return;
    }

    if (resultText) resultText.textContent = "Analyzing local logs...";
    if (resultBox) resultBox.style.display = "block";

    // Simple heuristic analysis since we don't have Gemini in this pure Tauri JS context easily
    // (Unless you add a command for it in Rust, or use the JS shim from index.html)
    setTimeout(() => {
        let analysis = "Log Analysis: \n";
        const epochCount = (logs.match(/Epoch/g) || []).length;
        const lossMatches = logs.match(/loss: (\d+\.\d+)/g);
        
        if (epochCount > 0) {
            analysis += `• Found ${epochCount} training epochs.\n`;
        } else {
            analysis += "• No training epochs detected yet.\n";
        }

        if (logs.includes("Error") || logs.includes("Exception")) {
            analysis += "• ⚠️ Errors detected in logs. Please review.\n";
        } else {
            analysis += "• System appears stable.\n";
        }

        if (resultText) resultText.textContent = analysis;
    }, 1000);
};

// RUN: Toggle Bot
window.toggleBot = async function(btn) {
    if (!invoke) return alert("Tauri backend not found.");
    
    isBotRunning = !isBotRunning;

    if (isBotRunning) {
        try {
            logToTerminal('Initializing autonomous bot...', 'info');
            btn.disabled = true;
            
            const res = await invoke('start_bot');
            logToTerminal(res, 'success');

            btn.innerText = "■ STOP BOT";
            btn.style.background = "var(--accent)";
            btn.style.color = "white";
        } catch (err) {
            logToTerminal(`Failed to start bot: ${err}`, 'error');
            isBotRunning = false;
        } finally {
            btn.disabled = false;
        }
    } else {
        try {
            btn.disabled = true;
            const res = await invoke('stop_process');
            logToTerminal(res, 'success');

            btn.innerText = "▶ START BOT";
            btn.style.background = "var(--success)";
            btn.style.color = "black";
        } catch (err) {
            logToTerminal(`Failed to stop bot: ${err}`, 'error');
        } finally {
            btn.disabled = false;
        }
    }
};

// RUN: Install Drivers (Mock / Rust Command Placeholder)
window.installDrivers = async function() {
    logToTerminal('Checking drivers...', 'info');
    // In a real scenario, you'd add an `install_drivers` command to Rust
    setTimeout(() => {
        logToTerminal('ℹ Driver installation requires manual setup in this version.', 'warning');
        logToTerminal('Please ensure Interception and vJoy are installed.', 'info');
        document.getElementById('drivers-status').textContent = "Check Manual";
    }, 1000);
};

// AI STRATEGIST: Chat (Mock for UI Demo)
window.sendChatMessage = async function() {
    const input = document.getElementById('chat-input');
    const history = document.getElementById('chat-history');
    const spinner = document.getElementById('chat-spinner');
    
    if (!input || !history) return;
    const msg = input.value.trim();
    if (!msg) return;

    // User Bubble
    const userBubble = document.createElement('div');
    userBubble.className = 'chat-bubble bubble-user';
    userBubble.textContent = msg;
    history.appendChild(userBubble);

    input.value = "";
    history.scrollTop = history.scrollHeight;
    
    if (spinner) spinner.style.display = "block";

    // Simulate AI Delay
    setTimeout(() => {
        if (spinner) spinner.style.display = "none";
        
        const aiBubble = document.createElement('div');
        aiBubble.className = 'chat-bubble bubble-ai';
        aiBubble.innerHTML = "I am ready to help! <br><i>(Note: Full Gemini integration requires configuring the API key in the Rust backend settings)</i>";
        history.appendChild(aiBubble);
        history.scrollTop = history.scrollHeight;
    }, 1500);
};

window.handleChatEnter = function(e) {
    if (e.key === 'Enter') window.sendChatMessage();
};

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
    // 1. Initial Logging
    logToTerminal('═══════════════════════════════════════', 'info');
    logToTerminal('BOT MMORPG AI v0.1.5 (Tauri Edition)', 'info');
    logToTerminal('Initializing Rust Core...', 'info');
    
    if (invoke) {
        updateBackendStatus('Running', 'Rust Backend Active');
        logToTerminal('✓ Tauri Backend Connected', 'success');
        
        // 2. Load Config (API Keys)
        invoke('get_ai_config').then(config => {
            logToTerminal(`Loaded Config. Provider: ${config.provider}`, 'info');
            // Logic to update Settings UI would go here if settings modal is open
        }).catch(err => {
            logToTerminal(`Config Load Warning: ${err}`, 'warning');
        });

    } else {
        updateBackendStatus('Error', 'Tauri Not Found');
        logToTerminal('⚠ Tauri API not detected. Is this running in a browser?', 'error');
    }

    // 3. Wire up Event Listeners
    wireEvents();
});

function wireEvents() {
    // Navigation
    document.querySelectorAll("button[data-tab]").forEach(btn => {
        btn.addEventListener("click", () => {
            const tab = btn.getAttribute("data-tab");
            if (tab) window.showTab(tab);
        });
    });

    // Action Buttons
    const bind = (id, func) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("click", () => func(el));
    };

    bind("btnRecord", window.toggleRecord);
    bind("btnStartTraining", window.startTraining);
    bind("btnAnalyzeLogs", window.analyzeLogs);
    bind("btnStartBot", window.toggleBot);
    bind("btnInstallDrivers", window.installDrivers);
    bind("btnSendChat", window.sendChatMessage);
    
    // Quick Start Button
    bind("nav-teach", () => window.showTab('teach'));
}