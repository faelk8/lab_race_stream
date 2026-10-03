# ADR 0001: Clean Architecture and Dependency Inversion

## Status

Accepted

## Context

The MVP needs a simulator, an application use case, and Kafka/Avro adapters. The domain must remain testable without Kafka, Schema Registry, or Docker, and future adapters must not force changes to race rules.

## Decision

Use four Python boundaries under `src/racestream/`:

- `domain/` owns `CarState`, `TelemetryEvent`, and `RaceSimulator`; it imports only the Python standard library.
- `application/` owns telemetry validation, `SimulationService`, and the `EventPublisher` protocol.
- `infrastructure/` implements the Kafka producer/consumer and Schema Registry integration.
- `interfaces/` is the composition root: it reads environment configuration, constructs concrete adapters, injects them into application use cases, and runs the process loops.

The application depends on the `EventPublisher` protocol rather than `AvroKafkaPublisher`. Unit tests inject an in-memory publisher. Pydantic is used at the application boundary; Kafka and Avro libraries remain infrastructure dependencies.

## Consequences

- Simulation tests run without external services.
- A new publisher adapter can implement the existing protocol without changing domain or application logic.
- The process entry points own construction and lifecycle of infrastructure resources.
- The protocol is intentionally narrow and does not attempt to abstract Kafka consumer semantics.

## Validation

- `tests/unit/test_simulation_service.py` verifies event publication through an in-memory implementation.
- `tests/unit/test_simulator.py` verifies deterministic domain behavior without infrastructure.