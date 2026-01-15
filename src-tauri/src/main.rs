// src-tauri/src/main.rs
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use std::fs;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use reqwest::Client;
use tauri::{AppHandle, Manager, Window};

// ---------------------------
// CONSTANTS / DEFAULTS
// ---------------------------
const DEFAULT_GAME_ID: &str = "genshin_impact";
const SCRIPTS_DIR_REL: &str = "versions/0.01";

// ---------------------------
// APP STATE (Arc inner + SidecarApi stored there)
// ---------------------------

#[derive(Clone, Debug)]
struct SidecarApi {
    base_url: String,
    token: String,
}

struct AppStateInner {
    current_process: Mutex<Option<Child>>,
    sidecar: Mutex<Option<SidecarApi>>,
    http: Client,
}

#[derive(Clone)]
struct AppState {
    inner: Arc<AppStateInner>,
}

#[derive(Serialize, Deserialize)]
struct AiConfig {
    provider: String,
    gemini_key: String,
    openai_key: String,
}

// ---------------------------
// CONFIG (.env) HELPERS
// ---------------------------

fn env_file_path(app: &AppHandle) -> PathBuf {
    // dev convenience: ../.env
    if cfg!(debug_assertions) {
        if let Ok(cwd) = std::env::current_dir() {
            let candidate = cwd.join("..").join(".env");
            if candidate.exists() {
                return candidate;
            }
        }
    }

    // production-safe
    let cfg_dir = app
        .path_resolver()
        .app_config_dir()
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));

    let _ = fs::create_dir_all(&cfg_dir);
    cfg_dir.join(".env")
}

fn ensure_default_env(app: &AppHandle) {
    let path = env_file_path(app);
    if path.exists() {
        return;
    }
    let default_content = "AI_PROVIDER=\"gemini\"\nGEMINI_API_KEY=\"\"\nOPENAI_API_KEY=\"\"\n";
    let _ = fs::write(path, default_content);
}

fn get_env_var(app: &AppHandle, key: &str) -> String {
    ensure_default_env(app);
    let env_path = env_file_path(app);
    let content = fs::read_to_string(&env_path).unwrap_or_default();

    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((k, v)) = line.split_once('=') {
            if k.trim() == key {
                let mut value = v.trim().to_string();
                if (value.starts_with('"') && value.ends_with('"'))
                    || (value.starts_with('\'') && value.ends_with('\''))
                {
                    value = value[1..value.len() - 1].to_string();
                }
                return value;
            }
        }
    }
    String::new()
}

fn update_env_file(app: &AppHandle, key: &str, value: &str) -> Result<(), String> {
    ensure_default_env(app);
    let env_path = env_file_path(app);

    let mut lines: Vec<String> = fs::read_to_string(&env_path)
        .unwrap_or_default()
        .lines()
        .map(|s| s.to_string())
        .collect();

    let mut found = false;
    for line in lines.iter_mut() {
        if let Some((k, _)) = line.split_once('=') {
            if k.trim() == key {
                *line = format!("{}=\"{}\"", key, value.replace('"', "\\\""));
                found = true;
                break;
            }
        }
    }
    if !found {
        lines.push(format!("{}=\"{}\"", key, value.replace('"', "\\\"")));
    }

    fs::write(&env_path, lines.join("\n") + "\n").map_err(|e| e.to_string())
}

// ---------------------------
// UTILS
// ---------------------------

fn normalize_game_id(game_id: Option<String>) -> String {
    let gid = game_id.unwrap_or_default().trim().to_string();
    if gid.is_empty() {
        DEFAULT_GAME_ID.to_string()
    } else {
        gid
    }
}

fn scripts_dir_path(app: &AppHandle) -> PathBuf {
    let resolved = app.path_resolver().resolve_resource(SCRIPTS_DIR_REL);
    resolved.unwrap_or_else(|| PathBuf::from(format!("../{}", SCRIPTS_DIR_REL)))
}

fn python_interpreter() -> &'static str {
    if cfg!(target_os = "windows") {
        "python"
    } else {
        "python3"
    }
}

