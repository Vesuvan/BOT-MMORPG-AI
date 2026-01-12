import { Command } from '@tauri-apps/api/shell';
import { invoke } from '@tauri-apps/api/tauri';

const out = document.getElementById('out');
const backendTag = document.getElementById('backend');
const driversTag = document.getElementById('drivers');

function log(msg) {
  out.textContent = (out.textContent + msg + "\n").slice(-20000);
}

let backendPort = null;

async function startBackend() {
  // Sidecar name must match tauri.conf.json externalBin entry (without extension).
  const cmd = Command.sidecar('binaries/main-backend');
  cmd.on('close', data => log(`[backend] exited: code=${data.code} signal=${data.signal}`));
  cmd.on('error', err => log(`[backend] error: ${JSON.stringify(err)}`));
  cmd.stdout.on('data', line => {
    // backend prints a JSON line with port info
    try {
      const j = JSON.parse(line);
      if (j.port) backendPort = j.port;
      backendTag.textContent = backendPort ? `running :${backendPort}` : 'running';
    } catch {
      log(`[backend] ${line}`);
    }
  });
  cmd.stderr.on('data', line => log(`[backend:stderr] ${line}`));

  await cmd.spawn();
  backendTag.textContent = 'running';
}

async function fetchJSON(path, opts) {
  if (!backendPort) throw new Error('Backend port not set yet');
  const res = await fetch(`http://127.0.0.1:${backendPort}${path}`, opts);
  const j = await res.json();
  if (!res.ok) throw new Error(j.error || j.stderr || 'Request failed');
  return j;
}

async function refreshDrivers() {
  try {
    const d = await fetchJSON('/drivers');
    const ok = (d.interception === true) && (d.vjoy === true);
    driversTag.textContent = ok ? 'ok' : `interception=${d.interception} vjoy=${d.vjoy}`;
  } catch (e) {
    driversTag.textContent = 'unknown';
  }
}

document.getElementById('btnInstall').addEventListener('click', async () => {
  log('[ui] requesting driver install…');
  // Uses Rust command to run elevated PowerShell from bundled resources.
  const r = await invoke('install_drivers');
  log(`[install] ${JSON.stringify(r)}`);
  await refreshDrivers();
});

for (const [id, action] of [
  ['btnCollect', 'collect'],
  ['btnTrain', 'train'],
  ['btnPlay', 'play'],
]) {
  document.getElementById(id).addEventListener('click', async () => {
    log(`[ui] action ${action}…`);
    try {
      const r = await fetchJSON(`/action/${action}`, { method: 'POST' });
      log(r.stdout || '[ok]');
      if (r.stderr) log(r.stderr);
    } catch (e) {
      log(`[error] ${e.message}`);
    }
  });
}

await startBackend();
await new Promise(r => setTimeout(r, 600));
await refreshDrivers();
