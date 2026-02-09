# Changelog

All notable changes to BOT-MMORPG-AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-09

### Added
- Tauri desktop application with NSIS Windows installer
- Python ML backend with PyTorch neural network models
- ModelHub: local model catalog, discovery, and session management
- Setup Wizard for guided first-run configuration
- AI Chat integration (Gemini, OpenAI, Ollama)
- Game profiles for Genshin Impact, WoW, FFXIV, Lost Ark, GW2
- Hardware-aware model selection and resolution recommendations
- Training School UI for data collection, training, and inference
- Screen capture with multi-monitor support
- Gamepad input simulation (vJoy, Interception drivers)
- CI/CD with GitHub Actions (test, lint, build, release)
- 120 automated tests covering config, models, bridge, and UI

### Fixed
- NSIS template resource bundling (Handlebars `{{this}}` vs `{{@key}}`)
- CI workflow downloads vJoySetup.exe from official release
- `.gitignore` whitelists Tauri config JSON and driver executables
- Git repository size reduced from 1.6 GB to 95 MB

### Security
- Tauri filesystem permissions restricted to granular read/write/dir ops
- CI lint and security checks now block on failure
- Secure data loader with SHA-256 hash verification for model files