// Repo root helper:
// - In dev, current_dir is usually .../src-tauri, so parent() is repo root.
// - If that fails, fallback to "..".
fn dev_repo_root() -> PathBuf {
    std::env::current_dir()
        .ok()
        .and_then(|p| p.parent().map(|x| x.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from(".."))
}

// ---------------------------
// SIDE-CAR (modelhub/tauri.py) STARTUP
// ---------------------------

fn start_sidecar_server(app: &AppHandle) -> Result<SidecarApi, String> {
    let token = {
        let pid = std::process::id();
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        format!("tkn-{}-{}", pid, now)
    };

    let mut cmd = if cfg!(debug_assertions) {
        // ✅ robust path: anchor to repo root, NOT CWD-dependent
        let root = dev_repo_root();
        let script_a = root.join("modelhub").join("tauri.py");
        let script_b = root.join("backend").join("main_backend.py");
        let script = if script_a.exists() { script_a } else { script_b };

        let mut c = Command::new(python_interpreter());
        c.arg(script);
        c
    } else {
        // Production sidecar binary name (you can change to your packaged sidecar exe)
        Command::new("main-backend")
    };

    let project_root = if cfg!(debug_assertions) {
        dev_repo_root()
    } else {
        app.path_resolver().app_config_dir().unwrap_or_else(|| {
            std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
        })
    };

    // NOTE:
    // In your python sidecar you showed, it expects "--port" and "--token" and "--project-root".
    // It does NOT require "--serve". Passing unknown flags will break startup.
    cmd.args([
        "--port",
        "0",
        "--token",
        &token,
        "--project-root",
        &project_root.to_string_lossy(),
    ]);

    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    let mut child = cmd.spawn().map_err(|e| format!("Failed to start sidecar: {e}"))?;
    let stdout = child
        .stdout
        .take()
        .ok_or("Sidecar stdout unavailable".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or("Sidecar stderr unavailable".to_string())?;

    let (tx, rx) = std::sync::mpsc::channel::<Result<SidecarApi, String>>();

    // stdout thread: look for READY line
    let tx_out = tx.clone();
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines().flatten() {
            if let Some(api) = parse_ready_line(&line) {
                let _ = tx_out.send(Ok(api));
                return;
            }
        }
        let _ = tx_out.send(Err(
            "Sidecar exited without READY line (stdout)".to_string(),
        ));
    });

    // stderr thread: forward lines to UI and detect FAILED
    let app_handle = app.clone();
    let tx_err = tx.clone();
    thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines().flatten() {
            if let Some(w) = app_handle.get_window("main") {
                let _ = w.emit::<String>("terminal_update", format!("[Sidecar stderr] {}", line));
            }
            if line.starts_with("FAILED ") {
                let _ = tx_err.send(Err(format!("Sidecar failed: {}", line)));
                return;
            }
        }
    });

    let timeout = Duration::from_secs(25);
    match rx.recv_timeout(timeout) {
        Ok(Ok(api)) => {
            // Keep child alive by storing it nowhere? In this design the child will live
            // as long as the process keeps running. If you need to stop it explicitly,
            // store it in state similar to current_process.
            let _ = child;
            Ok(api)
        }
        Ok(Err(e)) => Err(e),
        Err(_) => Err("Timed out waiting for sidecar READY line".to_string()),
    }
}

fn parse_ready_line(line: &str) -> Option<SidecarApi> {
    let line = line.trim();
    if !line.starts_with("READY ") {
        return None;
    }
    let mut url: Option<String> = None;
    let mut token: Option<String> = None;
    for part in line.split_whitespace() {
        if let Some(v) = part.strip_prefix("url=") {
            url = Some(v.to_string());
        } else if let Some(v) = part.strip_prefix("token=") {
            token = Some(v.to_string());
        }
    }
    match (url, token) {
        (Some(base_url), Some(token)) => Some(SidecarApi { base_url, token }),
        _ => None,
    }
}

// ---------------------------
// HTTP CALL HELPERS
// ---------------------------

