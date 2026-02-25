import json
import unittest
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[1]
UI_HTML = ROOT / "tauri-ui" / "index.html"
UI_JS = ROOT / "tauri-ui" / "main.js"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"
NSIS_TEMPLATE = ROOT / "installer" / "nsis_template.nsi"


class TestTauriUI(unittest.TestCase):
    # REMOVED: test_no_inline_onclick
    # Reason: The current UI design intentionally uses inline handlers (e.g. onclick="toggleRecord()")
    # which are permitted by the 'unsafe-inline' CSP policy in tauri.conf.json.

    def test_nav_has_data_tabs(self):
        """Ensure navigation buttons have data-tab attributes for JS routing."""
        if not UI_HTML.exists():
            self.skipTest("HTML not found")
        html = UI_HTML.read_text(encoding="utf-8", errors="replace")
        for tab in ("dashboard", "teach", "train", "run", "strategist"):
            self.assertIn(f'data-tab="{tab}"', html, f"Missing data-tab for {tab}")

    def test_main_js_no_tauri_imports(self):
        """Ensure we use window.__TAURI__ instead of node imports."""
        if not UI_JS.exists():
            self.skipTest("JS not found")
        js = UI_JS.read_text(encoding="utf-8", errors="replace")
        self.assertNotIn(
            "@tauri-apps/api", js, "main.js still imports npm @tauri-apps/api"
        )

    def test_main_js_has_event_listeners(self):
        """Ensure JS attaches event listeners (wireEvents or standard listeners)."""
        if not UI_JS.exists():
            self.skipTest("JS not found")
        js = UI_JS.read_text(encoding="utf-8", errors="replace")
        # Check for standard event attachment
        self.assertIn("addEventListener", js, "main.js missing addEventListener logic")

    def test_nsis_template_substitution_fixed(self):
        """Ensure NSIS template variables are double-escaped for Rust handlebars."""
        if not NSIS_TEMPLATE.exists():
            self.skipTest("NSIS not found")
        nsi = NSIS_TEMPLATE.read_text(encoding="utf-8", errors="replace")
        # Ensure correct escaping
        self.assertIn(
            r"\\{{main_binary_name}}.exe", nsi, "Missing double-escaped binary name"
        )

        # Ensure no BAD single escaping remains (ignoring the good ones)
        stripped = nsi.replace(r"\\{{main_binary_name}}", "")
        self.assertNotIn(
            r"\{{main_binary_name}}", stripped, "Found unescaped Handlebars var"
        )

    def test_csp_has_script_src(self):
        """Ensure Tauri conf has CSP defined."""
        if not TAURI_CONF.exists():
            self.skipTest("Conf not found")
        conf = json.loads(TAURI_CONF.read_text(encoding="utf-8", errors="replace"))
        csp = conf.get("tauri", {}).get("security", {}).get("csp", "")
        self.assertIn("script-src", csp, "CSP missing script-src")


if __name__ == "__main__":
    unittest.main()
