#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Window};

// -------------------------
// STATE
// -------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum SessionType {
    Recording,
    Training,
    Bot,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ActiveSession {
    session_type: SessionType,
    game_id: String,
    name: String,
    dataset_id: Option<String>,
    arch: Option<String>,
}

struct AppState {
    current_process: Arc<Mutex<Option<Child>>>,
    active_session: Arc<Mutex<Option<ActiveSession>>>,
}

#[derive(Serialize, Deserialize)]
struct AiConfig {
    provider: String,
    gemini_key: String,
    openai_key: String,
}

// -------------------------
// .env helpers
// -------------------------

fn get_env_var(key: &str) -> String {
    let path = Path::new(".env");
    if let Ok(content) = fs::read_to_string(path) {
        for line in content.lines() {
            if line.starts_with(&format!("{}=", key)) {
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

// -------------------------
// Python helpers
// -------------------------

fn python_cmd_name() -> &'static str {
    if cfg!(target_os = "windows") {
        "python"
    } else {
        "python3"
    }
}

/// Resolve a bundled resource; fall back to dev relative path.
fn resolve_resource_or_dev(app: &AppHandle, resource_rel: &str, dev_fallback: &str) -> PathBuf {
    app.path_resolver()
        .resolve_resource(resource_rel)
        .unwrap_or_else(|| PathBuf::from(dev_fallback))
}

/// Emit to terminal
fn term(window: &Window, msg: impl Into<String>) {
    let _ = window.emit("terminal_update", msg.into());
}

/// Run a short python command and parse JSON output.
fn run_python_json(app: &AppHandle, window: &Window, args: &[String]) -> Value {
    let cli_path = resolve_resource_or_dev(app, "scripts/modelhub_cli.py", "../scripts/modelhub_cli.py");

    if !cli_path.exists() {
        let msg = format!(
            "[ModelHub] Missing Python bridge: {} (create scripts/modelhub_cli.py)",
            cli_path.display()
        );
        term(window, msg.clone());
        return json!({"ok": false, "error": msg});
    }

    let mut cmd = Command::new(python_cmd_name());
    cmd.arg(cli_path);

    for a in args {
        cmd.arg(a);
    }

    cmd.current_dir(".");
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    match cmd.output() {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout).to_string();
            let stderr = String::from_utf8_lossy(&out.stderr).to_string();

            if !stderr.trim().is_empty() {
                term(window, format!("[ModelHub][stderr] {}", stderr.trim()));
            }

            match serde_json::from_str::<Value>(&stdout) {
                Ok(v) => v,
                Err(_) => json!({"ok": out.status.success(), "stdout": stdout, "stderr": stderr}),
            }
        }
        Err(e) => {
            let msg = format!("[ModelHub] Python spawn failed: {}", e);
            term(window, msg.clone());
            json!({"ok": false, "error": msg})
        }
    }
}

// -------------------------
// Session finalize
// -------------------------

fn finalize_active_session(app: AppHandle, window: Window, active_session: Arc<Mutex<Option<ActiveSession>>>) -> String {
    let session_opt = {
        let mut guard = active_session.lock().unwrap();
        guard.take()
    };

    let Some(session) = session_opt else {
        return "No active session".to_string();
    };

    match session.session_type {
        SessionType::Recording => {
            term(&window, "[Session] Finalizing recording (Python SessionManager) ...");
            let res = run_python_json(
                &app,
                &window,
                &vec![
                    "finalize-recording".to_string(),
                    "--game".to_string(),
                    session.game_id.clone(),
                    "--name".to_string(),
                    session.name.clone(),
                ],
            );
            term(&window, format!("[Session] finalize-recording => {}", res));
        }
        SessionType::Training => {
            term(&window, "[Session] Finalizing training (Python SessionManager) ...");
            let mut args = vec![
                "finalize-training".to_string(),
                "--game".to_string(),
                session.game_id.clone(),
                "--model-name".to_string(),
                session.name.clone(),
            ];
            if let Some(ds) = session.dataset_id.clone() {
                args.push("--dataset-id".to_string());
                args.push(ds);
            }
            if let Some(arch) = session.arch.clone() {
                args.push("--arch".to_string());
                args.push(arch);
            }
            let res = run_python_json(&app, &window, &args);
            term(&window, format!("[Session] finalize-training => {}", res));
        }
        SessionType::Bot => {
            // nothing to finalize
        }
    }

    "Finalized".to_string()
}

/// Run a long python script and stream output
fn run_python_script(
    app: AppHandle,
    script_name: &str,
    script_args: Vec<String>,
    window: Window,
    state: tauri::State<AppState>,
) -> String {
    let resource_rel = format!("versions/0.01/{}", script_name);
    let dev_fallback = format!("../versions/0.01/{}", script_name);
    let script_path_buf = resolve_resource_or_dev(&app, &resource_rel, &dev_fallback);

    term(&window, format!("[System] Locating script: {}", script_path_buf.display()));

    if !script_path_buf.exists() {
        let err = format!("Error: Script file not found at: {}", script_path_buf.display());
        term(&window, err.clone());
        return err;
    }

    let _ = stop_process(app.clone(), window.clone(), state.clone());

    let mut command = Command::new(python_cmd_name());
    command.arg(&script_path_buf);
    for a in script_args {
        command.arg(a);
    }

    let script_cwd = script_path_buf
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from("."));
    command.current_dir(&script_cwd);

    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());

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

            let proc_arc = state.current_process.clone();
            let sess_arc = state.active_session.clone();

            *proc_arc.lock().unwrap() = Some(child_process);

            // STDOUT thread
            {
                let window_out = window.clone();
                let app_out = app.clone();
                let proc_out = proc_arc.clone();
                let sess_out = sess_arc.clone();

                thread::spawn(move || {
                    let reader = BufReader::new(stdout);
                    for line in reader.lines() {
                        if let Ok(l) = line {
                            let _ = window_out.emit("terminal_update", l);
                        }
                    }
                    {
                        let mut g = proc_out.lock().unwrap();
                        *g = None;
                    }
                    let _ = finalize_active_session(app_out, window_out, sess_out);
                });
            }

            // STDERR thread
            {
                let window_err = window.clone();
                let app_err = app.clone();
                let proc_err = proc_arc.clone();
                let sess_err = sess_arc.clone();

                thread::spawn(move || {
                    let reader = BufReader::new(stderr);
                    for line in reader.lines() {
                        if let Ok(l) = line {
                            let _ = window_err.emit("terminal_update", format!("(stderr) {}", l));
                        }
                    }
                    {
                        let mut g = proc_err.lock().unwrap();
                        *g = None;
                    }
                    let _ = finalize_active_session(app_err, window_err, sess_err);
                });
            }

            format!("Started {}", script_name)
        }
        Err(e) => {
            let err_msg = format!("Failed to spawn python process: {}", e);
            term(&window, err_msg.clone());
            err_msg
        }
    }
}