async fn api_get_with(inner: &Arc<AppStateInner>, path: &str) -> Result<Value, String> {
    let api = inner
        .sidecar
        .lock()
        .unwrap()
        .clone()
        .ok_or_else(|| "Sidecar API not ready".to_string())?;

    let url = format!("{}{}", api.base_url, path);

    let res = inner
        .http
        .get(url)
        .header("X-Auth-Token", api.token)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let status = res.status();
    let body = res.json::<Value>().await.map_err(|e| e.to_string())?;

    if !status.is_success() {
        return Err(body.to_string());
    }
    Ok(body)
}

async fn api_post_with(inner: &Arc<AppStateInner>, path: &str, payload: Value) -> Result<Value, String> {
    let api = inner
        .sidecar
        .lock()
        .unwrap()
        .clone()
        .ok_or_else(|| "Sidecar API not ready".to_string())?;

    let url = format!("{}{}", api.base_url, path);

    let res = inner
        .http
        .post(url)
        .header("X-Auth-Token", api.token)
        .json(&payload)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let status = res.status();
    let body = res.json::<Value>().await.map_err(|e| e.to_string())?;

    if !status.is_success() {
        return Err(body.to_string());
    }
    Ok(body)
}

// ---------------------------
// PROCESS MANAGEMENT
// ---------------------------

fn ensure_monitor_thread(app: AppHandle, window: Window, inner: Arc<AppStateInner>) {
    thread::spawn(move || loop {
        thread::sleep(Duration::from_millis(250));

        let mut maybe_exit_code: Option<i32> = None;
        {
            let mut guard = inner.current_process.lock().unwrap();
            if let Some(child) = guard.as_mut() {
                match child.try_wait() {
                    Ok(Some(status)) => {
                        maybe_exit_code = status.code();
                        let _ = guard.take();
                    }
                    Ok(None) => {}
                    Err(_) => {
                        let _ = guard.take();
                    }
                }
            }
        }

        if let Some(code) = maybe_exit_code {
            let inner2 = inner.clone();
            let window2 = window.clone();
            tauri::async_runtime::spawn(async move {
                let _ = api_post_with(&inner2, "/session/finalize", json!({})).await;
                let _ = window2.emit("process_finished", format!("exit_code={}", code));
            });
        }

        let _ = app;
    });
}

fn stop_process_inner(window: &Window, inner: &Arc<AppStateInner>) -> String {
    let mut guard = inner.current_process.lock().unwrap();
    if let Some(mut child) = guard.take() {
        let _ = window.emit("terminal_update", format!("[System] Stopping PID {}", child.id()));
        let _ = child.kill();
        return "Process stopped".to_string();
    }
    "No process running".to_string()
}

