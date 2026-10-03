# ADR 0006: Track-Aware Driving and Minimum Car Spacing

## Status

Accepted

## Context

The simulator previously varied speed independently of track position. Cars could therefore enter corners at straight-line speed, keep the same gear, or overlap visually when lap estimates were close.

## Decision

- Define normalized Interlagos corner zones in the simulator domain.
- Begin braking when remaining distance is within the speed-based braking distance plus a buffer.
- Target a lower corner speed; derive gear from the resulting physical speed so downshifts follow deceleration.
- Hold throttle through braking/corner phases; resume acceleration on exit and cap straight-line speed at the car's configured maximum.
- Emit `driving_phase` (`straight`, `braking`, or `corner`) in telemetry v2 and use it to communicate state in the UI.
- Start cars with staggered positions and enforce at least 60 m between adjacent progress values after each simulation tick.
- Keep race-clock progress and physical speed separate: the compressed two-minute race does not multiply displayed km/h.

## Consequences

- Configured top speed controls the straight and each car shifts in response to its own speed profile.
- The 60 m gap is an educational simulation constraint selected to keep the enlarged selected marker separate from neighboring cars across viewport sizes; it is not a real-world safety distance.
- Track corner zones and coefficients are deterministic approximations, not a tire/vehicle dynamics model.
- Telemetry v2 remains readable for older registered records because the new schema field has the default `straight`.

## Validation

- Unit tests cover braking and downshift before a corner, acceleration after a corner, top-speed cap, and minimum pairwise spacing over repeated ticks.
- The v2 contract and schema tests validate the `driving_phase` field and default.