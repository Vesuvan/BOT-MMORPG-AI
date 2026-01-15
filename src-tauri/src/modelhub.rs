// src-tauri/src/modelhub.rs
//
// Rust <-> Python bridge for ModelHub.
// Calls:  python scripts/modelhub_cli.py <command> [args...]
// Returns: JSON (serde_json::Value) to the UI.
//
// Requires in Cargo.toml:
//   serde = { version = "1", features = ["derive"] }
//   serde_json = "1"
//   tauri = { version = "...", features = ["api-all"] }   // your existing setup
//
// And ensure scripts/modelhub_cli.py is included in bundle resources (or available in dev).

use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use tauri::AppHandle;

/// Choose python executable name for the current OS.
fn python_cmd() -> &'static str {
  if cfg!(target_os = "windows") { "python" } else { "python3" }
}

/// Resolve a path to scripts/modelhub_cli.py for both dev and bundled builds.
fn resolve_modelhub_cli(app: &AppHandle) -> PathBuf {
  // In production bundles, it may be included as a resource.
  // If you add `../scripts/**` or specifically `../scripts/modelhub_cli.py` to tauri.conf.json resources,
  // this will work. In dev, fallback to project-relative.
  if let Some(p) = app
    .path_resolver()
    .resolve_resource("scripts/modelhub_cli.py")
  {
    return p;
  }

  // Dev fallback: src-tauri/src -> src-tauri -> project root
  // scripts/modelhub_cli.py is at project root/scripts/modelhub_cli.py
  PathBuf::from("../scripts/modelhub_cli.py")
}

/// Execute python CLI and parse JSON output.
/// Returns a JSON Value (always).
fn run_cli_json(app: &AppHandle, args: &[String]) -> Result<Value, String> {
  let cli_path = resolve_modelhub_cli(app);

  if !cli_path.exists() {
    return Ok(json!({
      "ok": false,
      "error": format!("modelhub_cli.py not found at {}", cli_path.display())
    }));
  }

  let mut cmd = Command::new(python_cmd());
  cmd.arg(cli_path);

  for a in args {
    cmd.arg(a);
  }

  // Ensure we can read stdout/stderr
  cmd.stdout(Stdio::piped());
  cmd.stderr(Stdio::piped());

  // Optional: keep working directory stable (important for relative paths like .env, catalog/, etc.)
  // We set CWD to project root in dev; in production it's the app working dir.
  // If you want strict behavior, you can set it to the parent of scripts/ at runtime.
  // cmd.current_dir("..");

  let out = cmd.output().map_err(|e| format!("Failed to run python: {e}"))?;

  let stdout = String::from_utf8_lossy(&out.stdout).trim().to_string();
  let stderr = String::from_utf8_lossy(&out.stderr).trim().to_string();

  if stdout.is_empty() {
    return Ok(json!({
      "ok": false,
      "error": "No JSON received from modelhub_cli.py",
      "stderr": stderr,
      "status": out.status.code()
    }));
  }

  // modelhub_cli.py prints JSON only; parse it.
  match serde_json::from_str::<Value>(&stdout) {
    Ok(v) => Ok(v),
    Err(e) => Ok(json!({
      "ok": false,
      "error": format!("Invalid JSON from modelhub_cli.py: {e}"),
      "raw_stdout": stdout,
      "stderr": stderr,
      "status": out.status.code()
    })),
  }
}

/// Quick availability check (python in PATH + cli script exists + can run list-games).
#[tauri::command]
pub fn modelhub_is_available(app: AppHandle) -> Value {
  let args = vec!["list-games".to_string()];
  match run_cli_json(&app, &args) {
    Ok(v) => {
      // If python is missing, you'll usually get ok=false with error.
      // Return boolean-like payload for UI convenience.
      let ok = v.get("ok").and_then(|x| x.as_bool()).unwrap_or(false);
      json!({ "ok": ok, "raw": v })
    }
    Err(e) => json!({ "ok": false, "error": e }),
  }
}

#[tauri::command]
pub fn modelhub_list_games(app: AppHandle) -> Value {
  let args = vec!["list-games".to_string()];
  match run_cli_json(&app, &args) {
    Ok(v) => v,
    Err(e) => json!({ "ok": false, "error": e }),
  }
}

/// Returns { builtin_models, datasets, models, active } for a game.
#[tauri::command]
pub fn mh_get_catalog_data(app: AppHandle, game_id: String) -> Value {
  let args = vec![
    "get-catalog".to_string(),
    "--game".to_string(),
    game_id,
  ];

  match run_cli_json(&app, &args) {
    Ok(v) => v,
    Err(e) => json!({ "ok": false, "error": e }),
  }
}

/// Set active model for runtime.
#[tauri::command]
pub fn mh_set_active(app: AppHandle, game_id: String, model_id: String, path: String) -> Value {
  let args = vec![
    "set-active".to_string(),
    "--game".to_string(),
    game_id,
    "--model".to_string(),
    model_id,
    "--path".to_string(),
    path,
  ];

  match run_cli_json(&app, &args) {
    Ok(v) => v,
    Err(e) => json!({ "ok": false, "error": e }),
  }
}

/// Validate a model directory (checks profile.json against game blueprint).
#[tauri::command]
pub fn modelhub_validate_model(app: AppHandle, game_id: String, model_dir: String) -> Value {
  let args = vec![
    "validate".to_string(),
    "--game".to_string(),
    game_id,
    "--model-dir".to_string(),
    model_dir,
  ];

  match run_cli_json(&app, &args) {
    Ok(v) => v,
    Err(e) => json!({ "ok": false, "error": e }),
  }
}

/// Optional: start offline evaluation.
#[tauri::command]
pub fn modelhub_run_offline_evaluation(app: AppHandle, model_dir: String, dataset_dir: String) -> Value {
  let args = vec![
    "run-offline-eval".to_string(),
    "--model-dir".to_string(),
    model_dir,
    "--dataset-dir".to_string(),
    dataset_dir,
  ];

  match run_cli_json(&app, &args) {
    Ok(v) => v,
    Err(e) => json!({ "ok": false, "error": e }),
  }
}