fn run_python_script(
    app: AppHandle,
    script_name: &str,
    window: Window,
    inner: Arc<AppStateInner>,
) -> Result<String, String> {
    // ✅ exists-checked path selection:
    // 1) use Tauri resource if it exists
    // 2) else dev repo_root/versions/0.01/<script>
    // 3) else show best-effort path for debugging
    let resource_path = app
        .path_resolver()
        .resolve_resource(format!("{}/{}", SCRIPTS_DIR_REL, script_name));

    let dev_candidate = dev_repo_root().join(SCRIPTS_DIR_REL).join(script_name);

    let script_path = match resource_path {
        Some(p) if p.exists() => p,
        _ if dev_candidate.exists() => dev_candidate,
        Some(p) => p, // keep for debug display
        None => PathBuf::from(format!("{}/{}", SCRIPTS_DIR_REL, script_name)),
    };

    // Run with script’s parent as cwd (more reliable than target/debug/... guessing)
    let scripts_dir = script_path
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| scripts_dir_path(&app));

    let _ = window.emit("terminal_update", format!("[System] Script: {}", script_path.display()));
    let _ = window.emit("terminal_update", format!("[System] CWD: {}", scripts_dir.display()));

    if !script_path.exists() {
        let msg = format!("Error: Script not found at {}", script_path.display());
        let _ = window.emit("terminal_update", msg.clone());
        return Err(msg);
    }

    let _ = stop_process_inner(&window, &inner);

    let mut cmd = Command::new(python_interpreter());
    cmd.arg(&script_path);
    cmd.current_dir(&scripts_dir);

    let provider = {
        let p = get_env_var(&app, "AI_PROVIDER");
        if p.is_empty() {
            "gemini".to_string()
        } else {
            p
        }
    };
    let gemini_key = get_env_var(&app, "GEMINI_API_KEY");
    let openai_key = get_env_var(&app, "OPENAI_API_KEY");

    cmd.env("AI_PROVIDER", provider);
    cmd.env("GEMINI_API_KEY", gemini_key);
    cmd.env("OPENAI_API_KEY", openai_key);

    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    match cmd.spawn() {
        Ok(mut child) => {
            let stdout = child.stdout.take().unwrap();
            let stderr = child.stderr.take().unwrap();

            *inner.current_process.lock().unwrap() = Some(child);

            let w1 = window.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stdout);
                for line in reader.lines().flatten() {
                    let _ = w1.emit("terminal_update", line);
                }
            });

            let w2 = window.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines().flatten() {
                    let _ = w2.emit("terminal_update", format!("(stderr) {}", line));
                }
            });

            ensure_monitor_thread(app, window, inner);

            Ok(format!("Started {}", script_name))
        }
        Err(e) => {
            let msg = format!("Failed to spawn python: {}", e);
            let _ = window.emit("terminal_update", msg.clone());
            Err(msg)
        }
    }
}

// ---------------------------
// AI CHAT (PRODUCTION) - GEMINI + OPENAI
// ---------------------------

fn get_provider(app: &AppHandle) -> String {
    let p = get_env_var(app, "AI_PROVIDER");
    let p = p.trim().to_lowercase();
    if p.is_empty() { "gemini".to_string() } else { p }
}

fn normalize_provider(p: &str) -> String {
    match p.trim().to_lowercase().as_str() {
        "openai" => "openai".to_string(),
        _ => "gemini".to_string(),
    }
}

#[tauri::command]
async fn ai_chat(
    app: AppHandle,
    state: tauri::State<'_, AppState>,
    message: String,
) -> Result<String, String> {
    let provider = normalize_provider(&get_provider(&app));
    let user_msg = message.trim().to_string();
    if user_msg.is_empty() {
        return Err("Message is empty.".to_string());
    }

    if provider == "openai" {
        let key = get_env_var(&app, "OPENAI_API_KEY");
        if key.trim().is_empty() {
            return Err("OPENAI_API_KEY is empty. Open Settings and save your key.".to_string());
        }

        let body = json!({
            "model": "gpt-4o-mini",
            "messages": [
                { "role": "system", "content": "You are a helpful assistant. Reply concisely." },
                { "role": "user", "content": user_msg }
            ],
            "temperature": 0.7
        });

        let res = state
            .inner
            .http
            .post("https://api.openai.com/v1/chat/completions")
            .bearer_auth(key.trim())
            .json(&body)
            .send()
            .await
            .map_err(|e| e.to_string())?;

        let status = res.status();
        let v: Value = res.json().await.map_err(|e| e.to_string())?;

        if !status.is_success() {
            return Err(v.to_string());
        }

        let text = v["choices"][0]["message"]["content"]
            .as_str()
            .unwrap_or("")
            .to_string();

        if text.trim().is_empty() {
            return Err("OpenAI returned an empty response.".to_string());
        }
        return Ok(text);
    }

    // Default: Gemini
    let key = get_env_var(&app, "GEMINI_API_KEY");
    if key.trim().is_empty() {
        return Err("GEMINI_API_KEY is empty. Open Settings and save your key.".to_string());
    }

    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={}",
        key.trim()
    );

    let body = json!({
        "contents": [{
            "role": "user",
            "parts": [{ "text": user_msg }]
        }]
    });

    let res = state
        .inner
        .http
        .post(url)
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let status = res.status();
    let v: Value = res.json().await.map_err(|e| e.to_string())?;

    if !status.is_success() {
        return Err(v.to_string());
    }

    let text = v["candidates"][0]["content"]["parts"][0]["text"]
        .as_str()
        .unwrap_or("")
        .to_string();

    if text.trim().is_empty() {
        return Err("Gemini returned an empty response.".to_string());
    }

    Ok(text)
}

