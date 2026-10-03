CREATE TABLE IF NOT EXISTS cars (
    car_id TEXT PRIMARY KEY,
    driver_id TEXT NOT NULL,
    car_weight_kg DOUBLE PRECISION NOT NULL CHECK (car_weight_kg BETWEEN 700 AND 1000),
    driver_weight_kg DOUBLE PRECISION NOT NULL CHECK (driver_weight_kg BETWEEN 45 AND 150),
    top_speed_kmh DOUBLE PRECISION NOT NULL CHECK (top_speed_kmh BETWEEN 250 AND 380),
    tire_compound TEXT NOT NULL CHECK (tire_compound IN ('soft', 'medium', 'hard')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS races (
    race_id TEXT PRIMARY KEY,
    circuit_name TEXT NOT NULL,
    track_length_m DOUBLE PRECISION NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL,
    target_laps INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'finished')),
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