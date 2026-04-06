.PHONY: help build up down restart logs ps migrate shell test load-test clean

help:
	@echo "vndo-vclaw — available commands:"
	@echo "  make build        Build Docker images"
	@echo "  make up           Start all services"
	@echo "  make down         Stop all services"
	@echo "  make restart      Restart API service"
	@echo "  make logs         Follow logs from all services"
	@echo "  make logs-api     Follow API logs"
	@echo "  make ps           Show running containers"
	@echo "  make migrate      Run DB migrations"
	@echo "  make shell        Open shell inside API container"
	@echo "  make test         Run unit tests"
	@echo "  make load-test    Run Locust load test (headless, 60s)"
	@echo "  make clean        Remove volumes and containers"

build:
	docker compose build --no-cache

up:
	cp -n .env.example .env 2>/dev/null || true
	docker compose up -d --wait

down:
	docker compose down

restart:
	docker compose restart api

logs:
	docker compose logs -f --tail=100

logs-api:
	docker compose logs -f api --tail=200

ps:
	docker compose ps

migrate:
	docker compose run --rm migrate

shell:
	docker compose exec api /bin/bash

test:
	docker compose run --rm --no-deps \
	  -e POSTGRES_HOST=localhost \
	  -e REDIS_HOST=localhost \
	  -e KAFKA_BOOTSTRAP_SERVERS=localhost:9092 \
	  api pytest tests/ -v --tb=short

load-test:
	@echo "Running load test — ensure stack is up with: make up"
	locust -f tests/load_test.py \
	  --headless \
	  --host http://localhost:8000 \
	  --users 50 \
	  --spawn-rate 5 \
	  --run-time 60s \
	  --html tests/load_report.html

clean:
	docker compose down -v --remove-orphans
	docker system prune -f
