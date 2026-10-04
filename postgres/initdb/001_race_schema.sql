CREATE TABLE IF NOT EXISTS cars (
    car_id TEXT PRIMARY KEY,
    driver_id TEXT NOT NULL,
    car_weight_kg DOUBLE PRECISION NOT NULL CHECK (car_weight_kg BETWEEN 450 AND 1000),
    driver_weight_kg DOUBLE PRECISION NOT NULL CHECK (driver_weight_kg BETWEEN 45 AND 150),
    top_speed_kmh DOUBLE PRECISION NOT NULL CHECK (top_speed_kmh BETWEEN 250 AND 380),
    tire_compound TEXT NOT NULL CHECK (tire_compound IN ('soft', 'medium', 'hard')),
    team_id TEXT NOT NULL DEFAULT 'TEAM-A-01',
    team_category TEXT NOT NULL DEFAULT 'A' CHECK (team_category IN ('A', 'B', 'C')),
    driver_height_m DOUBLE PRECISION NOT NULL DEFAULT 1.75 CHECK (driver_height_m BETWEEN 1.60 AND 1.90),
    strategy TEXT NOT NULL DEFAULT 'A' CHECK (strategy IN ('A', 'B', 'C')),
    pit_service_seconds DOUBLE PRECISION NOT NULL DEFAULT 3 CHECK (pit_service_seconds BETWEEN 3 AND 6),
    car_length_m DOUBLE PRECISION NOT NULL DEFAULT 3 CHECK (car_length_m = 3),
    driver_name TEXT NOT NULL DEFAULT '',
    driver_country_code TEXT NOT NULL DEFAULT '' CHECK (driver_country_code ~ '^([A-Z]{2})?$'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS races (
    race_id TEXT PRIMARY KEY,
    circuit_name TEXT NOT NULL,
    track_length_m DOUBLE PRECISION NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL,
    target_laps INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'stopping', 'stopped', 'finished', 'failed')),
    controlled BOOLEAN NOT NULL DEFAULT false,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS race_results (
    race_id TEXT NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,
    car_id TEXT NOT NULL REFERENCES cars(car_id),
    race_position INTEGER NOT NULL,
    laps_completed INTEGER NOT NULL,
    last_lap_time_ms INTEGER,
    best_lap_time_ms INTEGER,
    car_weight_kg DOUBLE PRECISION NOT NULL,
    driver_weight_kg DOUBLE PRECISION NOT NULL,
    top_speed_kmh DOUBLE PRECISION NOT NULL,
    tire_compound TEXT NOT NULL,
    PRIMARY KEY (race_id, car_id),
    UNIQUE (race_id, race_position)
);