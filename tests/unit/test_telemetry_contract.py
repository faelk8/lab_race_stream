"""Tests for the version-one telemetry boundary contract."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from racestream.application.telemetry import TelemetryPayload, telemetry_to_payload
from racestream.domain.simulator import RaceSimulator


def test_domain_event_maps_to_valid_telemetry_payload() -> None:
    """Domain telemetry maps to the complete version-two contract."""
    event = RaceSimulator(seed=11, car_count=1).tick()[0]

    payload = telemetry_to_payload(event)
    validated = TelemetryPayload.model_validate(payload)

    assert payload["event_type"] == "race.telemetry.v2"
    assert payload["schema_version"] == 2
    assert payload["car_id"] == "CAR-01"
    assert validated.track_progress >= 0.0
    assert validated.target_laps == 60


def test_contract_rejects_progress_outside_normalized_track() -> None:
    """Track progress must remain in the half-open interval [0, 1)."""
    event = RaceSimulator(seed=11, car_count=1).tick()[0]

    with pytest.raises(ValidationError):
        telemetry_to_payload(replace(event, track_progress=1.0))


def test_avro_schema_contains_required_telemetry_fields() -> None:
    """The versioned Avro schema exposes the required race and car fields."""
    schema_path = Path("schemas/telemetry-v2.avsc")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    field_names = {field["name"] for field in schema["fields"]}

    assert schema["name"] == "TelemetryEvent"
    assert {
        "event_id",
        "event_type",
        "schema_version",
        "event_time",
        "produced_at",
        "race_id",
        "car_id",
        "driver_id",
        "fuel_kg",
        "car_weight_kg",
        "track_progress",
        "race_position",
        "tire_compound",
        "pit_status",
        "driving_phase",
        "current_lap_time_ms",
        "last_lap_time_ms",
        "best_lap_time_ms",
        "elapsed_race_seconds",
        "target_laps",
        "race_status",
    } <= field_names
    assert schema["fields"][-6]["default"] == 0
    assert schema["fields"][-5]["default"] is None


def test_contract_forbids_unknown_fields() -> None:
    """Unexpected fields are rejected instead of silently leaking downstream."""
    event = RaceSimulator(seed=11, car_count=1).tick()[0]
    payload = telemetry_to_payload(event)

    with pytest.raises(ValidationError):
        TelemetryPayload.model_validate({**payload, "frontend_x": 12})