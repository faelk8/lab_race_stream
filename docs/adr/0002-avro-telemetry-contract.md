# ADR 0002: Versioned Avro Telemetry Contract

## Status

Accepted

## Context

The first vertical slice needs a stable, inspectable event contract that can be validated before downstream stream-processing engines are selected.

## Decision

- Use Avro as the MVP serialization format and Confluent Schema Registry as the schema authority.
- Store the versioned schema in `schemas/telemetry-v1.avsc` and identify its event type as `race.telemetry.v1`.
- Publish to `race.telemetry.raw`, using `car_id` as the key to preserve per-car partition ordering.
- Register the schema under the topic-value subject and configure backward compatibility in the local Registry.
- Include event identifiers, event and production times, race/car/driver identifiers, vehicle state, normalized track progress, ranking, tires, and pit status.
- Keep frontend coordinates out of the event contract. Represent track position as `track_progress` in `[0.0, 1.0)`.
- Validate the event with Pydantic at the application boundary and with Avro during serialization.

## Consequences

- Producers and consumers share an explicit, versioned contract.
- Adding or changing fields requires an intentional schema evolution and compatibility test.
- Protobuf remains a possible future strategy but is not mixed into this topic or MVP.
- Event timestamps are ISO-8601 strings in v1 for straightforward Python and Avro interoperability.

## Validation

- Contract tests check required schema fields and reject invalid track progress and unexpected payload fields.
- The Kafka round-trip integration test confirms registration, serialization, consumption, and identifier preservation.