import { listen } from "@tauri-apps/api/event";
// Import everything exported from ui.js as a single namespace object 'UI'
import * as UI from "./ui.js"; 

// 1. Expose ALL UI functions to the global window object
// This makes onclick="showTab(...)", onclick="toggleRecord(...)", etc. work in HTML
Object.assign(window, UI);

// 2. Initialize the app when DOM is ready
window.addEventListener("DOMContentLoaded", () => {
  console.log("Initializing UI...");
  
  // Call the main initialization logic from ui.js
  if (typeof UI.initUI === 'function') {
    UI.initUI();
  } else {
    console.error("Error: initUI function not found in ui.js");
  }
});

// 3. Global error handler for catching unhandled frontend errors
window.addEventListener("error", (e) => {
  console.error("Global Error:", e.error);
});

// 4. Redundant listener for terminal updates (safety net)
// If ui.js fails to attach its listener, this ensures logs still print if update_terminal exists.
listen("terminal_update", (e) => {
  if (typeof window.update_terminal === 'function') {
    window.update_terminal(e.payload);
  }
});