#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::io::{BufRead, BufReader};
// FIXED: Removed 'Path' from import to solve unused import warning
use std::path::PathBuf; 
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Window};
use serde_json::json;

// --- STATE MANAGEMENT ---

struct AppState {
    current_process: Arc<Mutex<Option<Child>>>,
}

#[derive(serde::Serialize, serde::Deserialize)]
struct AiConfig {
    provider: String,
    gemini_key: String,
    openai_key: String,
}

// --- CONFIG (.env) HELPERS ---

/// Determines the correct path for the .env file.
/// DEV: Checks project root (../.env) for shared config with Python.
/// PROD: Uses the OS-specific App Config folder.
fn env_file_path(app: &AppHandle) -> PathBuf {
    // 1) Dev convenience: use project root .env if present
    if cfg!(debug_assertions) {
        if let Ok(cwd) = std::env::current_dir() {
            // Typically cwd is ".../src-tauri" when running `cargo tauri dev`
            let candidate = cwd.join("..").join(".env");
            if candidate.exists() {
                return candidate;
            }
        }
    }

    // 2) Production-safe: per-user config directory
    let cfg_dir = app
        .path_resolver()
        .app_config_dir()
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));

    if let Err(_) = fs::create_dir_all(&cfg_dir) {
        // fall back to current dir if config dir cannot be created
        return PathBuf::from(".env");
    }

    cfg_dir.join(".env")
}

fn ensure_default_env(app: &AppHandle) {
    let path = env_file_path(app);
    if path.exists() {
        return;
    }
    // Default values
    let default_content = "AI_PROVIDER=\"gemini\"\nGEMINI_API_KEY=\"\"\nOPENAI_API_KEY=\"\"\n";
    let _ = fs::write(path, default_content);
}

fn get_env_var(app: &AppHandle, key: &str) -> Option<String> {
    ensure_default_env(app);
    let env_path = env_file_path(app);
    let content = fs::read_to_string(&env_path).ok()?;
    
    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') { continue; }
        
        if let Some((k, v)) = line.split_once('=') {
            if k.trim() == key {
                let mut value = v.trim().to_string();
                // Strip optional quotes
                if (value.starts_with('"') && value.ends_with('"')) || (value.starts_with('\'') && value.ends_with('\'')) {
                    value = value[1..value.len()-1].to_string();
                }
                return Some(value);
            }
        }
    }
    None
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
                // Escape quotes if necessary
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

// --- HELPER: Run Python Script ---

fn run_python_script(
    app: AppHandle,
    script_name: &str, 
    window: Window, 
    state: tauri::State<AppState>
) -> String {
    
    // 1. Resolve Script Path
    let resource_path = app.path_resolver()
        .resolve_resource(format!("versions/0.01/{}", script_name));

    let script_path_buf: PathBuf = match resource_path {
        Some(path) => path,
        None => {
            // Fallback for dev if resource resolver fails
            PathBuf::from(format!("../versions/0.01/{}", script_name))
        }
    };

    let script_path = script_path_buf.to_string_lossy().to_string();

    // Log to UI
    let _ = window.emit("terminal_update", format!("[System] Locating script: {}", script_path));

    if !script_path_buf.exists() {
        let err_msg = format!("Error: Script file not found at: {}", script_path);
        let _ = window.emit("terminal_update", err_msg.clone());
        return err_msg;
    }
    
    // 2. Stop existing process if running
    stop_process(state.clone());

    // 3. Determine Python Interpreter
    let cmd_name = if cfg!(target_os = "windows") { "python" } else { "python3" };

    // 4. Spawn Process
    let mut command = Command::new(cmd_name);
    command.arg(&script_path);

    // Pass config to Python as environment variables
    let provider = get_env_var(&app, "AI_PROVIDER").unwrap_or_else(|| "gemini".to_string());
    let gemini_key = get_env_var(&app, "GEMINI_API_KEY").unwrap_or_default();
    let openai_key = get_env_var(&app, "OPENAI_API_KEY").unwrap_or_default();
    
    command.env("AI_PROVIDER", provider);
    command.env("GEMINI_API_KEY", gemini_key);
    command.env("OPENAI_API_KEY", openai_key);
    
    // IMPORTANT: Capture outputs
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    
    // Windows: Prevent shell window popup
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        command.creation_flags(CREATE_NO_WINDOW);
    }

    match command.spawn() {
        Ok(mut child_process) => {
            let stdout = child_process.stdout.take().unwrap();
            let stderr = child_process.stderr.take().unwrap();
            let process_handle = state.current_process.clone();
            
            *process_handle.lock().unwrap() = Some(child_process);

            // STDOUT Thread
            let window_clone = window.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stdout);
                for line in reader.lines() {
                    if let Ok(l) = line {
                        window_clone.emit("terminal_update", l).unwrap_or(());
                    }
                }
            });

            // STDERR Thread
            let window_clone_err = window.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    if let Ok(l) = line {
                        window_clone_err.emit("terminal_update", format!("(stderr) {}", l)).unwrap_or(());
                    }
                }
            });

            format!("Started {}", script_name)
        }
        Err(e) => {
            let err_msg = format!("Failed to spawn python process: {}", e);
            let _ = window.emit("terminal_update", err_msg.clone());
            err_msg
        }
    }
}

