"""Verifique falhas, ociosidade e recuperação das sondagens operacionais."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from racestream.infrastructure.operational_health import OperationalHealth


def test_ready_requires_dependencies_and_fresh_heartbeat():
    now = [0.0]
    health = OperationalHealth(timeout=10, clock=lambda: now[0])
    assert health.snapshot()["live"]
    assert not health.snapshot()["ready"]
    health.heartbeat(inicializado=True, kafka=True, postgres=True)
    assert health.snapshot()["ready"]
    health.heartbeat(kafka=False)
    assert not health.snapshot()["ready"]
    health.heartbeat(kafka=True)
    now[0] = 11
    assert not health.snapshot()["live"]
    health.heartbeat()
    assert health.snapshot()["ready"]
    health.stop()
    assert not health.snapshot()["live"]


def test_metrics_have_counters_without_race_labels():
    health = OperationalHealth()
    health.increment("consumer_events_total", 20)
    health.increment("consumer_events_total", 2)
    health.set("outbox_pending", 7)
    metrics = health.metrics()
    assert "racestream_consumer_events_total 22" in metrics
    assert "# TYPE racestream_consumer_events_total counter" in metrics
    assert "racestream_outbox_pending 7" in metrics
    assert "race_id" not in metrics


def test_spark_idle_busy_stalled_and_recovered():
    path = Path("stream-processing/spark/saude_stream.py")
    spec = importlib.util.spec_from_file_location("saude_stream", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monitor = module.QueryHealth(timeout=30)
    query = SimpleNamespace(
        isActive=True, lastProgress=None, status={"isTriggerActive": False}
    )
    assert monitor.observe(query, 0)["query_ready"] == 1
    assert monitor.observe(query, 1000)["query_ready"] == 1
    query.status["isTriggerActive"] = True
    assert monitor.observe(query, 1001)["query_ready"] == 1
    assert monitor.observe(query, 1032)["query_ready"] == 0
    query.lastProgress = {
        "batchId": 1,
        "numInputRows": 20,
        "durationMs": {"triggerExecution": 2500},
    }
    result = monitor.observe(query, 1033)
    assert result["query_ready"] == 1
    assert result["spark_input_rows"] == 20
    assert result["spark_batch_duration_seconds"] == 2.5
    query.isActive = False
    assert monitor.observe(query, 1034)["query_ready"] == 0


def test_api_readiness_is_closed_until_probe_and_live_stays_available():
    from racestream.interfaces.api import create_app

    app = create_app()
    endpoints = {
        route.path: route.endpoint for route in app.routes if hasattr(route, "endpoint")
    }
    assert endpoints["/live"]() == {"status": "ok"}
    assert endpoints["/ready"]().status_code == 503
    assert "racestream_ready 0.0" in endpoints["/metrics"]()


def test_dependency_failure_does_not_leak_secrets(monkeypatch, caplog):
    from racestream.infrastructure import dependency_probe

    def broken(*args, **kwargs):
        raise RuntimeError("senha-na-excecao")

    monkeypatch.setenv("DATABASE_URL", "postgresql://teste")
    monkeypatch.setattr(dependency_probe.psycopg, "connect", broken)
    monkeypatch.setattr(dependency_probe, "AdminClient", broken)
    assert dependency_probe.check_dependencies() == {"postgres": False, "kafka": False}
    assert "senha-na-excecao" not in caplog.text
