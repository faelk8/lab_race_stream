# RaceStream Lab — Codex Engineering Instructions

## 1. Project Purpose

RaceStream Lab is an educational and portfolio-grade distributed systems and data engineering laboratory.

The platform simulates a motorsport race with 20 cars producing continuous telemetry.

The project must demonstrate realistic engineering practices while remaining reproducible on a local Ubuntu 24.04 LTS development environment.

## 2. Main Architecture

Expected evolution:

```text
Race Simulator
    -> Kafka
    -> Schema Registry
    -> Stream Processing Engine
         -> Apache Flink
            OR
         -> Spark Structured Streaming / PySpark
    -> Kafka derived topics
    -> FastAPI
    -> WebSocket
    -> React dashboard

Historical/event data
    -> ClickHouse
    -> MinIO/S3
    -> Apache Iceberg

Operational relational data
    -> PostgreSQL
    -> Debezium CDC
    -> Kafka
```

## 3. Engineering Principles

Always prioritize:

1. correctness;
2. readability;
3. explicit contracts;
4. testability;
5. maintainability;
6. observability;
7. loose coupling;
8. reproducibility;
9. idempotency where event replay is possible;
10. incremental delivery.

Do not introduce unnecessary abstractions.

Do not claim code works without running the relevant available checks.

Do not rewrite unrelated working code.

## 4. Development Environment

Primary environment:

- Ubuntu 24.04 LTS;
- Python 3.12+;
- Docker;
- Docker Compose;
- Git;
- GitHub;
- Kubernetes in later phases.

The local environment must not require a cloud account.

## 5. Core Technologies

### Python

- Python 3.12+
- Pydantic
- FastAPI
- pytest
- asyncio
- mypy or pyright
- ruff

### Event Streaming

- Apache Kafka
- Schema Registry
- Avro as default event serialization
- Protobuf as supported alternative

### Stream Processing

The system must support two alternative engines:

- Apache Flink
- Apache Spark Structured Streaming / PySpark

The rest of the architecture must not be tightly coupled to either engine.

### Data Stores

- PostgreSQL: operational/configuration metadata
- ClickHouse: low-latency analytical telemetry queries
- MinIO/S3: object storage
- Apache Iceberg: analytical lakehouse tables

### CDC

- Debezium

### Frontend

- React
- TypeScript
- SVG
- WebSocket

### Infrastructure

- Docker Compose first
- Kubernetes later
- Helm later

### Observability

- OpenTelemetry
- Prometheus
- Grafana

### CI/CD

- GitHub Actions

## 6. Domain Model

Main domain concepts:

- Race
- Track
- Car
- Driver
- Team
- CarState
- RaceState
- TelemetryEvent
- Lap
- Sector
- PitStop
- TireState
- FuelState
- RaceStrategy
- Incident

Each car must maintain independent state.

Simulation must support deterministic random seeds where practical.

## 7. Telemetry

Typical telemetry fields:

- event_id
- event_type
- schema_version
- event_time
- produced_at
- race_id
- car_id
- driver_id
- speed_kmh
- gear
- rpm
- fuel_kg
- car_weight_kg
- lap
- sector
- lap_distance_m
- track_progress
- race_position
- throttle
- brake
- tire_compound
- tire_age_laps
- pit_status

Track position must primarily be represented by normalized `track_progress` from 0.0 to 1.0.

Do not put frontend pixel coordinates into the core telemetry contract.

## 8. Kafka Rules

Initial topics:

- `race.telemetry.raw`
- `race.telemetry.validated`
- `race.lap.completed`
- `race.pitstop`
- `race.incident`
- `race.state`
- `race.analytics`
- `race.dead-letter`

Use `car_id` as key for car-specific topics where ordering is required.

Use `race_id` where aggregation by race is more appropriate.

Producers and consumers must not depend directly on one another.

## 9. Schema Registry

Every event schema must be versioned.

Default format: Avro.

Protobuf must remain an alternative supported strategy.

Compatibility mode should initially be backward compatible unless a documented ADR changes that decision.

Schema evolution must be tested.

Breaking schema changes require an ADR and migration plan.

## 10. Serialization Abstraction

Business/domain code must not depend directly on Avro or Protobuf libraries.

Create serialization ports/interfaces such as:

```text
EventSerializer
EventDeserializer
SchemaRegistryClient
```

Infrastructure adapters may implement:

```text
AvroEventSerializer
ProtobufEventSerializer
```

## 11. Stream Processing Engine Abstraction

Flink and Spark are execution engines, not domain dependencies.

They must consume compatible input contracts and publish compatible output contracts.

Core transformations must be specified independently from the implementation engine whenever possible.

Examples:

- lap completion;
- moving speed averages;
- fuel consumption metrics;
- pit stop state transitions;
- ranking snapshots;
- race state snapshots;
- event-time windows;
- late-event handling.

Create separate implementation directories, for example:

```text
stream-processing/
    contracts/
    flink/
    spark/
```

Do not try to create a fake universal API that hides all engine-specific capabilities.

Shared behavior belongs in contracts and tests, not in an over-generalized runtime abstraction.

## 12. Event Time

Streaming logic must prefer event time for race calculations.

Define:

- event-time semantics;
- allowed lateness;
- watermark policy;
- replay behavior;
- duplicate handling.

Engine-specific implementations must document differences between Flink and Spark.

## 13. CDC

