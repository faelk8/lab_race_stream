import type { RaceIncident, RaceStartConfiguration } from "./types";

const STORAGE_KEY = "racestream.race-setup.v1";
const STORAGE_VERSION = 1;

export const DEFAULT_RACE_SETUP: RaceStartConfiguration = {
    rain_enabled: false,
    rain_start_lap: 1,
    rain_intensity: 0.5,
    incidents: [],
};

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function isIncident(value: unknown): value is RaceIncident {
    if (!value || typeof value !== "object") return false;
    const incident = value as Partial<RaceIncident>;
    return (incident.incident_type === "tire_puncture" || incident.incident_type === "collision" || incident.incident_type === "time_penalty") &&
        Number.isInteger(incident.lap) && Number(incident.lap) >= 1 &&
        typeof incident.car_id === "string" &&
        typeof incident.second_car_id === "string" &&
        Number.isInteger(incident.penalty_seconds) && Number(incident.penalty_seconds) >= 0;
}

function isConfiguration(value: unknown): value is RaceStartConfiguration {
    if (!value || typeof value !== "object") return false;
    const setup = value as Partial<RaceStartConfiguration>;
    return typeof setup.rain_enabled === "boolean" &&
        Number.isInteger(setup.rain_start_lap) && Number(setup.rain_start_lap) >= 1 &&
        typeof setup.rain_intensity === "number" && Number.isFinite(setup.rain_intensity) &&
        setup.rain_intensity >= 0.1 && setup.rain_intensity <= 1 &&
        Array.isArray(setup.incidents) && setup.incidents.length <= 20 &&
        setup.incidents.every(isIncident);
}

function browserStorage(): StorageLike | null {
    try {
        return typeof window === "undefined" ? null : window.localStorage;
    } catch {
        return null;
    }
}

/** Carrega o rascunho de configuração validado do armazenamento local. */
export function loadRaceSetup(storage: StorageLike | null = browserStorage()): RaceStartConfiguration {
    if (!storage) return { ...DEFAULT_RACE_SETUP, incidents: [] };
    try {
        const raw = storage.getItem(STORAGE_KEY);
        if (!raw) return { ...DEFAULT_RACE_SETUP, incidents: [] };
        const saved: unknown = JSON.parse(raw);
        if (!saved || typeof saved !== "object" || !("version" in saved) || !("configuration" in saved)) {
            return { ...DEFAULT_RACE_SETUP, incidents: [] };
        }
        const envelope = saved as { version: unknown; configuration: unknown };
        return envelope.version === STORAGE_VERSION && isConfiguration(envelope.configuration)
            ? { ...envelope.configuration, incidents: [...envelope.configuration.incidents] }
            : { ...DEFAULT_RACE_SETUP, incidents: [] };
    } catch {
        return { ...DEFAULT_RACE_SETUP, incidents: [] };
    }
}

/** Persiste o rascunho de configuração da próxima corrida. */
export function saveRaceSetup(setup: RaceStartConfiguration, storage: StorageLike | null = browserStorage()): void {
    if (!storage) return;
    try {
        storage.setItem(STORAGE_KEY, JSON.stringify({ version: STORAGE_VERSION, configuration: setup }));
    } catch {
        // O formulário continua funcional se o navegador bloquear o armazenamento.
    }
}

/** Apaga o rascunho salvo após o início confirmado ou a limpeza manual. */
export function clearRaceSetup(storage: StorageLike | null = browserStorage()): void {
    if (!storage) return;
    try {
        storage.removeItem(STORAGE_KEY);
    } catch {
        // A falha de armazenamento não deve interromper os controles da corrida.
    }
}
