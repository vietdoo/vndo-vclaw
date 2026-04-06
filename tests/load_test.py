"""
Locust load + fault-tolerance test for vndo-vclaw API.

Run:
    locust -f tests/load_test.py --host http://localhost:8000
    # headless:
    locust -f tests/load_test.py --headless --host http://localhost:8000 \
        --users 50 --spawn-rate 5 --run-time 60s --html tests/load_report.html
"""
import random
import string
import uuid

from locust import HttpUser, between, events, task


def rand_str(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


class VclawAPIUser(HttpUser):
    """Simulates a regular API consumer: logs, events, stats."""

    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        self.workflow_ids: list[str] = [f"wf-{rand_str()}" for _ in range(5)]
        self.event_ids: list[str] = []

    # ── Health ────────────────────────────────────────────────────────────
    @task(1)
    def health_check(self) -> None:
        self.client.get("/health", name="/health")

    # ── Logs ──────────────────────────────────────────────────────────────
    @task(10)
    def create_log(self) -> None:
        payload = {
            "level": random.choice(["DEBUG", "INFO", "INFO", "INFO", "WARNING", "ERROR"]),
            "message": f"Test log {rand_str(16)}",
            "source": random.choice(["api", "worker", "scheduler", "kafka-consumer"]),
            "trace_id": str(uuid.uuid4()),
            "extra": {"attempt": random.randint(1, 5)},
        }
        self.client.post("/api/v1/logs", json=payload, name="POST /api/v1/logs")

    @task(5)
    def list_logs(self) -> None:
        level = random.choice(["INFO", "WARNING", "ERROR", None, None])
        params = {"page": 1, "size": 20}
        if level:
            params["level"] = level
        self.client.get("/api/v1/logs", params=params, name="GET /api/v1/logs")

    @task(2)
    def log_stats(self) -> None:
        self.client.get("/api/v1/logs/stats", name="GET /api/v1/logs/stats")

    # ── Events ────────────────────────────────────────────────────────────
    @task(8)
    def create_event(self) -> None:
        wf_id = random.choice(self.workflow_ids)
        payload = {
            "workflow_id": wf_id,
            "workflow_name": f"Workflow {wf_id}",
            "event_type": random.choice(["task.start", "task.complete", "task.fail", "workflow.trigger"]),
            "status": random.choice(["pending", "running"]),
            "payload": {"step": rand_str(4), "retry": random.randint(0, 2)},
            "trace_id": str(uuid.uuid4()),
        }
        with self.client.post(
            "/api/v1/events", json=payload, name="POST /api/v1/events", catch_response=True
        ) as resp:
            if resp.status_code == 201:
                try:
                    event_id = resp.json().get("id")
                    if event_id:
                        self.event_ids.append(event_id)
                        if len(self.event_ids) > 100:
                            self.event_ids = self.event_ids[-50:]
                except Exception:
                    pass
            elif resp.status_code >= 500:
                resp.failure(f"Server error: {resp.status_code}")

    @task(4)
    def update_event(self) -> None:
        if not self.event_ids:
            return
        event_id = random.choice(self.event_ids)
        update = {
            "status": random.choice(["success", "failed"]),
            "duration_ms": round(random.uniform(10, 5000), 2),
        }
        self.client.patch(
            f"/api/v1/events/{event_id}",
            json=update,
            name="PATCH /api/v1/events/:id",
        )

    @task(3)
    def list_events(self) -> None:
        params = {"page": 1, "size": 20}
        if random.random() < 0.5:
            params["workflow_id"] = random.choice(self.workflow_ids)
        self.client.get("/api/v1/events", params=params, name="GET /api/v1/events")

    @task(2)
    def event_stats(self) -> None:
        self.client.get("/api/v1/events/stats/summary", name="GET /api/v1/events/stats/summary")

    # ── Stats ─────────────────────────────────────────────────────────────
    @task(3)
    def system_stats(self) -> None:
        self.client.get("/api/v1/stats/system", name="GET /api/v1/stats/system")

    @task(2)
    def dashboard(self) -> None:
        self.client.get("/api/v1/stats/dashboard", name="GET /api/v1/stats/dashboard")


class HeavyWriteUser(HttpUser):
    """Stress-tests write path: burst log + event creation."""

    wait_time = between(0.01, 0.05)
    weight = 1

    @task(5)
    def burst_log(self) -> None:
        self.client.post(
            "/api/v1/logs",
            json={
                "level": "ERROR",
                "message": "Burst error " + rand_str(32),
                "source": "stress-test",
            },
            name="POST /api/v1/logs (burst)",
        )

    @task(5)
    def burst_event(self) -> None:
        self.client.post(
            "/api/v1/events",
            json={
                "workflow_id": f"stress-{rand_str(6)}",
                "event_type": "task.fail",
                "status": "failed",
                "error_message": "Intentional stress failure",
            },
            name="POST /api/v1/events (burst)",
        )


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs) -> None:
    stats = environment.stats
    total = stats.total
    print("\n=== Load test summary ===")
    print(f"  Total requests : {total.num_requests}")
    print(f"  Failures       : {total.num_failures} ({total.fail_ratio * 100:.1f}%)")
    print(f"  Median (ms)    : {total.median_response_time}")
    print(f"  95th pct (ms)  : {total.get_response_time_percentile(0.95)}")
    print(f"  RPS            : {total.current_rps:.1f}")
    if total.fail_ratio > 0.05:
        print("  WARNING: failure rate > 5%")
