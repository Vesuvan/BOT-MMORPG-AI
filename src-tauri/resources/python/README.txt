Place a Windows Python runtime here for production builds.

Recommended: extract the Python embeddable package so this exists:
  src-tauri/resources/python/python.exe
  src-tauri/resources/python/Lib/...

At runtime the app copies it to:
  %LOCALAPPDATA%\BOT-MMORPG-AI\runtime\py\python\
Then creates a venv at:
  %LOCALAPPDATA%\BOT-MMORPG-AI\runtime\py\venv\
