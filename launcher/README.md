# BOT-MMORPG-AI Launcher

A gaming-style web-based launcher interface for the BOT-MMORPG-AI project.

## Features

- **Dashboard**: Overview of system status and quick actions
- **Teach Mode**: Record gameplay data for training
- **Train Brain**: Train the neural network model
- **Run Bot**: Execute the trained bot
- **AI Strategist**: Chat with Gemini AI for gaming advice and bot configuration tips

## Installation

1. Install the launcher dependencies:
```bash
cd launcher
pip install -r requirements.txt
```

2. (Optional) Set up Gemini API key for AI features:
```bash
# Create a .env file in the project root
echo "GEMINI_API_KEY=your_api_key_here" > ../.env
```

## Usage

Run the launcher from the launcher directory:

```bash
cd launcher
python launcher.py
```

Or run from the project root:

```bash
python launcher/launcher.py
```

The launcher will open in your default web browser at `http://localhost:8080`.

## Requirements

- Python 3.7+
- eel >= 0.16.0
- python-dotenv >= 1.0.0
- Chrome/Chromium browser (recommended) or any modern web browser

## AI Features

The launcher includes AI-powered features using Google's Gemini API:

- **AI Strategist Chat**: Get real-time advice on farming routes, character builds, and bot configuration
- **Training Log Analysis**: Analyze training logs to determine if your model needs more data
- **Text-to-Speech**: Voice feedback for important actions

To enable AI features, you need to set the `GEMINI_API_KEY` environment variable in a `.env` file in the project root.

## Structure

```
launcher/
├── launcher.py          # Main launcher backend
├── requirements.txt     # Python dependencies
├── README.md           # This file
└── web/
    └── main.html       # Frontend UI
```

## Notes

- The launcher expects the main project scripts to be located in `versions/0.01/`
- Make sure your game scripts (1-collect_data.py, 2-train_model.py, 3-test_model.py) are present in that directory
- The launcher provides a modern, user-friendly interface without modifying any existing project files