// ---------------------------
// TAURI COMMANDS
// ---------------------------

#[tauri::command]
fn get_ai_config(app: AppHandle) -> AiConfig {
    AiConfig {
        provider: get_env_var(&app, "AI_PROVIDER"),
        gemini_key: get_env_var(&app, "GEMINI_API_KEY"),
        openai_key: get_env_var(&app, "OPENAI_API_KEY"),
    }
}

// ✅ UPDATED: Robust save_configuration that returns errors and validates input
#[tauri::command]
fn save_configuration(app: AppHandle, provider: String, api_key: String) -> Result<bool, String> {
    let provider = provider.trim().to_lowercase();
    let api_key = api_key.trim().to_string();

    if api_key.is_empty() {
        return Err("API key is empty".to_string());
    }

    update_env_file(&app, "AI_PROVIDER", &provider)?;

    match provider.as_str() {
        "gemini" => {
            update_env_file(&app, "GEMINI_API_KEY", &api_key)?;
        }
        "openai" => {
            update_env_file(&app, "OPENAI_API_KEY", &api_key)?;
        }
        _ => return Err(format!("Unknown provider: {}", provider)),
    }

    Ok(true)
}

#[tauri::command]
async fn start_recording(
    state: tauri::State<'_, AppState>,
    app: AppHandle,
    window: Window,
    game_id: Option<String>,
    dataset_name: Option<String>,
) -> Result<String, String> {
    let gid = normalize_game_id(game_id);
    let name = dataset_name.unwrap_or_else(|| "Untitled".to_string());
    let inner = state.inner.clone();

    if let Err(e) = api_post_with(
        &inner,
        "/session/begin_recording",
        json!({"game_id": gid, "dataset_name": name}),
    )
    .await
    {
        let _ = window.emit("terminal_update", format!("[Warning] begin_recording failed: {}", e));
    }

    run_python_script(app, "1-collect_data.py", window, inner)
}

#[tauri::command]
async fn start_training(
    state: tauri::State<'_, AppState>,
    app: AppHandle,
    window: Window,
    game_id: Option<String>,
    model_name: Option<String>,
    dataset_id: Option<String>,
    arch: Option<String>,
) -> Result<String, String> {
    let gid = normalize_game_id(game_id);
    let mname = model_name.unwrap_or_else(|| "New Model".to_string());
    let did = dataset_id.unwrap_or_default();
    let a = arch.unwrap_or_else(|| "custom".to_string());
    let inner = state.inner.clone();

    if let Err(e) = api_post_with(
        &inner,
        "/session/begin_training",
        json!({"game_id": gid, "model_name": mname, "dataset_id": did, "arch": a}),
    )
    .await
    {
        let _ = window.emit("terminal_update", format!("[Warning] begin_training failed: {}", e));
    }

    run_python_script(app, "2-train_model.py", window, inner)
}

#[tauri::command]
fn start_bot(app: AppHandle, window: Window, state: tauri::State<AppState>) -> Result<String, String> {
    run_python_script(app, "3-test_model.py", window, state.inner.clone())
}

#[tauri::command]
async fn stop_process(state: tauri::State<'_, AppState>, window: Window) -> Result<String, String> {
    let inner = state.inner.clone();
    let msg = stop_process_inner(&window, &inner);

    if let Err(e) = api_post_with(&inner, "/session/finalize", json!({})).await {
        let _ = window.emit("terminal_update", format!("[Warning] finalize failed: {}", e));
    }

    Ok(msg)
}

#[tauri::command]
async fn modelhub_is_available(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    api_get_with(&state.inner, "/modelhub/available").await
}

#[tauri::command]
async fn modelhub_list_games(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    api_get_with(&state.inner, "/modelhub/games").await
}

