# ==============================================================================
# Phoenix - Development Commands
# ==============================================================================
# Run `make help` to see all available commands.
# ==============================================================================

.PHONY: help dev down build clean logs deploy seed test lint setup
.DEFAULT_GOAL := help

# Colors
CYAN  := \033[36m
GREEN := \033[32m
RED   := \033[31m
RESET := \033[0m

help: ## Show this help message
	@echo ""
	@echo "$(CYAN)🔥 Phoenix - Available Commands$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""

setup: ## First time setup - install local dependencies
	@echo "$(CYAN)Setting up Phoenix locally...$(RESET)"
	@command -v docker >/dev/null 2>&1 || { echo "$(RED)Docker not found. Install Docker Desktop first.$(RESET)"; exit 1; }
	@command -v gcloud >/dev/null 2>&1 || { echo "$(RED)gcloud CLI not found. Install it first.$(RESET)"; exit 1; }
	@test -f .env || (echo "$(CYAN)Creating .env from template...$(RESET)" && cp .env.example .env)
	@echo "$(GREEN)Setup complete. Edit .env with your real values, then run 'make dev'.$(RESET)"

dev: ## Start all services locally with docker-compose
	@echo "$(CYAN)Starting Phoenix services...$(RESET)"
	docker-compose up --build

dev-detached: ## Start services in background
	docker-compose up --build -d
	@echo "$(GREEN)Phoenix is running. Dashboard: http://localhost:5173$(RESET)"

down: ## Stop all services
	docker-compose down

build: ## Build all service images
	docker-compose build

clean: ## Remove all containers, volumes, and built images
	docker-compose down -v --rmi all

logs: ## Tail logs from all services
	docker-compose logs -f

logs-agent: ## Tail logs from the agent only
	docker-compose logs -f agent

logs-gateway: ## Tail logs from the gateway only
	docker-compose logs -f gateway

logs-web: ## Tail logs from the web dashboard only
	docker-compose logs -f web

deploy: ## Deploy all services to Google Cloud Run
	@echo "$(CYAN)Deploying Phoenix to Google Cloud...$(RESET)"
	./infra/scripts/deploy-all.sh

seed: ## Seed demo GitLab repository with broken pipelines
	@echo "$(CYAN)Seeding demo data...$(RESET)"
	./infra/scripts/seed-demo-data.sh

test: ## Run all tests
	@echo "$(CYAN)Running tests...$(RESET)"
	cd apps/agent && python -m pytest
	cd apps/gateway && go test ./...
	cd apps/parser && cargo test
	cd apps/web && npm test

lint: ## Lint all code
	cd apps/agent && ruff check src/
	cd apps/gateway && gofmt -l .
	cd apps/parser && cargo clippy
	cd apps/web && npm run lint

agent-shell: ## Open a shell inside the agent container
	docker-compose exec agent /bin/bash

gateway-shell: ## Open a shell inside the gateway container
	docker-compose exec gateway /bin/sh

restart: ## Restart all services
	docker-compose restart

status: ## Show status of all services
	docker-compose ps
