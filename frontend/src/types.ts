export type TireCompound = "soft" | "medium" | "hard";

export interface CarConfiguration {
    car_id: string;
    driver_id: string;
    driver_name: string;
    driver_country_code: string;
    car_weight_kg: number;
    driver_weight_kg: number;
    top_speed_kmh: number;
    tire_compound: TireCompound;
    team_id: string;
    team_category: "A" | "B" | "C";
    driver_height_m: number;
    strategy: "A" | "B" | "C";
    pit_service_seconds: number;
    car_length_m: number;
}

export interface RaceTelemetry {
    event_time: string;
    event_id: string;
    event_type: "race.telemetry.v2" | "race.telemetry.v3";
    schema_version: 2 | 3;
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
    pit_status: "on_track" | "pit_lane" | "in_pit" | "out_of_fuel" | "tire_burst";
    tire_pressure_psi?: number;
    pit_stops?: number;
    overtaking_lane?: number;
    driving_phase: "straight" | "braking" | "corner";
    current_lap_time_ms: number;
    last_lap_time_ms: number | null;
    best_lap_time_ms: number | null;
    elapsed_race_seconds: number;
    target_laps: number;
    race_status: "running" | "finished" | "stopped";
}

export interface RaceSnapshot {
    race_id: string;
    circuit_name: string;
    duration_seconds: number;
    target_laps: number;
    status: "queued" | "running" | "stopping" | "stopped" | "finished" | "failed";
    started_at: string;
    finished_at: string | null;
}