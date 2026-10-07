import type { CarConfiguration, RaceSnapshot, RaceStartConfiguration } from "./types";

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${apiBase}${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!response.ok) {
        const detail = await response.text();
        let message = detail;
        try {
            const payload: unknown = JSON.parse(detail);
            if (payload && typeof payload === "object" && "detail" in payload) {
                const validation = payload.detail;
                if (typeof validation === "string") message = validation;
                else if (Array.isArray(validation)) {
                    message = validation
                        .map((item) =>
                            item && typeof item === "object" && "msg" in item
                                ? String(item.msg).replace(/^Value error, /, "")
                                : "",
                        )
                        .filter(Boolean)
                        .join(" · ");
                }
            }
        } catch {
            // Respostas que não sejam JSON são exibidas como texto.
        }
        throw new Error(message || `HTTP ${response.status}`);
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
export function startRace(configuration: RaceStartConfiguration): Promise<RaceSnapshot> { return request("/api/races/start", { method: "POST", body: JSON.stringify(configuration) }); }
export function stopRace(id: string): Promise<RaceSnapshot> { return request(`/api/races/${encodeURIComponent(id)}/stop`, { method: "POST" }); }
export function pauseRace(id: string): Promise<RaceSnapshot> { return request(`/api/races/${encodeURIComponent(id)}/pause`, { method: "POST" }); }
export function resumeRace(id: string): Promise<RaceSnapshot> { return request(`/api/races/${encodeURIComponent(id)}/resume`, { method: "POST" }); }