// -------------------------
// COMMANDS
// -------------------------

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
fn start_recording(
    app: AppHandle,
    window: Window,
    state: tauri::State<AppState>,
    game_id: String,
    dataset_name: String,
) -> String {
    {
        let mut g = state.active_session.lock().unwrap();
        *g = Some(ActiveSession {
            session_type: SessionType::Recording,
            game_id: if game_id.trim().is_empty() { "genshin_impact".to_string() } else { game_id },
            name: if dataset_name.trim().is_empty() { "Untitled Dataset".to_string() } else { dataset_name },
            dataset_id: None,
            arch: None,
        });
    }

    let s = state.active_session.lock().unwrap().clone().unwrap();
    let _ = run_python_json(
        &app,
        &window,
        &vec![
            "begin-recording".to_string(),
            "--game".to_string(),
            s.game_id.clone(),
            "--name".to_string(),
            s.name.clone(),
        ],
    );

    run_python_script(app, "1-collect_data.py", vec![], window, state)
}

#[tauri::command]
fn start_training(
    app: AppHandle,
    window: Window,
    state: tauri::State<AppState>,
    game_id: String,
    model_name: String,
    dataset_id: String,
    arch: String,
) -> String {
    {
        let mut g = state.active_session.lock().unwrap();
        *g = Some(ActiveSession {
            session_type: SessionType::Training,
            game_id: if game_id.trim().is_empty() { "genshin_impact".to_string() } else { game_id },
            name: if model_name.trim().is_empty() { "New Model".to_string() } else { model_name },
            dataset_id: if dataset_id.trim().is_empty() { None } else { Some(dataset_id) },
            arch: if arch.trim().is_empty() { Some("custom".to_string()) } else { Some(arch) },
        });
    }

    let s = state.active_session.lock().unwrap().clone().unwrap();
    let mut args = vec![
        "begin-training".to_string(),
        "--game".to_string(),
        s.game_id.clone(),
        "--model-name".to_string(),
        s.name.clone(),
    ];
    if let Some(ds) = s.dataset_id.clone() {
        args.push("--dataset-id".to_string());
        args.push(ds);
    }
    if let Some(a) = s.arch.clone() {
        args.push("--arch".to_string());
        args.push(a);
    }
    let _ = run_python_json(&app, &window, &args);

    run_python_script(app, "2-train_model.py", vec![], window, state)
}

