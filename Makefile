.PHONY: help dev test lint format check build run clean

# ── Default ──
help:
	@echo "Zelos — Open Multi-Agent Orchestration Runtime"
	@echo ""
	@echo "Usage:"
	@echo "  make dev        Start Runtime in hot-reload dev mode"
	@echo "  make test       Run all tests"
	@echo "  make lint       Check code with Ruff"
	@echo "  make format     Auto-format code with Ruff"
	@echo "  make check      Run lint + test (CI pipeline)"
	@echo "  make build      Build Docker image"
	@echo "  make run        Start Runtime via Docker Compose"
	@echo "  make clean      Remove build artifacts"

# ── Development ──
dev:
	python3 start.py

# ── Testing ──
test:
	python3 -m pytest tests/ -v --tb=short

test-cov:
	python3 -m pytest tests/ -v --tb=short --cov=zelos --cov=zelos_sdk --cov-report=term-missing

# ── Lint & Format ──
lint:
	python3 -m ruff check .

format:
	python3 -m ruff format .

check: lint test
	@echo "✅ All checks passed"

# ── Docker ──
build:
	docker build -t zelos:0.6.0 .
	docker build --target dev -t zelos:dev .

run:
	docker compose up -d runtime

run-storage:
	docker compose --profile storage up -d

stop:
	docker compose down

# ── Clean ──
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage coverage.xml
