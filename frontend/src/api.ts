import type { CarConfiguration, RaceSnapshot } from "./types";

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${apiBase}${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `HTTP ${response.status}`);
    }
    return response.json() as Promise<T>;
}

export function getCars(): Promise<CarConfiguration[]> {
    return request<CarConfiguration[]>("/api/cars");
}

export function getLatestRace(): Promise<RaceSnapshot | null> {
    return request<RaceSnapshot | null>("/api/races/latest");
}

export function updateCar(
    configuration: CarConfiguration,
): Promise<CarConfiguration> {
    return request<CarConfiguration>(`/api/cars/${configuration.car_id}`, {
        method: "PUT",
        body: JSON.stringify(configuration),
    });
}

export function telemetrySocketUrl(raceId: string): string {
    const websocketBase = apiBase.replace(/^http/, "ws");
    return `${websocketBase}/ws/races/${encodeURIComponent(raceId)}`;
}
export function startRace(): Promise<RaceSnapshot> { return request("/api/races/start", { method: "POST" }); }
export function stopRace(id: string): Promise<RaceSnapshot> { return request(`/api/races/${encodeURIComponent(id)}/stop`, { method: "POST" }); }
