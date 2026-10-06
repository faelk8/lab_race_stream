-- Configurações reproduzíveis de clima e incidentes por corrida.
ALTER TABLE races
    ADD COLUMN IF NOT EXISTS rain_enabled BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS rain_start_lap INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS rain_intensity DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    ADD COLUMN IF NOT EXISTS incidents JSONB NOT NULL DEFAULT '[]'::jsonb;
