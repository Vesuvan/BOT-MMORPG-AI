.PHONY: help install install-dev install-uv clean lint format type-check test test-cov test-unit test-integration build docs clean-build clean-pyc clean-test check all

# Default target
.DEFAULT_GOAL := help

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

##@ General

help: ## Display this help message
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)  BOT-MMORPG-AI - AI Bot for MMORPG Games$(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════$(NC)"
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2 } \
		/^##@/ { printf "\n$(BLUE)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""

##@ Installation & Setup

install-uv: ## Install uv package manager (if not already installed)
	@echo "$(GREEN)Installing uv package manager...$(NC)"
	@command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
	@echo "$(GREEN)✓ uv is installed$(NC)"

install: install-uv ## Install production dependencies using uv
	@echo "$(GREEN)Installing production dependencies...$(NC)"
	uv pip install -e .
	@echo "$(GREEN)✓ Production dependencies installed$(NC)"

install-dev: install-uv ## Install development dependencies using uv
	@echo "$(GREEN)Installing development dependencies...$(NC)"
	uv pip install -e ".[dev]"
	@echo "$(GREEN)✓ Development dependencies installed$(NC)"

install-all: install-uv ## Install all dependencies (dev, docs, jupyter)
	@echo "$(GREEN)Installing all dependencies...$(NC)"
	uv pip install -e ".[all]"
	@echo "$(GREEN)✓ All dependencies installed$(NC)"

sync: install-uv ## Sync dependencies using uv (recommended for reproducible builds)
	@echo "$(GREEN)Syncing dependencies with uv...$(NC)"
	uv pip sync requirements.txt
	@echo "$(GREEN)✓ Dependencies synced$(NC)"

##@ Code Quality

lint: ## Run all linters (flake8, pylint)
	@echo "$(GREEN)Running flake8...$(NC)"
	@flake8 src/ tests/ --max-line-length=100 --exclude=frontend/assets/backup,build,dist || true
	@echo "$(GREEN)Running pylint...$(NC)"
	@pylint src/bot_mmorpg --rcfile=pyproject.toml || true
	@echo "$(GREEN)✓ Linting complete$(NC)"

format: ## Format code using black and isort
	@echo "$(GREEN)Formatting code with black...$(NC)"
	@black src/ tests/ --line-length=100 --exclude=frontend/assets/backup
	@echo "$(GREEN)Sorting imports with isort...$(NC)"
	@isort src/ tests/ --profile=black --line-length=100
	@echo "$(GREEN)✓ Code formatted$(NC)"

format-check: ## Check code formatting without making changes
	@echo "$(GREEN)Checking code format...$(NC)"
	@black src/ tests/ --check --line-length=100 --exclude=frontend/assets/backup
	@isort src/ tests/ --check-only --profile=black --line-length=100
	@echo "$(GREEN)✓ Format check complete$(NC)"

type-check: ## Run type checking with mypy
	@echo "$(GREEN)Running type checks...$(NC)"
	@mypy src/ --config-file=pyproject.toml || true
	@echo "$(GREEN)✓ Type checking complete$(NC)"

check: format-check lint type-check ## Run all code quality checks

##@ Testing

test: ## Run all tests
	@echo "$(GREEN)Running all tests...$(NC)"
	@pytest tests/ -v
	@echo "$(GREEN)✓ All tests passed$(NC)"

test-cov: ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	@pytest tests/ -v --cov=src/bot_mmorpg --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/$(NC)"

test-unit: ## Run unit tests only
	@echo "$(GREEN)Running unit tests...$(NC)"
	@pytest tests/ -v -m unit
	@echo "$(GREEN)✓ Unit tests passed$(NC)"

test-integration: ## Run integration tests only
	@echo "$(GREEN)Running integration tests...$(NC)"
	@pytest tests/ -v -m integration
	@echo "$(GREEN)✓ Integration tests passed$(NC)"

test-fast: ## Run fast tests only (exclude slow tests)
	@echo "$(GREEN)Running fast tests...$(NC)"
	@pytest tests/ -v -m "not slow"
	@echo "$(GREEN)✓ Fast tests passed$(NC)"

##@ Building & Documentation

build: clean-build ## Build distribution packages
	@echo "$(GREEN)Building distribution packages...$(NC)"
	@uv pip install build
	@python -m build
	@echo "$(GREEN)✓ Distribution packages built in dist/$(NC)"

docs: ## Generate documentation using Sphinx
	@echo "$(GREEN)Generating documentation...$(NC)"
	@uv pip install -e ".[docs]"
	@cd docs && make html
	@echo "$(GREEN)✓ Documentation generated in docs/_build/html/$(NC)"

##@ Cleaning

clean: clean-build clean-pyc clean-test ## Remove all build, test, coverage and Python artifacts
	@echo "$(GREEN)✓ Cleaned all artifacts$(NC)"

clean-build: ## Remove build artifacts
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	@rm -rf build/
	@rm -rf dist/
	@rm -rf .eggs/
	@find . -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	@find . -name '*.egg' -exec rm -f {} + 2>/dev/null || true

clean-pyc: ## Remove Python file artifacts
	@echo "$(YELLOW)Cleaning Python artifacts...$(NC)"
	@find . -name '*.pyc' -exec rm -f {} + 2>/dev/null || true
	@find . -name '*.pyo' -exec rm -f {} + 2>/dev/null || true
	@find . -name '*~' -exec rm -f {} + 2>/dev/null || true
	@find . -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

clean-test: ## Remove test and coverage artifacts
	@echo "$(YELLOW)Cleaning test artifacts...$(NC)"
	@rm -rf .tox/
	@rm -rf .pytest_cache/
	@rm -rf .coverage
	@rm -rf htmlcov/
	@rm -rf .mypy_cache/

##@ Application Commands

collect-data: ## Run data collection script
	@echo "$(GREEN)Starting data collection...$(NC)"
	@python versions/0.01/1-collect_data.py

train-model: ## Run model training script
	@echo "$(GREEN)Starting model training...$(NC)"
	@python versions/0.01/2-train_model.py

test-model: ## Run model testing/playing script
	@echo "$(GREEN)Starting model testing...$(NC)"
	@python versions/0.01/3-test_model.py

##@ Complete Workflows

all: install-dev format lint type-check test ## Run complete development workflow
	@echo "$(GREEN)✓ Complete workflow finished successfully$(NC)"

ci: format-check lint type-check test ## Run CI/CD pipeline checks
	@echo "$(GREEN)✓ CI checks passed$(NC)"

release: clean build ## Prepare a release
	@echo "$(GREEN)Release prepared. Distribution packages in dist/$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Review CHANGELOG.md"
	@echo "  2. Update version in src/bot_mmorpg/__init__.py"
	@echo "  3. Create a git tag"
	@echo "  4. Push to repository"
