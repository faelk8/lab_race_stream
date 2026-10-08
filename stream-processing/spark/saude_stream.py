"""Avalie atividade e progresso do Spark sem confundir ociosidade com falha."""

import time
from typing import Any


class QueryHealth:
    """Detecte uma query parada ou um micro-lote sem progresso prolongado."""

    def __init__(self, timeout: float = 300) -> None:
        """Configure o limite de execução de um único micro-lote."""
        self.timeout = timeout
        self.batch: int | None = None
        self.busy_since: float | None = None

    def observe(self, query: Any, now: float | None = None) -> dict[str, float]:
        """Retorne prontidão e métricas usando o estado público da query."""
        now = time.monotonic() if now is None else now
        progress = query.lastProgress or {}
        batch = progress.get("batchId")
        if batch != self.batch:
            self.batch = batch
            self.busy_since = None
        busy = query.status.get("isTriggerActive", False)
        if busy:
            if self.busy_since is None:
                self.busy_since = now
        else:
            self.busy_since = None
        stalled = self.busy_since is not None and now - self.busy_since > self.timeout
        return {
            "query_ready": float(query.isActive and not stalled),
            "spark_input_rows": float(progress.get("numInputRows", 0)),
            "spark_batch_duration_seconds": float(
                progress.get("durationMs", {}).get("triggerExecution", 0)
            )
            / 1000,
            "spark_batch_id": float(batch if batch is not None else -1),
            "spark_trigger_active": float(busy),
        }
