ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_car_weight_kg_check;
ALTER TABLE cars ADD CONSTRAINT cars_car_weight_kg_check CHECK (car_weight_kg BETWEEN 450 AND 1000);
ALTER TABLE cars ADD COLUMN IF NOT EXISTS team_id TEXT NOT NULL DEFAULT 'TEAM-A-01';
ALTER TABLE cars ADD COLUMN IF NOT EXISTS team_category TEXT NOT NULL DEFAULT 'A';
ALTER TABLE cars ADD COLUMN IF NOT EXISTS driver_height_m DOUBLE PRECISION NOT NULL DEFAULT 1.75;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS strategy TEXT NOT NULL DEFAULT 'A';
ALTER TABLE cars ADD COLUMN IF NOT EXISTS pit_service_seconds DOUBLE PRECISION NOT NULL DEFAULT 3;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS car_length_m DOUBLE PRECISION NOT NULL DEFAULT 3;
ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_team_category_check;
ALTER TABLE cars ADD CONSTRAINT cars_team_category_check CHECK (team_category IN ('A', 'B', 'C'));
ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_strategy_check;
ALTER TABLE cars ADD CONSTRAINT cars_strategy_check CHECK (strategy IN ('A', 'B', 'C'));
ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_driver_height_m_check;
ALTER TABLE cars ADD CONSTRAINT cars_driver_height_m_check CHECK (driver_height_m BETWEEN 1.60 AND 1.90);
ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_pit_service_seconds_check;
ALTER TABLE cars ADD CONSTRAINT cars_pit_service_seconds_check CHECK (pit_service_seconds BETWEEN 3 AND 6);
ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_car_length_m_check;
ALTER TABLE cars ADD CONSTRAINT cars_car_length_m_check CHECK (car_length_m = 3);

-- Substitua apenas as configurações padrão originais; preserve as edições do operador.
UPDATE cars AS c SET
 car_weight_kg = p.new_weight, driver_weight_kg = p.new_driver_weight,
 top_speed_kmh = p.new_speed, team_id = p.team_id,
 team_category = p.category, driver_height_m = p.height,
 strategy = p.strategy, pit_service_seconds = p.service, updated_at = now()
FROM (VALUES
('CAR-01', 840, 85, 334, 'soft', 500.0, 56.32, 290.0, 'TEAM-A-01', 'A', 1.6, 'A', 3.0),
('CAR-02', 832, 75, 327, 'medium', 500.0, 61.36, 303.0, 'TEAM-A-01', 'A', 1.67, 'B', 3.0),
('CAR-03', 824, 65, 340, 'hard', 500.0, 66.61, 316.0, 'TEAM-A-02', 'A', 1.74, 'C', 4.0),
('CAR-04', 816, 87, 333, 'soft', 500.0, 72.07, 298.0, 'TEAM-A-02', 'A', 1.81, 'A', 4.0),
('CAR-05', 844, 77, 326, 'medium', 500.0, 77.76, 311.0, 'TEAM-A-03', 'A', 1.88, 'B', 5.0),
('CAR-06', 836, 67, 339, 'hard', 500.0, 59.17, 293.0, 'TEAM-A-03', 'A', 1.64, 'C', 5.0),
('CAR-07', 828, 89, 332, 'soft', 500.0, 64.33, 306.0, 'TEAM-A-04', 'A', 1.71, 'A', 6.0),
('CAR-08', 820, 79, 325, 'medium', 500.0, 69.7, 319.0, 'TEAM-A-04', 'A', 1.78, 'B', 6.0),
('CAR-09', 812, 69, 338, 'hard', 510.0, 75.3, 291.0, 'TEAM-B-01', 'B', 1.85, 'C', 3.0),
('CAR-10', 840, 91, 331, 'soft', 510.0, 57.03, 304.0, 'TEAM-B-01', 'B', 1.61, 'A', 3.0),
('CAR-11', 832, 81, 324, 'medium', 510.0, 62.09, 286.0, 'TEAM-B-02', 'B', 1.68, 'B', 4.0),
('CAR-12', 824, 71, 337, 'hard', 510.0, 67.38, 299.0, 'TEAM-B-02', 'B', 1.75, 'C', 4.0),
('CAR-13', 816, 93, 330, 'soft', 510.0, 72.87, 281.0, 'TEAM-B-03', 'B', 1.82, 'A', 5.0),
('CAR-14', 844, 83, 323, 'medium', 510.0, 78.59, 294.0, 'TEAM-B-03', 'B', 1.89, 'B', 5.0),
('CAR-15', 836, 73, 336, 'hard', 510.0, 59.89, 307.0, 'TEAM-B-04', 'B', 1.65, 'C', 6.0),
('CAR-16', 828, 63, 329, 'soft', 510.0, 65.08, 289.0, 'TEAM-B-04', 'B', 1.72, 'A', 6.0),
('CAR-17', 820, 85, 322, 'medium', 515.0, 70.49, 282.0, 'TEAM-C-01', 'C', 1.79, 'B', 3.0),
('CAR-18', 812, 75, 335, 'hard', 515.0, 76.11, 264.0, 'TEAM-C-01', 'C', 1.86, 'C', 3.0),
('CAR-19', 840, 65, 328, 'soft', 515.0, 57.74, 277.0, 'TEAM-C-02', 'C', 1.62, 'A', 4.0),
('CAR-20', 832, 87, 321, 'medium', 515.0, 62.83, 290.0, 'TEAM-C-02', 'C', 1.69, 'B', 4.0)
) AS p(id, old_weight, old_driver_weight, old_speed, compound,
       new_weight, new_driver_weight, new_speed, team_id, category, height,
       strategy, service)
WHERE c.car_id = p.id AND c.car_weight_kg = p.old_weight
 AND c.driver_weight_kg = p.old_driver_weight AND c.top_speed_kmh = p.old_speed
 AND c.tire_compound = p.compound AND c.driver_id = replace(p.id, 'CAR-', 'DRV-');