#[tauri::command]
fn start_bot(app: AppHandle, window: Window, state: tauri::State<AppState>) -> String {
    {
        let mut g = state.active_session.lock().unwrap();
        *g = Some(ActiveSession {
            session_type: SessionType::Bot,
            game_id: "genshin_impact".to_string(),
            name: "Run Bot".to_string(),
            dataset_id: None,
            arch: None,
        });
    }

    run_python_script(app, "3-test_model.py", vec![], window, state)
}

#[tauri::command]
fn stop_process(app: AppHandle, window: Window, state: tauri::State<AppState>) -> String {
    let proc_arc = state.current_process.clone();
    let sess_arc = state.active_session.clone();

    {
        let mut handle = proc_arc.lock().unwrap();
        if let Some(mut child) = handle.take() {
            let _ = child.kill();
            term(&window, "[Process] Stopped.");
        } else {
            term(&window, "[Process] No process running.");
        }
    }

    finalize_active_session(app, window, sess_arc)
}

#[tauri::command]
fn modelhub_is_available(app: AppHandle) -> bool {
    // FIX: Added '&' before app
    let cli_path = resolve_resource_or_dev(&app, "scripts/modelhub_cli.py", "../scripts/modelhub_cli.py");
    cli_path.exists()
}

#[tauri::command]
fn modelhub_list_games(app: AppHandle, window: Window) -> Value {
    run_python_json(&app, &window, &vec!["list-games".to_string()])
}

#[tauri::command]
fn mh_get_catalog_data(app: AppHandle, window: Window, game_id: String) -> Value {
    run_python_json(
        &app,
        &window,
        &vec!["get-catalog".to_string(), "--game".to_string(), game_id],
    )
}

#[tauri::command]
fn mh_set_active(app: AppHandle, window: Window, game_id: String, model_id: String, path: String) -> Value {
    run_python_json(
        &app,
        &window,
        &vec![
            "set-active".to_string(),
            "--game".to_string(),
            game_id,
            "--model-id".to_string(),
            model_id,
            "--path".to_string(),
            path,
        ],
    )
}

#[tauri::command]
fn modelhub_validate_model(app: AppHandle, window: Window, game_id: String, model_dir: String) -> Value {
    run_python_json(
        &app,
        &window,
        &vec![
            "validate".to_string(),
            "--game".to_string(),
            game_id,
            "--model-dir".to_string(),
            model_dir,
        ],
    )
}

#[tauri::command]
fn modelhub_run_offline_evaluation(app: AppHandle, window: Window, model_dir: String, dataset_dir: String) -> Value {
    run_python_json(
        &app,
        &window,
        &vec![
            "offline-eval".to_string(),
            "--model-dir".to_string(),
            model_dir,
            "--dataset-dir".to_string(),
            dataset_dir,
        ],
    )
}

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
    {
        json!({"ok": false, "error": "Drivers are Windows-only"})
    }
}

// -------------------------
// MAIN
// -------------------------

fn main() {
    tauri::Builder::default()
        .manage(AppState {
            current_process: Arc::new(Mutex::new(None)),
            active_session: Arc::new(Mutex::new(None)),
        })
        .invoke_handler(tauri::generate_handler![
            get_ai_config,
            save_configuration,
            start_recording,
            start_training,
            start_bot,
            stop_process,
            modelhub_is_available,
            modelhub_list_games,
            mh_get_catalog_data,
            mh_set_active,
            modelhub_validate_model,
            modelhub_run_offline_evaluation,
            install_drivers
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}