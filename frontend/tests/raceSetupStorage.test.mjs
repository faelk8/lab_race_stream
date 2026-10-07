import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/raceSetupStorage.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
});
const storageModule = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

function memoryStorage() {
    const data = new Map();
    return {
        getItem: (key) => data.get(key) ?? null,
        setItem: (key, value) => data.set(key, String(value)),
        removeItem: (key) => data.delete(key),
    };
}

test("Rascunho de corrida sobrevive à recarga e mantém incidentes e chuva", () => {
    const storage = memoryStorage();
    const setup = {
        rain_enabled: true,
        rain_start_lap: 12,
        rain_intensity: 0.75,
        incidents: [{ incident_type: "collision", lap: 15, car_id: "CAR-10", second_car_id: "CAR-12", penalty_seconds: 0 }],
    };
    storageModule.saveRaceSetup(setup, storage);
    assert.deepEqual(storageModule.loadRaceSetup(storage), setup);
});

test("Rascunho inválido é ignorado e a limpeza remove o armazenamento", () => {
    const storage = memoryStorage();
    storageModule.saveRaceSetup({ rain_enabled: false, rain_start_lap: 0, rain_intensity: 5, incidents: [] }, storage);
    assert.deepEqual(storageModule.loadRaceSetup(storage), storageModule.DEFAULT_RACE_SETUP);
    storageModule.saveRaceSetup({ rain_enabled: false, rain_start_lap: 1, rain_intensity: 0.5, incidents: [] }, storage);
    storageModule.clearRaceSetup(storage);
    assert.deepEqual(storageModule.loadRaceSetup(storage), storageModule.DEFAULT_RACE_SETUP);
});
