import type { CarConfiguration, RaceIncident, RaceTelemetry } from "./types";

const REFERENCE_LAP_MS = 90_000;

/** Ordena as configurações pela classificação de um quadro completo. */
export function rankCars(cars: CarConfiguration[], events: Record<string, RaceTelemetry>): CarConfiguration[] {
    return [...cars].sort((left, right) =>
        compareRaceOrder(events[left.car_id], events[right.car_id]) ||
        left.car_id.localeCompare(right.car_id),
    );
}

export function compareRaceOrder(left: RaceTelemetry | undefined, right: RaceTelemetry | undefined): number {
    if (!left || !right) return (left ? -1 : 0) - (right ? -1 : 0);
    if (left.distance_m != null && right.distance_m != null && left.distance_m !== right.distance_m) {
        return right.distance_m - left.distance_m;
    }
    return left.race_position - right.race_position;
}

/** Retire carros fora do mapa, mantendo os dados deles no pelotão e no histórico. */
export function visibleTrackCars(cars: RaceTelemetry[]): RaceTelemetry[] {
    return cars.filter((car) => car.car_status !== "retired");
}

/** Retorna os carros ainda disponíveis para um evento na volta informada. */
export function availableCarsForIncidentLap<T extends { car_id: string }>(
    cars: T[], incidents: RaceIncident[], lap: number,
): T[] {
    const retired = new Set<string>();
    for (const incident of incidents) {
        if (incident.incident_type === "collision" && incident.lap <= lap) {
            retired.add(incident.car_id);
            retired.add(incident.second_car_id);
        }
    }
    return cars.filter((car) => !retired.has(car.car_id));
}

/** Reconhece uma repetição do mesmo evento, sem depender da ordem da colisão. */
export function isDuplicateIncident(incidents: RaceIncident[], candidate: RaceIncident): boolean {
    const candidateCars = candidate.incident_type === "collision"
        ? [candidate.car_id, candidate.second_car_id].sort().join(":")
        : candidate.car_id;
    return incidents.some((incident) => {
        if (incident.incident_type !== candidate.incident_type || incident.lap !== candidate.lap ||
            incident.penalty_seconds !== candidate.penalty_seconds) return false;
        const incidentCars = incident.incident_type === "collision"
            ? [incident.car_id, incident.second_car_id].sort().join(":")
            : incident.car_id;
        return incidentCars === candidateCars;
    });
}

/** Distribui visualmente marcadores próximos sem alterar a ordem de corrida. */
export function spreadTrackPositions(cars: RaceTelemetry[], pathLength: number, trackLength: number, mapOffset = 0, minimumGap = 9): Map<string, number> {
    const positions = new Map<string, number>();
    if (pathLength <= 0 || cars.length === 0) return positions;
    const ordered = [...cars].sort(compareRaceOrder);
    let previous: number | null = null;
    for (const car of ordered) {
        const physicalDistance = car.distance_m ?? car.track_progress * trackLength;
        const raw = (physicalDistance / trackLength + mapOffset) * pathLength;
        let unwrapped = raw;
        if (previous !== null) {
            unwrapped += Math.round((previous - raw) / pathLength) * pathLength;
            while (unwrapped >= previous) unwrapped -= pathLength;
            if (previous - unwrapped < minimumGap) unwrapped = previous - minimumGap;
        }
        previous = unwrapped;
        positions.set(car.car_id, (unwrapped % pathLength + pathLength) % pathLength);
    }
    return positions;
}

/** Estima o atraso pela distância atrás do líder, em milissegundos físicos. */
export function leaderGapMs(car: RaceTelemetry | undefined, leader: RaceTelemetry | undefined): number | null {
    if (!car || !leader) return null;
    const distance = (leader.lap - 1 + leader.track_progress) - (car.lap - 1 + car.track_progress);
    return Math.round(Math.max(0, distance) * REFERENCE_LAP_MS);
}

/** Formata o atraso incluindo minutos, segundos e milissegundos. */
export function formatGap(milliseconds: number | null): string {
    if (milliseconds === null) return "--:--.---";
    const minutes = Math.floor(milliseconds / 60_000);
    const seconds = Math.floor(milliseconds % 60_000 / 1_000);
    return `+${minutes}:${seconds.toString().padStart(2, "0")}.${(milliseconds % 1_000).toString().padStart(3, "0")}`;
}

/** Converte o código ISO do país em uma bandeira Unicode. */
export function countryFlag(code: string): string {
    if (!/^[A-Z]{2}$/.test(code)) return "";
    return [...code].map((letter) => String.fromCodePoint(127397 + letter.charCodeAt(0))).join("");
}

/** Mostra o nome do país em português do Brasil. */
export function countryName(code: string): string {
    return code ? new Intl.DisplayNames(["pt-BR"], { type: "region" }).of(code) ?? code : "País não informado";
}

/** Apresenta o identificador padrão da equipe com um nome legível. */
export function teamName(id: string): string {
    const match = /^TEAM-([ABC])-(\d+)$/.exec(id);
    return match ? `Equipe ${match[1]}${Number(match[2])}` : id;
}

/** Reúne eventos do mesmo instante e rejeita quadros antigos ou incompletos. */
export class RaceFrameBuffer {
    private readonly expected: Set<string>;
    private readonly frames = new Map<string, Record<string, RaceTelemetry>>();
    private committedElapsed = -1;
    private committedEventTime = "";

    constructor(private readonly raceId: string, carIds: string[]) {
        this.expected = new Set(carIds);
    }

    push(event: RaceTelemetry): Record<string, RaceTelemetry> | null {
        if (event.race_id !== this.raceId || !this.expected.has(event.car_id) ||
            !Number.isFinite(event.elapsed_race_seconds) || (event.elapsed_race_seconds < this.committedElapsed || (event.elapsed_race_seconds === this.committedElapsed && event.event_time <= this.committedEventTime))) return null;
        const key = `${event.event_time}:${event.elapsed_race_seconds}`;
        const frame = this.frames.get(key) ?? {};
        frame[event.car_id] = event;
        this.frames.set(key, frame);
        if (this.frames.size > 32) {
            const oldest = [...this.frames.entries()].sort(([, left], [, right]) =>
                Object.values(left)[0].elapsed_race_seconds - Object.values(right)[0].elapsed_race_seconds,
            )[0][0];
            this.frames.delete(oldest);
        }
        const positions = Object.values(frame).map((car) => car.race_position);
        if (positions.length !== this.expected.size || new Set(positions).size !== this.expected.size ||
            positions.some((position) => !Number.isInteger(position) || position < 1 || position > this.expected.size)) return null;
        this.committedElapsed = event.elapsed_race_seconds;
        this.committedEventTime = event.event_time;
        for (const [frameKey, pending] of this.frames) {
            if (Object.values(pending)[0].elapsed_race_seconds <= this.committedElapsed) this.frames.delete(frameKey);
        }
        return frame;
    }
}
