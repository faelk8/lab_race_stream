ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_tire_compound_check;
ALTER TABLE cars
    ADD CONSTRAINT cars_tire_compound_check
    CHECK (tire_compound IN ('soft', 'medium', 'hard', 'wet'));
