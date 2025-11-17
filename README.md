# BOT-MMORPG-AI

<div align="center">

![Bot MMORPG AI](./assets/images/posts/README/genshin-impact.jpg)

**AI-Powered Bot for MMORPG and RPG Games**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.8%2B-orange.svg)](https://www.tensorflow.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Documentation](#documentation) • [Contributing](#contributing)

</div>

---

## About

**BOT-MMORPG-AI** is a sophisticated artificial intelligence system designed to autonomously play MMORPG (Massively Multiplayer Online Role-Playing Games) and RPG games using deep learning and computer vision. The bot learns from gameplay recordings and uses neural networks to make intelligent decisions in real-time.

### Primary Game Target

The project primarily targets **[Genshin Impact](https://genshin.mihoyo.com/)**, but the architecture is designed to be adaptable to other games including:
- New World
- World of Warcraft
- Guild Wars 2
- Final Fantasy XIV
- Elder Scrolls Online
- And more...

### Project Objectives

1. **General Neural Network**: Develop an adaptive neural network architecture that can be trained for different video games
2. **Cloud Infrastructure**: Build scalable local and cloud infrastructure for data recording, processing, and model training
3. **Community Driven**: Foster learning, collaboration, and knowledge sharing within the AI Gaming Community

---

## Features

### Core Capabilities

- **Auto Exploration**: Navigate from point A to point B autonomously
- **Combat AI**: Engage and defeat enemies in dungeons
- **Item Collection**: Automatically collect items and resources
- **Multi-Input Support**: Handles both keyboard and gamepad inputs
- **Real-time Screen Capture**: Captures and processes game screens at 60 FPS
- **Deep Learning Models**: Uses state-of-the-art CNN architectures (Inception V3, ResNet, etc.)
- **Motion Detection**: Prevents the bot from getting stuck using computer vision
- **Modular Architecture**: Easily extendable and customizable

### Technical Features

- **TensorFlow/TFLearn** neural network implementation
- **OpenCV** for real-time image processing
- **Computer Vision** for path detection and obstacle avoidance
- **Transfer Learning** support for multiple model architectures
- **Data Augmentation** for improved model performance
- **Production-Ready**: Complete with testing, linting, and CI/CD configuration

---

## Installation

### Prerequisites

- **Operating System**: Windows 10/11 (for game compatibility)
- **Python**: 3.8 - 3.11
- **GPU**: NVIDIA GPU with CUDA support (recommended for training)
- **Game**: Genshin Impact (or your target game) installed
- **Controller**: Xbox controller or equivalent (optional but recommended)

### Quick Start with UV (Recommended)

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/ruslanmv/BOT-MMORPG-AI.git
cd BOT-MMORPG-AI

# Install production dependencies
make install

# Or install all dependencies including dev tools
make install-all
```

### Traditional Installation

```bash
# Clone the repository
git clone https://github.com/ruslanmv/BOT-MMORPG-AI.git
cd BOT-MMORPG-AI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"
```

---

## Usage

### Step 1: Data Collection

Record gameplay data to train the neural network:

```bash
# Using Makefile
make collect-data

# Or directly
python versions/0.01/1-collect_data.py
```

**Setup for Data Collection:**
1. Open your Genshin Impact game
2. Set resolution to 1920x1080 (fullscreen)
3. Position your character at the starting point
4. Set in-game time to 12:00
5. Connect your controller (if using gamepad mode)
6. Run the collection script
7. Play normally - the bot will record your actions

**Controls during collection:**
- `T`: Pause/unpause recording
- `Q`: Stop and save

### Step 2: Train the Model

Train the neural network on collected data:

```bash
# Using Makefile
make train-model

# Or directly
python versions/0.01/2-train_model.py
```

The training process will:
- Load preprocessed training data
- Train the Inception V3 model
- Save checkpoints every 10 batches
- Generate validation metrics

### Step 3: Test the Model

Deploy the trained model to play autonomously:

```bash
# Using Makefile
make test-model

# Or directly
python versions/0.01/3-test_model.py
```

**Setup for Testing:**
1. Open your Genshin Impact game
2. Position your character at the bridge of Mondstadt
3. Set in-game time to 12:00
4. Verify controller is connected
5. Run the test script
6. Switch to game window

**Controls during testing:**
- `T`: Pause/unpause AI
- `ESC`: Stop the bot

---

## Project Structure

```
BOT-MMORPG-AI/
├── src/
│   └── bot_mmorpg/          # Main package source code
│       ├── __init__.py
│       ├── models/          # Neural network architectures
│       ├── utils/           # Utility functions
│       └── scripts/         # Entry point scripts
├── versions/
│   └── 0.01/                # Version-specific implementations
│       ├── 1-collect_data.py
│       ├── 2-train_model.py
│       ├── 3-test_model.py
│       ├── models.py        # Model definitions
│       ├── grabscreen.py    # Screen capture
│       ├── getkeys.py       # Keyboard input
│       ├── getgamepad.py    # Gamepad input
│       └── directkeys.py    # Key simulation
├── frontend/
│   ├── input_record/        # Input recording utilities
│   └── video_record/        # Video recording utilities
├── tests/                   # Test suite
├── assets/                  # Images and resources
├── pyproject.toml          # Project configuration
├── Makefile                # Build automation
├── LICENSE                 # Apache 2.0 License
└── README.md              # This file
```

---

## Development

### Code Quality

```bash
# Format code
make format

# Run linters
make lint

# Type checking
make type-check

# Run all checks
make check
```

### Testing

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test types
make test-unit        # Unit tests only
make test-integration # Integration tests only
make test-fast        # Exclude slow tests
```

### Building

```bash
# Build distribution packages
make build

# Generate documentation
make docs

# Full CI pipeline
make ci
```

---

## Documentation

### Neural Network Architectures

The project supports multiple neural network architectures:

| Model | Size | Top-1 Acc | Top-5 Acc | Parameters | Inference (GPU) |
|-------|------|-----------|-----------|------------|-----------------|
| InceptionV3 | 92 MB | 77.9% | 93.7% | 23.9M | 6.9 ms |
| ResNet50 | 98 MB | 74.9% | 92.1% | 25.6M | 4.6 ms |
| ResNet101 | 171 MB | 76.4% | 92.8% | 44.7M | 5.2 ms |
| VGG16 | 528 MB | 71.3% | 90.1% | 138.4M | 4.2 ms |
| MobileNetV2 | 14 MB | 71.3% | 90.1% | 3.5M | 3.8 ms |

### Output Classes

The model predicts 29 different actions:
- **Keyboard** (9): W, S, A, D, WA, WD, SA, SD, NOKEY
- **Gamepad** (20): LT, RT, Lx, Ly, Rx, Ry, D-Pad, Buttons (A, B, X, Y, etc.)

### Training Data Format

Data is stored as NumPy arrays:
- **Input**: Screen captures (480x270x3 RGB images)
- **Output**: Multi-hot encoded action vectors (29 classes)
- **Format**: `.npy` files with 500 samples each

---

## Advanced Features

### Jupyter Notebooks

For interactive development and experimentation:

```bash
# Install Jupyter dependencies
pip install -e ".[jupyter]"

# Launch JupyterLab
jupyter lab
```

Available notebooks in `versions/0.01/`:
- Data collection and preprocessing
- Model training with visualizations
- Data cleaning and augmentation
- Way identification using OpenCV
- Intermediate representation visualization

### Cloud Training

The project supports cloud-based training on:
- **Google Colab**: Free GPU training
- **AWS EMR**: Scalable cluster training
- **Azure ML**: Enterprise-grade training
- **Google Cloud AI Platform**: Distributed training

### Experimental Features

- **U-Net Models**: For semantic segmentation of game paths
- **LSTM Networks**: For temporal action prediction
- **ResNeXt**: Advanced residual network architectures
- **3D Convolutions**: For multi-frame temporal learning

---

## Performance Optimization

### Motion Detection

The bot uses motion detection to prevent getting stuck:
```python
motion_req = 800  # Minimum motion threshold
log_len = 25      # Motion history length
```

When stuck, the bot executes random evasive maneuvers.

### Prediction Weighting

Custom weights applied to predictions for game-specific behavior:
```python
weights = [4.5, 0.1, 0.1, 0.1, 1.8, 1.8, 0.5, 0.5, 0.2, ...]
```

---

## Troubleshooting

### Common Issues

**Issue**: Model not loading
- **Solution**: Ensure model files are in `model/` directory

**Issue**: Screen capture not working
- **Solution**: Run game in fullscreen 1920x1080 resolution

**Issue**: Bot getting stuck
- **Solution**: Adjust `motion_req` threshold in test script

**Issue**: Low FPS during recording
- **Solution**: Lower capture resolution or use faster storage

**Issue**: CUDA out of memory
- **Solution**: Reduce batch size in training configuration

---

## Contributing

We welcome contributions from the community!

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add docstrings to all functions and classes
- Include type hints for function signatures
- Write unit tests for new features
- Update documentation as needed
- Run `make check` before submitting

### Code of Conduct

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

---

## Community

Join our community for support, discussions, and collaboration:

- **Slack**: [aws-ml-group.slack.com](https://aws-ml-group.slack.com/)
- **GitHub Issues**: [Report bugs and request features](https://github.com/ruslanmv/BOT-MMORPG-AI/issues)
- **Website**: [ruslanmv.com](https://ruslanmv.com/)

---

## Acknowledgments

This project builds upon excellent work from the community:

- **[gamePyd](https://github.com/4amVim/gamePyd)** - Game control utilities
- **[vJoy](http://vjoystick.sourceforge.net/)** - Virtual joystick interface
- **[ScpVBus](https://github.com/nefarius/ScpVBus)** by [nefarius](https://github.com/nefarius)
- **[PYXInput](https://github.com/bayangan1991/PYXInput)** contributors
- **[PyGTA5](https://github.com/Sentdex/pygta5)** by Sentdex
- **Inception V3** architecture by Google Research

Special thanks to the AI Gaming Community for their continuous support and feedback.

---

## Roadmap

### Version 1.1 (Q2 2025)
- [ ] Multi-game support framework
- [ ] Web-based dashboard for monitoring
- [ ] Improved data augmentation pipeline
- [ ] Distributed training support

### Version 1.2 (Q3 2025)
- [ ] Reinforcement learning integration
- [ ] Real-time model updating
- [ ] Cloud storage integration (S3, MinIO)
- [ ] Performance profiling tools

### Version 2.0 (Q4 2025)
- [ ] Generalized game agent framework
- [ ] Plugin system for custom games
- [ ] Advanced reward shaping
- [ ] Model compression for edge deployment

---

## Citation

If you use this project in your research, please cite:

```bibtex
@software{magana2025botmmorpgai,
  author = {Magana Vsevolodovna, Ruslan},
  title = {BOT-MMORPG-AI: AI-Powered Bot for MMORPG Games},
  year = {2025},
  url = {https://github.com/ruslanmv/BOT-MMORPG-AI},
  version = {1.0.0}
}
```

---

## License

This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSE) file for details.

```
Copyright 2025 Ruslan Magana Vsevolodovna

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

## Author

**Ruslan Magana Vsevolodovna**

- Website: [ruslanmv.com](https://ruslanmv.com/)
- Email: contact@ruslanmv.com
- GitHub: [@ruslanmv](https://github.com/ruslanmv)

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ruslanmv/BOT-MMORPG-AI&type=Date)](https://star-history.com/#ruslanmv/BOT-MMORPG-AI&Date)

---

<div align="center">

**Made with ❤️ by the AI Gaming Community**

[⬆ back to top](#bot-mmorpg-ai)

</div>
