"""Saúde e métricas operacionais sem dependências de frameworks."""

import json
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class OperationalHealth:
    """Registre batimentos, dependências e métricas com acesso entre threads."""

    def __init__(
        self, timeout: float = 60, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """Configure o prazo máximo sem progresso do loop operacional."""
        self.timeout = timeout
        self.clock = clock
        self._heartbeat = clock()
        self._checks: dict[str, bool] = {"inicializado": False}
        self._metrics: dict[str, float] = {}
        self._counters: set[str] = set()
        self._lock = threading.Lock()
        self._stopped = False

    def heartbeat(self, **checks: bool) -> None:
        """Atualize o batimento e as dependências observadas pelo serviço."""
        with self._lock:
            self._heartbeat = self.clock()
            self._checks.update(checks)

    def set(self, name: str, value: float) -> None:
        """Atualize uma métrica agregada sem labels de alta cardinalidade."""
        with self._lock:
            self._metrics[name] = value

    def increment(self, name: str, amount: float = 1) -> None:
        """Incremente um contador monotônico."""
        with self._lock:
            self._counters.add(name)
            self._metrics[name] = self._metrics.get(name, 0) + amount

    def stop(self) -> None:
        """Marque o encerramento antes de liberar conexões externas."""
        with self._lock:
            self._stopped = True

    def snapshot(self) -> dict[str, object]:
        """Retorne saúde sem expor exceções, endereços ou credenciais."""
        with self._lock:
            age = max(0.0, self.clock() - self._heartbeat)
            live = not self._stopped and age <= self.timeout
            return {
                "live": live,
                "ready": live and all(self._checks.values()),
                "checks": dict(self._checks),
                "heartbeat_age_seconds": age,
            }

    def metrics(self) -> str:
        """Exporte métricas em formato texto compatível com Prometheus."""
        snapshot = self.snapshot()
        with self._lock:
            values = dict(self._metrics)
            counters = set(self._counters)
        values.update(
            live=float(bool(snapshot["live"])),
            ready=float(bool(snapshot["ready"])),
            heartbeat_age_seconds=float(str(snapshot["heartbeat_age_seconds"])),
        )
        lines = []
        for name, value in sorted(values.items()):
            kind = "counter" if name in counters else "gauge"
            lines.extend(
                [f"# TYPE racestream_{name} {kind}", f"racestream_{name} {value}"]
            )
        return "\n".join(lines) + "\n"


def serve_health(health: OperationalHealth, port: int) -> ThreadingHTTPServer:
    """Abra o servidor operacional; o chamador deve encerrá-lo ao sair."""

    class Handler(BaseHTTPRequestHandler):
        """Sirva apenas saúde e métricas, sem registrar dados das requisições."""

        def do_GET(self) -> None:
            """Responda com 503 quando o serviço não estiver apto."""
            if self.path == "/metrics":
                body = health.metrics().encode()
                status, content_type = 200, "text/plain; version=0.0.4"
            elif self.path in ("/live", "/ready"):
                snapshot = health.snapshot()
                status = 200 if snapshot[self.path[1:]] else 503
                body = json.dumps(snapshot).encode()
                content_type = "application/json"
            else:
                status, body, content_type = 404, b"", "text/plain"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            """Evite logs de sondagem repetitivos."""

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
