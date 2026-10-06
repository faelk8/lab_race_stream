# ADR 0003: Local Kafka and Schema Registry Topology

> Atualização de 06/10/2026: a topologia local de nó único permanece vigente.
> O tópico único citado na decisão original foi ampliado para dez tópicos com
> nomes curtos pela [ADR 0013](0013-nomes-curtos-topicos-kafka.md).

## Status

Accepted

## Context

The MVP must run reproducibly on a developer workstation with Docker Compose and without a cloud account or multi-node cluster.

## Decision

- Run a single Confluent Kafka broker in KRaft mode as both broker and controller.
- Expose `localhost:9092` to host processes and `kafka:29092` to Compose services.
- Run a single Schema Registry at `localhost:8081`, using the internal Kafka listener.
- Initialize `race.telemetry.raw` as a six-partition, single-replica topic before starting the applications.
- Gate producer and consumer startup on topic initialization and Schema Registry health.
- Persist Kafka state in the named `kafka-data` volume.
- Keep the topology explicitly local-development-only; it is not a production availability or security configuration.

## Consequences

- `docker compose up --build` starts the complete MVP without manual topic creation.
- A single broker has no fault tolerance; the volume preserves local data across normal container recreation.
- The internal and external listeners allow the same broker to serve both local tools and containers.
- Removing persisted local data requires the explicit `docker compose down -v` operation.

## Validation

- `docker compose config --quiet` validates the Compose model.
- The integration smoke test passed with Kafka and Schema Registry running.
- The Schema Registry exposed the `race.telemetry.raw-value` subject after producer startup.
