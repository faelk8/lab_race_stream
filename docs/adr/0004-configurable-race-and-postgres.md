# ADR 0004: Configurable 60-Lap Race and PostgreSQL

## Status

Accepted

## Context

The dashboard requires independent car performance, lap timing, editable setup, and durable race results. The requested 60-lap event must fit into two minutes of local wall-clock time without reporting impossible physical speeds.

## Decision

- Use Interlagos at 4,309 m, a 90,000 ms reference lap, a 120-second race clock, and a 60-lap reference distance.
- Advance race progress with a separate compressed race clock. Keep physical speed telemetry capped by each car's configured top speed.
- Calculate a deterministic lap-time estimate from dry car mass, driver mass, top speed, tire compound, and tire age.
- Start with tire deltas of soft `-250 ms/lap`, medium `0 ms/lap`, and hard `+300 ms/lap`; add `15 ms` per lap of tire age.
- Persist car configuration, race lifecycle, and per-car final result/configuration snapshots in PostgreSQL. Do not store high-frequency telemetry samples there; Kafka remains the event stream.
- Apply updated setup to the next race. An active race uses the setup snapshot loaded at its start.
- Store lap estimates, last/best lap times, elapsed race time, target laps, and race status in telemetry v2.

## Consequences

- The baseline setup represents 60 laps in exactly 120 seconds; other setups accumulate deterministic relative time differences.
- Displayed vehicle speed remains within the configured top speed even though track progress is accelerated.
- PostgreSQL migrations create `cars`, `races`, and `race_results`; volume data survives normal `docker compose down`.
- Tire and mass coefficients are simulation parameters, not claims of real-world vehicle performance; adjust them through tests and documented decisions.

## Validation

- Unit tests verify baseline duration, tire deltas, car profile variation, and deterministic progression.
- Compose startup seeded 20 varied cars; a completed race persisted 20 results.