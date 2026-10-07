export type TireCompound = "soft" | "medium" | "hard" | "wet";

export interface TrackDefinition {
    map_start_offset: number;
    length_m: number;
    sector_ends: number[];
    checkpoints: number[];
}

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
    event_type: "race.telemetry.v2" | "race.telemetry.v3" | "race.telemetry.v4";
    schema_version: 2 | 3 | 4;
    kind?: string;
    snapshot_id?: number;
    distance_m?: number;
    driver_name?: string;
    driver_country_code?: string;
    team_id?: string;
    car_status?: string;
    g_longitudinal?: number | null;
    g_lateral?: number | null;
    g_horizontal?: number | null;
    g_peak?: number;
    worst_lap_time_ms?: number | null;
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
    track_status?: "green" | "safety_car";
}

export interface RaceSnapshot {
    race_id: string;
    circuit_name: string;
    duration_seconds: number;
    target_laps: number;
    status: "queued" | "running" | "stopping" | "stopped" | "finished" | "failed";
    started_at: string;
    finished_at: string | null;
    rain_enabled: boolean;
    rain_start_lap: number;
    rain_intensity: number;
    incidents: RaceIncident[];
}

export interface RaceIncident {
    incident_type: "tire_puncture" | "collision";
    lap: number;
    car_id: string;
    second_car_id: string;
}

export interface RaceStartConfiguration {
    rain_enabled: boolean;
    rain_start_lap: number;
    rain_intensity: number;
    incidents: RaceIncident[];
}
export interface Split {
    checkpoint_id: string;
    lap: number;
    segment_time_ms: number;
    lap_elapsed_ms: number;
    best_personal_ms: number | null;
    best_team_ms: number | null;
    best_race_ms: number | null;
    delta_ms: number | null;
    color: string;
    valid: boolean;
}

export interface CarAnalytics {
    car_id: string;
    driver_id: string;
    team_id: string;
    last_lap_time_ms: number | null;
    best_lap_time_ms: number | null;
    worst_lap_time_ms: number | null;
    theoretical_lap_ms: number | null;
    pace_ms: number | null;
    lap_count: number;
    sector_best_ms: (number | null)[];
    splits: Split[];
    gap_to_leader_ms: number | null;
    interval_to_ahead_ms: number | null;
    gap_reference: string;
    gap_reference_age_ms: number | null;
    laps_behind: number;
}

export interface RaceStateEvent {
    kind: "state";
    race_id: string;
    state_sequence: number;
    produced_at: string;
    snapshot_id: number;
    complete: boolean;
    cars: { telemetry: RaceTelemetry; stale: boolean }[];
}

export interface AnalyticsEvent {
    kind: "analytics";
    race_id: string;
    revision: number;
    snapshot_id: number;
    cars: CarAnalytics[];
}