// --- COMMANDS ---

#[tauri::command]
fn get_ai_config(app: AppHandle) -> AiConfig {
    AiConfig {
        provider: get_env_var(&app, "AI_PROVIDER").unwrap_or_default(),
        gemini_key: get_env_var(&app, "GEMINI_API_KEY").unwrap_or_default(),
        openai_key: get_env_var(&app, "OPENAI_API_KEY").unwrap_or_default(),
    }
}

#[tauri::command]
fn save_configuration(app: AppHandle, provider: String, api_key: String) -> bool {
    let _ = update_env_file(&app, "AI_PROVIDER", &provider);
    if provider == "gemini" {
        let _ = update_env_file(&app, "GEMINI_API_KEY", &api_key);
    } else if provider == "openai" {
        let _ = update_env_file(&app, "OPENAI_API_KEY", &api_key);
    }
    true
}

#[tauri::command]
fn start_recording(app: AppHandle, window: Window, state: tauri::State<AppState>) -> String {
    run_python_script(app, "1-collect_data.py", window, state)
}

#[tauri::command]
fn start_training(app: AppHandle, window: Window, state: tauri::State<AppState>) -> String {
    run_python_script(app, "2-train_model.py", window, state)
}

#[tauri::command]
fn start_bot(app: AppHandle, window: Window, state: tauri::State<AppState>) -> String {
    run_python_script(app, "3-test_model.py", window, state)
}

#[tauri::command]
fn stop_process(state: tauri::State<AppState>) -> String {
    let mut handle = state.current_process.lock().unwrap();
    if let Some(mut child) = handle.take() {
        match child.kill() {
            Ok(_) => return "Process stopped".to_string(),
            Err(e) => return format!("Error killing process: {}", e),
        }
    }
    "No process running".to_string()
}

// --- DRIVER INSTALLER (Windows Only) ---
#[tauri::command]
fn install_drivers(app: tauri::AppHandle) -> serde_json::Value {
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

        let out = Command::new("powershell")
            .args(["-NoProfile", "-Command", &ps])
            .output();

        match out {
            Ok(o) => json!({ "ok": o.status.success(), "code": o.status.code() }),
            Err(e) => json!({"ok": false, "error": e.to_string()}),
        }
    }
    #[cfg(not(target_os = "windows"))]
    { json!({"ok": false, "error": "Drivers are Windows-only"}) }
}

fn main() {
    tauri::Builder::default()
        .manage(AppState {
            current_process: Arc::new(Mutex::new(None)),
        })
        .invoke_handler(tauri::generate_handler![
            get_ai_config,
            save_configuration,
            start_recording,
            start_training,
            start_bot,
            stop_process,
            install_drivers
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}