Use Debezium for changes originating from PostgreSQL when CDC becomes necessary.

Examples:

- race configuration changes;
- driver metadata updates;
- team configuration updates;
- strategy configuration changes.

CDC must not be introduced into the first MVP.

## 14. Iceberg and Object Storage

Use MinIO locally as an S3-compatible object store.

Apache Iceberg will provide analytical tables for raw, refined, and curated data.

Suggested logical layers:

```text
bronze / raw
silver / refined
gold / analytics
```

Prefer names based on semantics in the implementation, for example:

- `telemetry_raw`
- `telemetry_enriched`
- `lap_performance`
- `pitstop_analysis`

Do not make the architecture depend on the terms bronze/silver/gold.

## 15. Storage Responsibilities

PostgreSQL:

- race metadata;
- tracks;
- drivers;
- teams;
- configuration;
- operational state that requires transactions.

ClickHouse:

- recent/historical telemetry analytics;
- fast aggregate dashboard queries;
- time-series-like analytical queries.

Iceberg:

- durable analytical history;
- replay and batch analysis;
- schema evolution;
- partition evolution;
- Spark/Flink interoperability.

Kafka is not the long-term analytical database.

## 16. Python Architecture

Python services should generally follow:

```text
domain/
application/
infrastructure/
interfaces/
```

Domain code must not import Kafka, FastAPI, SQLAlchemy, ClickHouse clients, Avro clients, or infrastructure frameworks.

Prefer dependency injection through constructors.

Prefer composition over inheritance.

Avoid service locators and global mutable state.

## 17. Python Quality Standards

All Python code must use:

- PEP 8;
- type hints;
- clear names;
- small cohesive functions/classes;
- SOLID where it improves maintainability;
- clean architecture boundaries.

Every public module, class, method, and function must contain Sphinx-compatible docstrings.

Example:

```python
def calculate_fuel_consumption(speed_kmh: float, throttle: float) -> float:
    """Calculate fuel consumption for one simulation step.

    :param speed_kmh: Current vehicle speed in kilometers per hour.
    :param throttle: Throttle ratio from 0.0 to 1.0.
    :return: Fuel consumed during the simulation step in kilograms.
    """
```

## 18. Testing

Required testing layers:

- unit tests;
- contract tests;
- schema compatibility tests;
- integration tests;
- end-to-end tests;
- stream engine parity tests where equivalent behavior is expected;
- load tests in later phases.

Important domain calculations requiring unit tests:

- fuel consumption;
- car weight;
- lap completion;
- sector completion;
- pit transitions;
- ranking;
- track progress;
- race position.

## 19. Stream Engine Parity

When both Flink and Spark implementations exist, maintain a shared fixture dataset.

The same input fixture should be processed by both implementations.

For transformations intended to be semantically equivalent, compare normalized outputs.

Differences caused by engine semantics must be documented.

## 20. Configuration

No important configuration should be hardcoded.

Use environment variables and versioned configuration files.

Provide `.env.example`.

Never commit secrets.

## 21. Logging and Observability

Use structured logs.

Useful context fields include:

- race_id;
- car_id;
- event_id;
- topic;
- partition;
- offset.

Do not continuously log complete telemetry payloads except in explicit debug mode.

Add traces and metrics when operationally useful.

## 22. Error Handling

Never silently suppress exceptions.

Consider Kafka at-least-once behavior and event replay.

Design consumers to tolerate duplicates whenever practical.

Use dead-letter handling for malformed or non-processable events after explicit policy decisions.

## 23. Docker

Every deployable service should eventually have a Dockerfile.

Docker Compose is the first orchestration target.

Use health checks where appropriate.

## 24. Kubernetes

Do not introduce Kubernetes before Docker Compose is reliable.

Later Kubernetes resources should include:

- readiness probes;
- liveness probes;
- startup probes where useful;
- resource requests;
- resource limits;
- ConfigMaps;
- Secrets;
- PodDisruptionBudgets where appropriate.

## 25. Documentation

Architecture changes must be documented.

Use ADRs under `docs/adr/` for major decisions.

Keep README commands current and executable.

## 26. Plans

Before significant work, read `.agent/PLANS.md`.

For multi-service features, major infrastructure, migrations, or large refactors, create/update an ExecPlan.

ExecPlans must include:

- objective;
- current state;
- affected architecture;
- implementation steps;
- validation;
- tests;
- risks;
- decisions;
- progress.

## 27. Implementation Sequence

Preferred sequence:

1. simulator domain;
2. telemetry event contract;
3. Kafka;
4. Schema Registry + Avro;
5. simple consumer;
6. FastAPI/WebSocket;
7. frontend track;
8. stream contracts;
9. Flink implementation;
10. Spark Structured Streaming implementation;
11. PostgreSQL;
12. Debezium CDC;
13. ClickHouse;
14. MinIO/S3;
15. Iceberg;
16. observability;
17. Docker Compose stabilization;
18. Kubernetes;
19. CI/CD;
20. load/resilience testing.

## 28. Codex Working Rules

Before changing code:

1. inspect the repository;
2. read `AGENTS.md`;
3. read the active ExecPlan;
4. inspect relevant tests;
5. identify affected components.

After changes:

1. format;
2. lint;
3. type-check;
4. run unit tests;
5. run relevant integration tests;
6. update documentation/plan.

Do not proceed to a later architecture phase merely because it appears in this document.

Implement only the current requested phase.
