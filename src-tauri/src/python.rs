// src-tauri/src/python.rs
//
// Centralized Python runner utilities for Tauri.
// Provides:
//  - spawn_python_stream: long-running scripts with stdout/stderr streaming to UI
//  - run_python_json: quick one-shot python tool execution returning JSON
//
// Usage from main.rs:
//   mod python;
//   use python::{spawn_python_stream, run_python_json, resolve_resource_or_dev, python_cmd_name};
//
// NOTE: This module assumes your frontend listens to "terminal_update" events.
//
use serde_json::{json, Value};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::thread;
use tauri::{AppHandle, Window};

pub fn python_cmd_name() -> &'static str {
    if cfg!(target_os = "windows") {
        "python"
    } else {
        "python3"
    }
}

/// Resolve a bundled resource; fall back to dev relative path.
pub fn resolve_resource_or_dev(app: &AppHandle, resource_rel: impl AsRef<str>, dev_fallback: impl AsRef<str>) -> PathBuf {
    app.path_resolver()
        .resolve_resource(resource_rel.as_ref())
        .unwrap_or_else(|| PathBuf::from(dev_fallback.as_ref()))
}

/// Emit a line to the UI terminal.
pub fn term(window: &Window, msg: impl Into<String>) {
    let _ = window.emit("terminal_update", msg.into());
}

/// Spawn a long-running python script and stream stdout/stderr.
/// Returns the Child process handle on success.
///
/// - `script_path`: absolute or resolved path to .py
/// - `cwd`: optional working directory (recommended for your versions/0.01 scripts)
/// - `args`: any args passed to script
pub fn spawn_python_stream(
    window: Window,
    script_path: PathBuf,
    cwd: Option<PathBuf>,
    args: Vec<String>,
) -> Result<Child, String> {
    if !script_path.exists() {
        let err = format!("Python script not found: {}", script_path.display());
        term(&window, format!("[System] {}", err));
        return Err(err);
    }

    let mut cmd = Command::new(python_cmd_name());
    cmd.arg(&script_path);
    for a in args {
        cmd.arg(a);
    }

    if let Some(dir) = cwd {
        cmd.current_dir(dir);
    }

    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());

    // prevent console window popups on Windows
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    match cmd.spawn() {
        Ok(mut child) => {
            let stdout = child.stdout.take().ok_or_else(|| "Failed to capture stdout".to_string())?;
            let stderr = child.stderr.take().ok_or_else(|| "Failed to capture stderr".to_string())?;

            // stdout thread
            let w1 = window.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stdout);
                for line in reader.lines() {
                    if let Ok(l) = line {
                        let _ = w1.emit("terminal_update", l);
                    }
                }
            });

            // stderr thread
            let w2 = window.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    if let Ok(l) = line {
                        let _ = w2.emit("terminal_update", format!("(stderr) {}", l));
                    }
                }
            });

            Ok(child)
        }
        Err(e) => {
            let err = format!("Failed to spawn python process: {}", e);
            term(&window, format!("[System] {}", err));
            Err(err)
        }
    }
}

/// Run a quick python "tool" script and capture JSON output.
/// This is ideal for ModelHub registry/catalog operations.
///
/// - `tool_path`: python entrypoint that prints JSON to stdout
/// - `cwd`: optional working directory
/// - `args`: list of args (already tokenized)
///
/// Returns a JSON Value:
/// - If stdout is valid JSON, parsed Value
/// - Else a wrapper: { ok, stdout, stderr }
pub fn run_python_json(
    window: Window,
    tool_path: PathBuf,
    cwd: Option<PathBuf>,
    args: Vec<String>,
) -> Value {
    if !tool_path.exists() {
        let msg = format!("Missing python tool: {}", tool_path.display());
        term(&window, format!("[ModelHub] {}", msg));
        return json!({"ok": false, "error": msg});
    }

    let mut cmd = Command::new(python_cmd_name());
    cmd.arg(&tool_path);

    for a in args {
        cmd.arg(a);
    }

    if let Some(dir) = cwd {
        cmd.current_dir(dir);
    }

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
                term(&window, format!("[ModelHub][stderr] {}", stderr.trim()));
            }

            match serde_json::from_str::<Value>(&stdout) {
                Ok(v) => v,
                Err(_) => json!({
                    "ok": out.status.success(),
                    "stdout": stdout,
                    "stderr": stderr
                }),
            }
        }
        Err(e) => {
            let msg = format!("Python tool spawn failed: {}", e);
            term(&window, format!("[ModelHub] {}", msg));
            json!({"ok": false, "error": msg})
        }
    }
}

/// Optional helper: choose a good working directory for scripts that expect relative files.
/// For versions/0.01 scripts, pass the directory containing the script.
pub fn default_cwd_for_script(script_path: &Path) -> Option<PathBuf> {
    script_path.parent().map(|p| p.to_path_buf())
}
