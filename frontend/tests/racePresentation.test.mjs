import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/racePresentation.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } });
const { rankCars, leaderGapMs, formatGap, countryFlag, countryName, RaceFrameBuffer, spreadTrackPositions } =
    await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

function event(carId, position, elapsed = 1, lap = 2, progress = 0.9) {
    return { car_id: carId, race_id: "corrida-teste", race_position: position,
        elapsed_race_seconds: elapsed, event_time: `instante-${elapsed}`, lap,
        track_progress: progress, last_lap_time_ms: position === 15 ? 70_000 : 90_000 };
}

test("O 15º tem maior atraso que o 4º mesmo com uma última volta mais rápida", () => {
    const cars = Array.from({ length: 20 }, (_, i) => ({ car_id: `CAR-${i + 1}` })).reverse();
    const events = Object.fromEntries(cars.map((car) => {
        const position = Number(car.car_id.split("-")[1]);
        return [car.car_id, event(car.car_id, position, 1, 2, 1 - position / 25)];
    }));
    const ranked = rankCars(cars, events);
    const gaps = ranked.map((car) => leaderGapMs(events[car.car_id], events["CAR-1"]));
    assert.deepEqual(ranked.map((car) => events[car.car_id].race_position), Array.from({ length: 20 }, (_, i) => i + 1));
    assert.ok(events["CAR-15"].last_lap_time_ms < events["CAR-4"].last_lap_time_ms);
    assert.ok(gaps[14] > gaps[3]);
    assert.ok(gaps.every((gap, i) => i === 0 || gap >= gaps[i - 1]));
});

test("O pelotão prioriza distância de corrida, não o tempo da última volta", () => {
    const cars = [{ car_id: "CAR-A" }, { car_id: "CAR-B" }];
    const events = {
        "CAR-A": { ...event("CAR-A", 1), distance_m: 200, last_lap_time_ms: 95_000 },
        "CAR-B": { ...event("CAR-B", 2), distance_m: 210, last_lap_time_ms: 80_000 },
    };
    assert.deepEqual(rankCars(cars, events).map((car) => car.car_id), ["CAR-B", "CAR-A"]);
});

test("Marcadores seguem a ordem do pelotão e mantêm espaçamento mínimo na pista", () => {
    const cars = [
        { ...event("CAR-2", 2), track_progress: 0.1001, distance_m: 1001 },
        { ...event("CAR-1", 1), track_progress: 0.1002, distance_m: 1002 },
        { ...event("CAR-3", 3), track_progress: 0.1000, distance_m: 1000 },
    ];
    const positions = spreadTrackPositions(cars, 1000, 10000, 0, 9);
    const ordered = [...cars].sort((a, b) => a.race_position - b.race_position);
    for (let i = 1; i < ordered.length; i++) {
        let gap = positions.get(ordered[i - 1].car_id) - positions.get(ordered[i].car_id);
        if (gap < 0) gap += 1000;
        assert.ok(gap >= 9);
    }
    const swapped = cars.map((car) => ({
        ...car,
        race_position: car.race_position === 1 ? 3 : car.race_position === 3 ? 1 : 2,
        distance_m: car.car_id === "CAR-3" ? 1003 : car.car_id === "CAR-2" ? 1002 : 1001,
    }));
    const swappedPositions = spreadTrackPositions(swapped, 1000, 10000, 0, 9);
    assert.notEqual(swappedPositions.get("CAR-3"), positions.get("CAR-3"));
});

test("O atraso inclui voltas completas e mantém a precisão de milissegundos", () => {
    assert.equal(leaderGapMs(event("CAR-2", 2, 1, 2, 0.9), event("CAR-1", 1, 1, 3, 0.1)), 18_000);
    assert.equal(formatGap(123_456), "+2:03.456");
    assert.equal(formatGap(null), "--:--.---");
});

test("Quadros completos mantêm a classificação ao receber ultrapassagem fora de ordem", () => {
    const buffer = new RaceFrameBuffer("corrida-teste", ["CAR-1", "CAR-2"]);
    assert.equal(buffer.push(event("CAR-1", 1, 1)), null);
    assert.equal(buffer.push(event("CAR-2", 1, 2)), null);
    const first = buffer.push(event("CAR-2", 2, 1));
    assert.equal(first["CAR-1"].race_position, 1);
    assert.equal(first["CAR-2"].race_position, 2);
    const second = buffer.push(event("CAR-1", 2, 2));
    assert.equal(second["CAR-2"].race_position, 1);
    assert.equal(second["CAR-1"].race_position, 2);
    assert.equal(buffer.push(event("CAR-1", 1, 1)), null);
    assert.equal(buffer.push({ ...event("CAR-2", 2, 3), race_id: "outra-corrida" }), null);
});

test("Posições duplicadas não são publicadas como um quadro completo", () => {
    const buffer = new RaceFrameBuffer("corrida-teste", ["CAR-1", "CAR-2"]);
    assert.equal(buffer.push(event("CAR-1", 1)), null);
    assert.equal(buffer.push(event("CAR-2", 1)), null);
});

test("Um quadro recente pode completar mesmo após muitos quadros incompletos", () => {
    const buffer = new RaceFrameBuffer("corrida-teste", ["CAR-1", "CAR-2"]);
    for (let i = 1; i <= 80; i++) buffer.push(event("CAR-1", 1, i));
    const latest = buffer.push(event("CAR-2", 2, 80));
    assert.equal(latest["CAR-1"].elapsed_race_seconds, 80);
    assert.equal(buffer.push(event("CAR-2", 2, 1)), null);
});

test("Bandeiras correspondem ao país e os nomes aparecem em português", () => {
    assert.equal(countryFlag("BR"), "🇧🇷");
    assert.equal(countryFlag("JP"), "🇯🇵");
    assert.equal(countryFlag(""), "");
    assert.equal(countryName("BR"), "Brasil");
});

test("O mapa mantém os carros clicáveis sem renderizar balões de identificação", () => {
    const source = readFileSync(new URL("../src/InterlagosTrack.tsx", import.meta.url), "utf8");
    assert.match(source, /onSelectCar\(car\.car_id\)/);
    assert.doesNotMatch(source, /map-car-balloon|placeMapLabels/);
});

test("A parada atualiza o quadro sem avançar o tempo da corrida", () => {
    const buffer = new RaceFrameBuffer("corrida-teste", ["CAR-1", "CAR-2"]);
    buffer.push(event("CAR-1", 1));
    buffer.push(event("CAR-2", 2));
    const stopped = (id, position) => ({ ...event(id, position), event_time: "instante-1-parada", race_status: "stopped", speed_kmh: 0 });
    assert.equal(buffer.push(stopped("CAR-1", 1)), null);
    const frame = buffer.push(stopped("CAR-2", 2));
    assert.equal(frame["CAR-1"].race_status, "stopped");
    assert.equal(frame["CAR-2"].elapsed_race_seconds, 1);
    assert.equal(buffer.push(event("CAR-1", 1)), null);
});
