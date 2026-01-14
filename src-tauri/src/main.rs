#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio, Child};
use std::sync::{Arc, Mutex};
use std::thread;
// FIXED: Removed 'Manager' to resolve "unused import" warning
use tauri::{Window, AppHandle};
use serde_json::json;

// --- STATE MANAGEMENT ---

// State to hold the running python process so we can kill it later
struct AppState {
    current_process: Arc<Mutex<Option<Child>>>,
}

#[derive(serde::Serialize, serde::Deserialize)]
struct AiConfig {
    provider: String,
    gemini_key: String,
    openai_key: String,
}

// --- HELPER: Parse .env manually ---
fn get_env_var(key: &str) -> String {
    // Try to find .env in the current working directory
    let path = Path::new(".env");
    
    if let Ok(content) = fs::read_to_string(path) {
        for line in content.lines() {
            if line.starts_with(key) {
                let parts: Vec<&str> = line.splitn(2, '=').collect();
                if parts.len() == 2 {
                    return parts[1].trim().trim_matches('"').to_string();
                }
            }
        }
    }
    String::new()
}

fn update_env_file(key: &str, value: &str) {
    let path = Path::new(".env");
    let content = fs::read_to_string(path).unwrap_or_default();
    let mut new_lines = Vec::new();
    let mut found = false;

    for line in content.lines() {
        if line.starts_with(&format!("{}=", key)) {
            new_lines.push(format!("{}=\"{}\"", key, value));
            found = true;
        } else {
            new_lines.push(line.to_string());
        }
    }

    if !found {
        new_lines.push(format!("{}=\"{}\"", key, value));
    }

    let _ = fs::write(path, new_lines.join("\n"));
}

// --- HELPER: Run Python Script ---
fn run_python_script(
    app: AppHandle,
    script_name: &str, 
    window: Window, 
    state: tauri::State<AppState>
) -> String {
    
    // 1. Resolve Script Path
    // In dev: looks in absolute path relative to Cargo.toml (fallback)
    // In prod: looks in the bundled resource directory
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

    // Log to UI for debugging
    let _ = window.emit("terminal_update", format!("[System] Locating script: {}", script_path));

    if !script_path_buf.exists() {
        let err_msg = format!("Error: Script file not found at: {}", script_path);
        let _ = window.emit("terminal_update", err_msg.clone());
        return err_msg;
    }
    
    // 2. Stop existing
    stop_process(state.clone());

    // 3. Determine Python Interpreter
    // In production, we assume python is in PATH or bundled
    let cmd_name = if cfg!(target_os = "windows") { "python" } else { "python3" };

    // 4. Spawn Process
    let mut command = Command::new(cmd_name);
    command.arg(&script_path);
    
    // IMPORTANT: Capture outputs
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    
    // Fix: Ensure we run in a windowless mode on Windows to avoid popping up shells
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

            // STDERR Thread (Critical for debugging crashes)
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
fn get_ai_config() -> AiConfig {
    AiConfig {
        provider: get_env_var("AI_PROVIDER"),
        gemini_key: get_env_var("GEMINI_API_KEY"),
        openai_key: get_env_var("OPENAI_API_KEY"),
    }
}

#[tauri::command]
fn save_configuration(provider: String, api_key: String) -> bool {
    update_env_file("AI_PROVIDER", &provider);
    if provider == "gemini" {
        update_env_file("GEMINI_API_KEY", &api_key);
    } else if provider == "openai" {
        update_env_file("OPENAI_API_KEY", &api_key);
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