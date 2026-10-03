export type TireCompound = "soft" | "medium" | "hard";

export interface CarConfiguration {
    car_id: string;
    driver_id: string;
    car_weight_kg: number;
    driver_weight_kg: number;
    top_speed_kmh: number;
    tire_compound: TireCompound;
}

export interface RaceTelemetry {
    event_id: string;
    event_type: "race.telemetry.v2";
    schema_version: 2;
    race_id: string;
    car_id: string;
    driver_id: string;
    speed_kmh: number;
    gear: number;
    fuel_kg: number;
    car_weight_kg: number;
    lap: number;
    sector: number;
    track_progress: number;
    race_position: number;
    tire_compound: TireCompound;
    driving_phase: "straight" | "braking" | "corner";
    current_lap_time_ms: number;
    last_lap_time_ms: number | null;
    best_lap_time_ms: number | null;
    elapsed_race_seconds: number;
    target_laps: number;
    race_status: "running" | "finished";
}

export interface RaceSnapshot {
    race_id: string;
    circuit_name: string;
    duration_seconds: number;
    target_laps: number;
    status: "running" | "finished";
    started_at: string;
    finished_at: string | null;
}