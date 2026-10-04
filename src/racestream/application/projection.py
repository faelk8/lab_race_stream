"""Projeções determinísticas de voltas, parciais e quadros da corrida."""

from copy import deepcopy
from statistics import median
from typing import Any


def initial_projection() -> dict[str, Any]:
    """Crie o estado serializável e limitado de uma sessão."""
    return {
        "cars": {},
        "frames": {},
        "last_snapshot": -1,
        "state_sequence": 0,
        "analysis_sequence": 0,
        "participants": [],
        "best": {},
        "best_team": {},
        "best_race": {},
        "splits": {},
        "sectors": {},
        "sector_best": {},
        "laps": {},
        "clean": {},
        "lap_end": {},
        "reference": {},
        "control": None,
    }


def derived(
    event: dict[str, Any], kind: str, suffix: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Construa um evento derivado com identidade reprodutível."""
    keys = (
        "race_id",
        "event_time",
        "produced_at",
        "simulation_time_us",
        "source_sequence",
        "track_version",
        "rules_version",
        "car_id",
    )
    return {
        **{k: event[k] for k in keys},
        "kind": kind,
        "schema_version": 1,
        "event_id": f"{event['event_id']}:{suffix}",
        **data,
    }


def apply_event(state: dict[str, Any], event: dict[str, Any]) -> list[dict[str, Any]]:
    """Atualize uma projeção já deduplicada e retorne seus derivados."""
    kind, car = event["kind"], event["car_id"]
    output: list[dict[str, Any]] = []
    if kind == "control":
        if event["participants"]:
            state["participants"] = event["participants"]
        state["control"] = event
    elif kind == "timing":
        lap, point = event["lap"], event["checkpoint_id"]
        key = f"{car}:{point}"
        team_key = f"{event['team_id']}:{point}"
        old = state["best"].get(key)
        best_race = state["best_race"].get(point)
        current = event["segment_time_ms"]
        valid = event["valid"] and not event["pit_lap"]
        color = "gray"
        if valid:
            color = (
                "purple"
                if best_race is None or current <= best_race
                else "green"
                if old is None or current < old
                else "yellow"
            )
            state["best"][key] = min(old if old is not None else current, current)
            state["best_team"][team_key] = min(
                state["best_team"].get(team_key, current), current
            )
            state["best_race"][point] = min(
                best_race if best_race is not None else current, current
            )
        split = {
            "checkpoint_id": point,
            "lap": lap,
            "segment_time_ms": current,
            "lap_elapsed_ms": event["lap_elapsed_ms"],
            "best_personal_ms": state["best"].get(key),
            "best_team_ms": state["best_team"].get(team_key),
            "best_race_ms": state["best_race"].get(point),
            "delta_ms": current - old if old is not None else None,
            "color": color,
            "valid": valid,
        }
        splits = state["splits"].setdefault(car, {})
        previous = splits.get(point)
        if previous is None or lap >= previous["lap"]:
            splits[point] = split
        sector_key = f"{car}:{lap}"
        if event["sector"]:
            sectors = state["sectors"].setdefault(sector_key, {})
            sectors[str(event["sector"])] = event["sector_time_ms"]
            if valid:
                bests = state["sector_best"].setdefault(car, {})
                k = str(event["sector"])
                bests[k] = min(
                    bests.get(k, event["sector_time_ms"]), event["sector_time_ms"]
                )
        # Referência por mesma volta/linha, limitada à janela de voltas recentes.
        reference_key = f"{lap}:{point}"
        state["latest_timing_lap"] = max(state.get("latest_timing_lap", 0), lap)
        state["reference"].setdefault(reference_key, {})[car] = event[
            "simulation_time_us"
        ]
        for reference in list(state["reference"]):
            if int(reference.split(":")[0]) < state["latest_timing_lap"] - 2:
                del state["reference"][reference]
        if point == "SF":
            state["lap_end"][sector_key] = event
        if (
            sector_key in state["lap_end"]
            and len(state["sectors"].get(sector_key, {})) == 3
        ):
            event = state["lap_end"].pop(sector_key)
            sectors = state["sectors"].get(sector_key, {})
            valid_lap = len(sectors) == 3
            completed = derived(
                event,
                "lap",
                "lap",
                {
                    "driver_id": event["driver_id"],
                    "team_id": event["team_id"],
                    "lap": lap,
                    "lap_time_ms": event["lap_elapsed_ms"],
                    "sectors_ms": [sectors.get(str(i), 0) for i in (1, 2, 3)],
                    "pit_lap": event["pit_lap"],
                    "valid": valid_lap,
                },
            )
            output.append(completed)
            info = state["laps"].setdefault(
                car,
                {"last": None, "best": None, "worst": None, "count": 0, "number": 0},
            )
            if valid_lap:
                value = completed["lap_time_ms"]
                if lap > info["number"]:
                    info["last"], info["number"] = value, lap
                info["best"] = min(info["best"] or value, value)
                info["worst"] = max(info["worst"] or value, value)
                info["count"] += 1
                if not event["pit_lap"] and lap > 1:
                    clean = state["clean"].setdefault(car, {})
                    clean[str(lap)] = value
                    for number in sorted(clean, key=int)[:-5]:
                        del clean[number]
            state["sectors"].pop(sector_key, None)
            if state["cars"]:
                output.append(analytics_event(state, event))
    elif kind == "telemetry":
        output.append({**event, "kind": "validated"})
        snapshot = event["snapshot_id"]
        if snapshot > state["last_snapshot"]:
            state["frames"].setdefault(str(snapshot), {})[car] = event
            frame = state["frames"][str(snapshot)]
            expected = {p["car_id"] for p in state["participants"]}
            if expected and set(frame) == expected:
                positions = {e["race_position"] for e in frame.values()}
                if positions != set(range(1, len(expected) + 1)):
                    raise ValueError("Quadro com classificação duplicada ou incompleta")
                output.extend(emit_frame(state, event, frame, True))
            old_keys = [k for k in state["frames"] if int(k) <= snapshot - 3]
            if old_keys:
                pending = state["frames"][max(old_keys, key=int)]
                output.extend(
                    emit_frame(state, next(iter(pending.values())), pending, False)
                )
            # Limite de memória para quadros incompletos; a camada de persistência
            # emite um quadro parcial ao vencer o prazo de entrega.
            for key in sorted(state["frames"], key=int)[:-4]:
                del state["frames"][key]
    return output


def emit_frame(
    state: dict[str, Any], event: dict[str, Any], frame: dict[str, Any], complete: bool
) -> list[dict[str, Any]]:
    """Consolide um quadro sem inventar posições para eventos ausentes."""
    if complete and {e["race_position"] for e in frame.values()} != set(
        range(1, len(frame) + 1)
    ):
        raise ValueError("Quadro com classificação duplicada ou incompleta")
    state["state_sequence"] += 1
    snapshot = event["snapshot_id"]
    state["last_snapshot"] = snapshot
    old = deepcopy(state["cars"])
    state["cars"].update(frame)
    cars = []
    for car, telemetry in state["cars"].items():
        item = deepcopy(telemetry)
        if not complete and car in old:
            # Enquanto o quadro não estiver completo, a classificação anterior
            # permanece autoritativa; os valores individuais continuam atualizando.
            item["race_position"] = old[car]["race_position"]
            state["cars"][car] = item
        cars.append({"telemetry": item, "stale": car not in frame})
    cars.sort(key=lambda item: item["telemetry"]["race_position"])
    for key in list(state["frames"]):
        if int(key) <= snapshot:
            del state["frames"][key]
    result = derived(
        event,
        "state",
        f"state:{state['state_sequence']}",
        {
            "car_id": "",
            "state_sequence": state["state_sequence"],
            "snapshot_id": snapshot,
            "complete": complete,
            "cars": cars,
        },
    )
    return [result, analytics_event(state, event)]


def analytics_event(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Calcule resumos por carro e gaps com uma única referência comum."""
    state["analysis_sequence"] = state.get("analysis_sequence", 0) + 1
    cars = sorted(state["cars"].values(), key=lambda e: e["race_position"])
    ids = [e["car_id"] for e in cars]
    references = [
        (key, values)
        for key, values in state["reference"].items()
        if ids
        and set(ids) <= set(values)
        and [values[c] for c in ids] == sorted(values[c] for c in ids)
    ]
    reference, times = max(
        references, key=lambda item: min(item[1].values()), default=("", {})
    )
    summaries = []
    for index, telemetry in enumerate(cars):
        car = telemetry["car_id"]
        laps = state["laps"].get(car, {})
        bests = state["sector_best"].get(car, {})
        clean = list(state["clean"].get(car, {}).values())
        splits = deepcopy(list(state["splits"].get(car, {}).values()))
        for split in splits:
            point = split["checkpoint_id"]
            split["best_personal_ms"] = state["best"].get(f"{car}:{point}")
            split["best_team_ms"] = state["best_team"].get(
                f"{telemetry['team_id']}:{point}"
            )
            split["best_race_ms"] = state["best_race"].get(point)
            personal = split["best_personal_ms"]
            best_race = split["best_race_ms"]
            split["delta_ms"] = (
                split["segment_time_ms"] - personal if personal is not None else None
            )
            split["color"] = (
                "gray"
                if not split["valid"]
                else "purple"
                if best_race is not None and split["segment_time_ms"] <= best_race
                else "green"
                if personal is not None and split["segment_time_ms"] <= personal
                else "yellow"
            )
        summaries.append(
            {
                "car_id": car,
                "driver_id": telemetry["driver_id"],
                "team_id": telemetry["team_id"],
                "last_lap_time_ms": laps.get("last"),
                "best_lap_time_ms": laps.get("best"),
                "worst_lap_time_ms": laps.get("worst"),
                "lap_count": laps.get("count", 0),
                "theoretical_lap_ms": sum(bests.values()) if len(bests) == 3 else None,
                "pace_ms": round(median(clean)) if clean else None,
                "sector_best_ms": [bests.get(str(i)) for i in (1, 2, 3)],
                "splits": sorted(
                    splits,
                    key=lambda s: s["checkpoint_id"],
                ),
                "gap_to_leader_ms": round((times[car] - times[ids[0]]) / 1000)
                if times
                else None,
                "interval_to_ahead_ms": round(
                    (times[car] - times[ids[index - 1]]) / 1000
                )
                if times and index
                else None,
                "gap_reference": reference,
                "gap_reference_age_ms": max(
                    0,
                    round(
                        (
                            max(t["simulation_time_us"] for t in cars)
                            - max(times.values())
                        )
                        / 1000
                    ),
                )
                if times
                else None,
                "laps_behind": max(
                    0, cars[0]["laps_completed"] - telemetry["laps_completed"]
                ),
            }
        )
    return derived(
        event,
        "analytics",
        f"analytics:{state['analysis_sequence']}",
        {
            "car_id": "",
            "revision": state["analysis_sequence"],
            "snapshot_id": state["last_snapshot"],
            "cars": summaries,
        },
    )
