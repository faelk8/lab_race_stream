# ExecPlan — MVP: Simulator -> Kafka -> Schema Registry -> Consumer

## 1. Objective

Deliver the first executable vertical slice of RaceStream Lab.

The developer must be able to run:

```bash
docker compose up
```

and observe 20 simulated cars publishing validated telemetry events to Kafka while a Python consumer receives them.

## 2. Scope

Included:

- Python simulator;
- 20 independent cars;
- telemetry domain model;
- Kafka producer;
- Kafka topic creation;
- Schema Registry;
- Avro serialization;
- Python consumer;
- structured logging;
- Docker Compose;
- unit tests;
- schema tests;
- integration smoke test.

Excluded:

- Flink;
- Spark;
- React;
- FastAPI/WebSocket;
- PostgreSQL;
- Debezium;
- ClickHouse;
- MinIO;
- Iceberg;
- Kubernetes;
- Grafana/Prometheus.

## 3. Target Flow

```text
20-car simulator
      |
      v
Avro serializer
      |
      v
Schema Registry
      |
      v
Kafka: race.telemetry.raw
      |
      v
Python consumer
```

## 4. Core Domain

Implement independent vehicle state including:

- car_id;
- speed;
- gear;
- rpm;
- fuel;
- weight;
- lap;
- sector;
- track_progress;
- throttle;
- brake;
- tires;
- pit state.

Initial simulation physics may be simplified but must be deterministic under a configured seed.

## 5. Event Contract

Initial event type:

`race.telemetry.v1`

Required envelope:

- event_id;
- event_type;
- schema_version;
- event_time;
- produced_at;
- race_id;
- car_id.

## 6. Kafka

Topic:

`race.telemetry.raw`

Key:

`car_id`

Initial local partition count may be 6 or another documented reasonable development value.

## 7. Milestones

### Milestone 1 — Domain only

Build the simulator without Kafka.

Validate:

- 20 cars exist;
- states evolve;
- fuel decreases;
- weight reflects fuel;
- progress completes laps;
- deterministic seed works.

### Milestone 2 — Event model

Map domain state to immutable telemetry events.

### Milestone 3 — Kafka infrastructure

Add local Kafka and topic initialization.

### Milestone 4 — Schema Registry and Avro

Register schema and serialize events.

### Milestone 5 — Consumer

Consume and deserialize events.

### Milestone 6 — Docker Compose integration

All components start from one command.

## 8. Tests

Unit tests:

- fuel consumption;
- weight calculation;
- track progress;
- lap increment;
- gear bounds;
- deterministic behavior.

Contract tests:

- Avro event validates;
- required fields exist;
- schema version is correct.

Integration test:

- produce an event;
- consume it;
- deserialize it;
- compare expected identifiers.

## 9. Validation

Expected commands:

```bash
.venv/bin/ruff check src tests
.venv/bin/pytest
.venv/bin/mypy src tests
docker compose config
docker compose up --build
RUN_KAFKA_INTEGRATION=1 .venv/bin/pytest tests/integration -q
```

## 10. Done Criteria

MVP is complete only when:

- all 20 cars publish;
- events are schema-validated;
- consumer receives and deserializes events;
- tests pass;
- README contains exact local execution instructions.

## 11. Progress

- [x] Milestone 1 — deterministic 20-car domain simulator.
- [x] Milestone 2 — immutable telemetry event and validated v1 contract.
- [x] Milestone 3 — local Kafka KRaft service and topic initialization.
- [x] Milestone 4 — Avro serialization and Schema Registry registration.
- [x] Milestone 5 — Python consumer with explicit offset commits.
- [x] Milestone 6 — Docker Compose vertical slice.
- [x] Unit and contract tests: 10 passed.
- [x] Kafka integration round-trip: 1 passed with Compose running.
- [x] Ruff, mypy and Docker Compose configuration checks.
- [x] README quick start and architecture decision records.

Validation checkpoint (2026-10-02):

- `.venv/bin/pytest -q`: 10 passed, 1 integration test skipped by default.
- `RUN_KAFKA_INTEGRATION=1 .venv/bin/pytest tests/integration/test_kafka_roundtrip.py -q`: 1 passed.
- `.venv/bin/ruff check src tests`: passed.
- `.venv/bin/mypy src tests`: passed.
- `docker compose config --quiet`: passed.
- `docker compose up --build -d`: Kafka and Schema Registry healthy; producer and consumer running.
- Schema Registry subject observed: `race.telemetry.raw-value`.

## 12. Resumption Notes

The MVP implementation is complete and running locally. There are no unfinished MVP milestones. The GitHub repository has not yet been initialized or pushed at this checkpoint.

When resuming:

1. Read `AGENTS.md`, `PLANS.md`, this ExecPlan, and `docs/adr/`.
2. Run `git status --short --branch` from this project directory; the project must have its own `.git` directory and must not use the parent home-directory repository.
3. Run `.venv/bin/pytest -q`, `.venv/bin/ruff check src tests`, and `.venv/bin/mypy src tests`.
4. Inspect `docker compose ps`; use `docker compose logs -f consumer` to observe events.
5. Choose a new, explicitly scoped phase. For stream processing, start from `execplan-streaming.md`; do not add Flink, Spark, frontend, databases, CDC, or Kubernetes as part of this MVP.
