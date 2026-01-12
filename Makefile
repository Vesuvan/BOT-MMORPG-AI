.PHONY: help install install-dev install-uv venv sync clean lint format format-check type-check test test-cov test-unit test-integration build docs clean-build clean-pyc clean-test clean-venv check all release install-launcher install-all collect-data train-model test-model artifact build-installer verify-installer test-installer clean-installer

# Default target
.DEFAULT_GOAL := help

# Command Definitions
# SYS_PYTHON: Uses your global python just for the 'help' menu (fast, no sync required)
SYS_PYTHON := python
# RUN_PYTHON: Uses 'uv run' to ensure code runs inside the virtual env
RUN_PYTHON := uv run python

# OS detection
ifeq ($(OS),Windows_NT)
	IS_WINDOWS := 1
else
	IS_WINDOWS := 0
endif

##@ General

help: ## Display this help message
	@echo "======================================================================="
	@echo " BOT-MMORPG-AI - AI Bot for MMORPG Games"
	@echo "======================================================================="
	@$(SYS_PYTHON) -c "import sys, re; \
	lines = [l.strip() for l in sys.stdin]; \
	print('Available commands:'); \
	[print(f'  {m.group(1):<20} {m.group(2)}') for l in lines if (m := re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', l))]" < $(MAKEFILE_LIST)
	@echo ""

##@ Installation & Setup

install-uv: ## Install uv package manager
	@echo Installing uv package manager...
ifeq ($(IS_WINDOWS),1)
	@powershell -NoProfile -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
else
	@sh -c "curl -LsSf https://astral.sh/uv/install.sh | sh"
endif
	@echo uv is installed
	@echo If 'uv' is not found, restart your terminal so PATH updates take effect.

venv: ## Create the virtual environment (Forces Python 3.10 for TensorFlow Windows compatibility)
	@echo Creating virtual environment with Python 3.10...
	@uv venv --python 3.10
	@echo Virtual environment created in .venv/

install: install-uv venv ## Install production dependencies
	@echo Installing production dependencies...
	@uv pip install -e .
	@echo Production dependencies installed

install-dev: install-uv venv ## Install development dependencies
	@echo Installing development dependencies...
	@uv pip install -e ".[dev]"
	@echo Development dependencies installed

install-launcher: install-uv venv ## Install launcher dependencies (Eel)
	@echo Installing launcher dependencies...
	@uv pip install -e ".[launcher]"
	@echo Launcher dependencies installed

install-all: install-uv venv ## Install all dependencies (requires pyproject.toml update)
	@echo Installing all dependencies...
	@uv pip install -e ".[all]"
	@echo All dependencies installed

sync: install-uv venv ## Sync dependencies using uv
	@echo Syncing dependencies with uv...
	@uv pip sync requirements.txt
	@echo Dependencies synced

##@ Code Quality

lint: ## Run all linters (flake8, pylint)
	@echo Running flake8...
	@$(RUN_PYTHON) -m flake8 src/ tests/ --max-line-length=100 --exclude=frontend/assets/backup,build,dist || $(RUN_PYTHON) -c "exit(0)"
	@echo Running pylint...
	@$(RUN_PYTHON) -m pylint src/bot_mmorpg --rcfile=pyproject.toml || $(RUN_PYTHON) -c "exit(0)"
	@echo Linting complete

format: ## Format code using black and isort
	@echo Formatting code with black...
	@$(RUN_PYTHON) -m black src/ tests/ --line-length=100 --exclude=frontend/assets/backup
	@echo Sorting imports with isort...
	@$(RUN_PYTHON) -m isort src/ tests/ --profile=black --line-length=100
	@echo Code formatted

format-check: ## Check code formatting
	@echo Checking code format...
	@$(RUN_PYTHON) -m black src/ tests/ --check --line-length=100 --exclude=frontend/assets/backup
	@$(RUN_PYTHON) -m isort src/ tests/ --check-only --profile=black --line-length=100
	@echo Format check complete

type-check: ## Run type checking with mypy
	@echo Running type checks...
	@$(RUN_PYTHON) -m mypy src/ --config-file=pyproject.toml || $(RUN_PYTHON) -c "exit(0)"
	@echo Type checking complete

check: format-check lint type-check ## Run all code quality checks

##@ Testing

test: ## Run all tests
	@echo Running all tests...
	@$(RUN_PYTHON) -m pytest tests/ -v
	@echo All tests passed

test-cov: ## Run tests with coverage report
	@echo Running tests with coverage...
	@$(RUN_PYTHON) -m pytest tests/ -v --cov=src/bot_mmorpg --cov-report=html --cov-report=term-missing
	@echo Coverage report generated in htmlcov/

test-unit: ## Run unit tests only
	@echo Running unit tests...
	@$(RUN_PYTHON) -m pytest tests/ -v -m unit
	@echo Unit tests passed

test-integration: ## Run integration tests only
	@echo Running integration tests...
	@$(RUN_PYTHON) -m pytest tests/ -v -m integration
	@echo Integration tests passed

##@ Building & Documentation

build: clean-build ## Build distribution packages
	@echo Building distribution packages...
	@uv pip install build
	@$(RUN_PYTHON) -m build
	@echo Distribution packages built in dist/

