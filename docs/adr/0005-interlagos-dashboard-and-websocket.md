# ADR 0005: Interlagos Dashboard and WebSocket Fanout

## Status

Accepted

## Context

The race needs a browser interface with current car positions and configuration controls. Browser consumers must not couple to Kafka client details or request historical telemetry at high frequency.

## Decision

- Use FastAPI for REST car setup/latest-race reads and a race-scoped WebSocket for current telemetry.
- Use one background Kafka consumer per API process and fan events into bounded per-client queues; discard stale queued snapshots rather than accumulate latency.
- Use React + TypeScript + Vite for a live track, 20-car leaderboard, lap telemetry, and car-setup editor.
- Render track position from normalized `track_progress`; do not send frontend pixel coordinates into the event contract.
- Use the Interlagos SVG by Ch1902 from Wikimedia Commons as the track visual reference. The file is public domain; source and author are recorded in `frontend/public/ATTRIBUTION.md`.
- Keep the dashboard and API on local Compose ports 5173 and 8000. Keep PostgreSQL on the private Compose network to avoid conflicting with host databases.

## Consequences

- The frontend does not depend on Kafka or PostgreSQL libraries.
- REST setup changes are durable and become active at the next race start.
- Slow WebSocket clients receive recent state instead of an unbounded event backlog.
- Track artwork is a visualization asset; domain progress remains normalized and engine-independent.

## Validation

- REST tests cover setup save/validation through injected repository ports.
- Browser verification observed live telemetry and leaderboard updates, exercised setup save/restore, and measured no horizontal overflow at 375 px.
- The Vite production build passed.