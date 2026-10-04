-- Identidade dos pilotos; preservar metadados já definidos pelo operador.
ALTER TABLE cars ADD COLUMN IF NOT EXISTS driver_name TEXT NOT NULL DEFAULT '';
ALTER TABLE cars ADD COLUMN IF NOT EXISTS driver_country_code TEXT NOT NULL DEFAULT '';
ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_driver_country_code_check;
ALTER TABLE cars ADD CONSTRAINT cars_driver_country_code_check
 CHECK (driver_country_code ~ '^([A-Z]{2})?$');
UPDATE cars AS c SET
 driver_name = CASE WHEN c.driver_name = '' THEN p.name ELSE c.driver_name END,
 driver_country_code = CASE WHEN c.driver_country_code = '' THEN p.country ELSE c.driver_country_code END
FROM (VALUES
('DRV-01', 'Rafael Almeida', 'BR'),
('DRV-02', 'Lucas Ribeiro', 'BR'),
('DRV-03', 'Matías Silva', 'AR'),
('DRV-04', 'Diego Torres', 'AR'),
('DRV-05', 'João Costa', 'PT'),
('DRV-06', 'Miguel Santos', 'PT'),
('DRV-07', 'Oliver Bennett', 'GB'),
('DRV-08', 'William Parker', 'GB'),
('DRV-09', 'Matteo Rossi', 'IT'),
('DRV-10', 'Luca Bianchi', 'IT'),
('DRV-11', 'Alejandro García', 'ES'),
('DRV-12', 'Carlos Medina', 'ES'),
('DRV-13', 'Pierre Martin', 'FR'),
('DRV-14', 'Julien Moreau', 'FR'),
('DRV-15', 'Lukas Weber', 'DE'),
('DRV-16', 'Maximilian Keller', 'DE'),
('DRV-17', 'Kenji Sato', 'JP'),
('DRV-18', 'Haruto Tanaka', 'JP'),
('DRV-19', 'Liam Campbell', 'CA'),
('DRV-20', 'Noah Wilson', 'CA')
) AS p(driver_id, name, country)
WHERE c.driver_id = p.driver_id
 AND (c.driver_name = '' OR c.driver_country_code = '');
