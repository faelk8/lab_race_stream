-- Coordenação de início e parada pelo painel; manter históricos existentes.
ALTER TABLE races ADD COLUMN IF NOT EXISTS controlled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE races DROP CONSTRAINT IF EXISTS races_status_check;
ALTER TABLE races ADD CONSTRAINT races_status_check
 CHECK (status IN ('queued', 'running', 'paused', 'stopping', 'stopped', 'finished', 'failed'));
-- Corridas do produtor antigo não podem continuar após trocar para controle manual.
UPDATE races SET status = 'stopped', finished_at = now()
 WHERE NOT controlled AND status = 'running';
CREATE UNIQUE INDEX IF NOT EXISTS races_one_controlled_active
 ON races ((1)) WHERE controlled AND status IN ('queued', 'running', 'paused', 'stopping');