docs: ## Generate documentation using Sphinx
	@echo Generating documentation...
	@uv pip install -e ".[docs]"
	@cd docs && make html
	@echo Documentation generated in docs/_build/html/

##@ Cleaning

clean: clean-build clean-pyc clean-test clean-venv ## Remove all artifacts
	@echo Cleaned all artifacts

clean-venv: ## Remove virtual environment
	@echo Removing virtual environment...
	@$(SYS_PYTHON) -c "import shutil; shutil.rmtree('.venv', ignore_errors=True)"

clean-build: ## Remove build artifacts
	@echo Cleaning build artifacts...
	@$(SYS_PYTHON) -c "import shutil, os; dirs=['build', 'dist', '.eggs']; [shutil.rmtree(d, ignore_errors=True) for d in dirs];"
	@$(SYS_PYTHON) -c "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.egg-info')]"

clean-pyc: ## Remove Python file artifacts
	@echo Cleaning Python artifacts...
	@$(SYS_PYTHON) -c "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.py[co]')]"
	@$(SYS_PYTHON) -c "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*~')]"
	@$(SYS_PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"

clean-test: ## Remove test and coverage artifacts
	@echo Cleaning test artifacts...
	@$(SYS_PYTHON) -c "import shutil; dirs=['.tox', '.pytest_cache', 'htmlcov', '.mypy_cache']; [shutil.rmtree(d, ignore_errors=True) for d in dirs];"
	@$(SYS_PYTHON) -c "import os; os.remove('.coverage') if os.path.exists('.coverage') else None"

##@ Application Commands

collect-data: ## Run data collection script
	@echo Starting data collection...
	@$(RUN_PYTHON) versions/0.01/1-collect_data.py

train-model: ## Run model training script
	@echo Starting model training...
	@$(RUN_PYTHON) versions/0.01/2-train_model.py

test-model: ## Run model testing/playing script
	@echo Starting model testing...
	@$(RUN_PYTHON) versions/0.01/3-test_model.py

##@ Installer (Windows Only)

artifact: build-installer verify-installer ## Build Windows installer artifact (complete workflow)
	@echo ""
	@echo "========================================"
	@echo " Installer Build Complete!"
	@echo "========================================"
	@echo "Installer location: src-tauri/target/release/bundle/nsis/"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Test installer: make test-installer"
	@echo "  2. Test on Windows VM"
	@echo "  3. Create release: git tag v1.0.0 && git push origin v1.0.0"
	@echo ""

build-installer: ## Build the Windows installer
ifeq ($(IS_WINDOWS),1)
	@echo "========================================"
	@echo " Building Windows Installer"
	@echo "========================================"
	@echo "This will:"
	@echo "  1. Build Python backend with PyInstaller"
	@echo "  2. Build Tauri desktop application"
	@echo "  3. Create NSIS installer package"
	@echo ""
	@powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_pipeline.ps1
else
	@echo "========================================"
	@echo " Windows Installer Build"
	@echo "========================================"
	@echo "ERROR: Installer build is only supported on Windows."
	@echo ""
	@echo "To build the installer:"
	@echo "  1. Use a Windows machine or VM"
	@echo "  2. Install prerequisites: Python 3.10+, Rust, Tauri CLI"
	@echo "  3. Run: make artifact"
	@echo ""
	@echo "Or use GitHub Actions:"
	@echo "  - Push to GitHub: git push"
	@echo "  - Check Actions tab for build artifacts"
	@echo "  - Download installer from workflow run"
	@echo ""
	@exit 1
endif

verify-installer: ## Verify installer was built correctly
ifeq ($(IS_WINDOWS),1)
	@echo "========================================"
	@echo " Verifying Installer Build"
	@echo "========================================"
	@powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_installer.ps1
else
	@echo "========================================"
	@echo " Installer Verification"
	@echo "========================================"
	@echo "Verification is only available on Windows."
	@echo "Use GitHub Actions to verify builds on CI."
	@echo ""
endif

test-installer: ## Test the installer package
ifeq ($(IS_WINDOWS),1)
	@echo "========================================"
	@echo " Testing Installer Package"
	@echo "========================================"
	@powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test_installer.ps1
else
	@echo "========================================"
	@echo " Installer Testing"
	@echo "========================================"
	@echo "Testing is only available on Windows."
	@echo "Use GitHub Actions to test builds on CI."
	@echo ""
endif

clean-installer: ## Clean installer build artifacts
	@echo Cleaning installer artifacts...
ifeq ($(IS_WINDOWS),1)
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist, build, src-tauri/target, src-tauri/binaries, src-tauri/drivers, src-tauri/resources, *.spec"
else
	@rm -rf dist build src-tauri/target src-tauri/binaries src-tauri/drivers src-tauri/resources *.spec 2>/dev/null || true
endif
	@echo Installer artifacts cleaned

##@ Complete Workflows

all: install-dev format lint type-check test ## Run complete development workflow
	@echo Complete workflow finished successfully

release: clean build ## Prepare a release
	@echo Release prepared. Distribution packages in dist/
	@echo Next steps:
	@echo   1. Review CHANGELOG.md
	@echo   2. Update version in src/bot_mmorpg/__init__.py
	@echo   3. Create a git tag
	@echo   4. Push to repository
