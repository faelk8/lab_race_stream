-- Permite pausar e retomar uma corrida controlada sem encerrá-la.
ALTER TABLE races DROP CONSTRAINT IF EXISTS races_status_check;
ALTER TABLE races ADD CONSTRAINT races_status_check
 CHECK (status IN ('queued', 'running', 'paused', 'stopping', 'stopped', 'finished', 'failed'));
DROP INDEX IF EXISTS races_one_controlled_active;
CREATE UNIQUE INDEX races_one_controlled_active
 ON races ((1)) WHERE controlled AND status IN ('queued', 'running', 'paused', 'stopping');
