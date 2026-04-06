#!/usr/bin/env bash
# Wait for Postgres, Redis, and Kafka to be ready before starting the API.
set -e

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
KAFKA_HOST="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
KAFKA_HOST="${KAFKA_HOST%%:*}"
KAFKA_PORT="${KAFKA_BOOTSTRAP_SERVERS##*:}"

wait_for() {
    local name="$1" host="$2" port="$3" retries=30
    echo "Waiting for $name at $host:$port..."
    for i in $(seq 1 $retries); do
        if nc -z "$host" "$port" 2>/dev/null; then
            echo "$name is ready."
            return 0
        fi
        sleep 2
    done
    echo "ERROR: $name did not become ready in time."
    exit 1
}

wait_for "PostgreSQL" "$POSTGRES_HOST" "$POSTGRES_PORT"
wait_for "Redis" "$REDIS_HOST" "$REDIS_PORT"

echo "All dependencies ready."
