-- Atualize instalações existentes sem sobrescrever uma personalização manual.
UPDATE cars
SET driver_name = 'Rafael Batista', updated_at = now()
WHERE driver_id = 'DRV-01'
  AND driver_name = 'Rafael Almeida';
