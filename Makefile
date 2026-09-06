.PHONY: demo test build api web install help

help:
	@echo "ReviveAI - Autonomous Revenue Recovery Engine"
	@echo "Available commands:"
	@echo "  make demo     Reset demo environment to deterministic known state"
	@echo "  make test     Run full automated backend test suite (pytest)"
	@echo "  make build    Build web frontend for production"
	@echo "  make api      Run FastAPI backend development server"
	@echo "  make web      Run Next.js frontend development server"

demo:
	python scripts/reset_demo.py

test:
	pytest tests/ -v

build:
	cd apps/web && npm run build

api:
	cd apps/api && uvicorn app.main:app --reload --port 8000

web:
	cd apps/web && npm run dev
