#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde_json::json;
use std::process::Command;

#[tauri::command]
fn install_drivers(app: tauri::AppHandle) -> serde_json::Value {
  #[cfg(target_os = "windows")]
  {
    let resource_path = app
      .path_resolver()
      .resolve_resource("scripts/install_drivers.ps1");

    let script = match resource_path {
      Some(p) => p,
      None => return json!({"ok": false, "error": "Could not find install_drivers.ps1 in resources"}),
    };

    let ps = format!(
      "Start-Process PowerShell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File \"{}\"'",
      script.display()
    );

    let out = Command::new("powershell")
      .args(["-NoProfile", "-Command", &ps])
      .output();

    match out {
      Ok(o) => json!({
        "ok": o.status.success(),
        "code": o.status.code(),
        "stdout": String::from_utf8_lossy(&o.stdout),
        "stderr": String::from_utf8_lossy(&o.stderr)
      }),
      Err(e) => json!({"ok": false, "error": e.to_string()}),
    }
  }

  #[cfg(not(target_os = "windows"))]
  {
    json!({"ok": false, "error": "drivers are Windows-only"})
  }
}

fn main() {
  tauri::Builder::default()
    .invoke_handler(tauri::generate_handler![install_drivers])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