#[tauri::command]
async fn mh_get_catalog_data(
    state: tauri::State<'_, AppState>,
    game_id: Option<String>,
) -> Result<Value, String> {
    let gid = normalize_game_id(game_id);
    api_get_with(
        &state.inner,
        &format!("/modelhub/catalog?game_id={}", urlencoding::encode(&gid)),
    )
    .await
}

#[tauri::command]
async fn mh_set_active(
    state: tauri::State<'_, AppState>,
    game_id: Option<String>,
    model_id: String,
    path: String,
) -> Result<Value, String> {
    let gid = normalize_game_id(game_id);
    api_post_with(
        &state.inner,
        "/modelhub/active",
        json!({"game_id": gid, "model_id": model_id, "path": path}),
    )
    .await
}

#[tauri::command]
async fn mh_delete_model(
    state: tauri::State<'_, AppState>,
    game_id: Option<String>,
    model_id: String,
    path: String,
) -> Result<Value, String> {
    let gid = normalize_game_id(game_id);
    api_post_with(
        &state.inner,
        "/modelhub/delete",
        json!({"game_id": gid, "model_id": model_id, "path": path}),
    )
    .await
}

#[tauri::command]
async fn modelhub_validate_model(
    state: tauri::State<'_, AppState>,
    game_id: Option<String>,
    model_dir: String,
) -> Result<Value, String> {
    let gid = normalize_game_id(game_id);
    api_post_with(
        &state.inner,
        "/modelhub/validate",
        json!({"game_id": gid, "model_dir": model_dir}),
    )
    .await
}

#[tauri::command]
async fn modelhub_run_offline_evaluation(
    state: tauri::State<'_, AppState>,
    model_dir: String,
    dataset_dir: String,
) -> Result<Value, String> {
    api_post_with(
        &state.inner,
        "/modelhub/offline-eval",
        json!({"model_dir": model_dir, "dataset_dir": dataset_dir}),
    )
    .await
}

#[tauri::command]
fn install_drivers(app: tauri::AppHandle) -> Value {
    #[cfg(target_os = "windows")]
    {
        let resource_path = app
            .path_resolver()
            .resolve_resource("resources/scripts/install_drivers.ps1");

        let script = match resource_path {
            Some(p) => p,
            None => return json!({"ok": false, "error": "Could not find install_drivers.ps1"}),
        };

        let ps = format!(
            "Start-Process PowerShell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File \"{}\"'",
            script.display()
        );

        let out = Command::new("powershell").args(["-NoProfile", "-Command", &ps]).output();

        match out {
            Ok(o) => json!({ "ok": o.status.success(), "code": o.status.code() }),
            Err(e) => json!({ "ok": false, "error": e.to_string() }),
        }
    }
    #[cfg(not(target_os = "windows"))]
    {
        json!({"ok": false, "error": "Drivers are Windows-only"})
    }
}

// ---------------------------
// MAIN
// ---------------------------
fn main() {
    tauri::Builder::default()
        .manage(AppState {
            inner: Arc::new(AppStateInner {
                current_process: Mutex::new(None),
                sidecar: Mutex::new(None),
                http: Client::new(),
            }),
        })
        .setup(|app| {
            let app_handle = app.handle();
            let state = app.state::<AppState>();

            match start_sidecar_server(&app_handle) {
                Ok(api) => {
                    *state.inner.sidecar.lock().unwrap() = Some(api);
                    if let Some(w) = app.get_window("main") {
                        let _ = w.emit::<String>("terminal_update", "[System] Sidecar READY".to_string());
                    }
                }
                Err(e) => {
                    if let Some(w) = app.get_window("main") {
                        let _ = w.emit::<String>("terminal_update", format!("[Fatal] Sidecar failed: {}", e));
                    }
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // Settings + AI
            get_ai_config,
            save_configuration,
            ai_chat,

            // Existing
            start_recording,
            start_training,
            start_bot,
            stop_process,
            modelhub_is_available,
            modelhub_list_games,
            mh_get_catalog_data,
            mh_set_active,
            mh_delete_model,
            modelhub_validate_model,
            modelhub_run_offline_evaluation,
            install_drivers
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
