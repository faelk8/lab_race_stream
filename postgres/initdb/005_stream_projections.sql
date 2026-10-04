-- Projeções recuperáveis e publicação transacional dos eventos derivados.
CREATE TABLE IF NOT EXISTS stream_sessions (
    race_id text PRIMARY KEY, projection jsonb NOT NULL,
    state jsonb, analytics jsonb, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS stream_receipts (
    topic text NOT NULL, partition_id integer NOT NULL, offset_id bigint NOT NULL,
    PRIMARY KEY (topic, partition_id, offset_id)
);
CREATE TABLE IF NOT EXISTS stream_events (
    event_id text PRIMARY KEY, race_id text NOT NULL, kind text NOT NULL,
    car_id text NOT NULL, logical_key text UNIQUE,
    simulation_time_us bigint NOT NULL, payload jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stream_events_race_car ON stream_events (race_id, car_id, kind, simulation_time_us);
CREATE TABLE IF NOT EXISTS stream_outbox (
    id bigserial PRIMARY KEY, event_id text UNIQUE NOT NULL, payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
