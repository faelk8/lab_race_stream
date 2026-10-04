import { useEffect, useState } from "react";
import type { CarAnalytics, CarConfiguration, RaceTelemetry } from "./types";
import { formatGap, teamName } from "./racePresentation";

function time(value: number | null | undefined): string {
    return value == null || value === 0 ? "—" : `${(value / 1000).toFixed(3)} s`;
}

interface Props {
    raceId?: string;
    selectedCarId: string | null;
    selectedTeam: string | null;
    cars: CarConfiguration[];
    telemetry: Record<string, RaceTelemetry>;
    analytics: Record<string, CarAnalytics>;
}

export function RaceInsights({ raceId, selectedCarId, selectedTeam, cars, telemetry, analytics }: Props) {
    const [laps, setLaps] = useState<{ lap: number; lap_time_ms: number; sectors_ms: number[]; pit_lap: boolean; valid: boolean }[]>([]);
    const [error, setError] = useState(false);
    const [reference, setReference] = useState<"personal" | "team" | "race">("personal");
    const [pointPositions, setPointPositions] = useState<Record<string, number>>({});
    const summary = selectedCarId ? analytics[selectedCarId] : undefined;
    const event = selectedCarId ? telemetry[selectedCarId] : undefined;
    const participants = selectedTeam ? cars.filter(c => c.team_id === selectedTeam) : cars.filter(c => c.car_id === selectedCarId);
    useEffect(() => {
        const controller = new AbortController();
        const api = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
        fetch(`${api}/api/tracks/interlagos`, { signal: controller.signal })
            .then(r => { if (!r.ok) throw new Error(); return r.json(); })
            .then(track => setPointPositions(Object.fromEntries([
                ...track.checkpoints.map((p: number, i: number) => [`P${String(i + 1).padStart(2, "0")}`, p]),
                ["S1", track.sector_ends[0]], ["S2", track.sector_ends[1]], ["SF", 1],
            ])))
            .catch(e => { if (e.name !== "AbortError") setPointPositions({}); });
        return () => controller.abort();
    }, []);
    const chart = (summary?.splits ?? []).filter(s => s.valid && pointPositions[s.checkpoint_id] != null)
        .map(s => ({ x: pointPositions[s.checkpoint_id], current: s.segment_time_ms,
            best: reference === "personal" ? s.best_personal_ms : reference === "team" ? s.best_team_ms : s.best_race_ms }))
        .sort((a, b) => a.x - b.x);
    const chartMaximum = Math.max(1, ...chart.flatMap(p => [p.current, p.best ?? 0]));
    useEffect(() => {
        const controller = new AbortController();
        setLaps([]);
        setError(false);
        if (raceId && selectedCarId) {
            const api = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
            fetch(`${api}/api/races/${encodeURIComponent(raceId)}/cars/${encodeURIComponent(selectedCarId)}/laps`, { signal: controller.signal })
                .then(r => { if (!r.ok) throw new Error(); return r.json(); }).then(setLaps)
                .catch(e => { if (e.name !== "AbortError") setError(true); });
        }
        return () => controller.abort();
    }, [raceId, selectedCarId, summary?.lap_count]);
    return <section className="insights-panel" aria-label="Análises da corrida">
        <div className="panel-heading"><div><p className="eyebrow">CRONOMETRAGEM POR PASSAGEM</p><h2>{selectedTeam ? teamName(selectedTeam) : "ACOMPANHAMENTO DO PILOTO"}</h2></div></div>
        <div className="comparison-cards">{participants.map(car => {
            const data = analytics[car.car_id];
            return <article key={car.car_id}><strong>{car.driver_name}</strong><small>{car.car_id} · {teamName(car.team_id)}</small>
                <dl><dt>Última volta</dt><dd>{time(data?.last_lap_time_ms)}</dd><dt>Melhor volta</dt><dd>{time(data?.best_lap_time_ms)}</dd><dt>Pior volta</dt><dd>{time(data?.worst_lap_time_ms)}</dd><dt>Volta teórica</dt><dd>{time(data?.theoretical_lap_ms)}</dd><dt>Ritmo limpo (até 5 voltas)</dt><dd>{time(data?.pace_ms)}</dd><dt>Intervalo à frente</dt><dd>{formatGap(data?.interval_to_ahead_ms ?? null)}</dd></dl>
                <small>Referência dos intervalos: {data?.gap_reference || "aguardando passagem comum"}{data?.gap_reference_age_ms != null ? ` · medida há ${(data.gap_reference_age_ms / 1000).toFixed(1)} s de corrida` : ""}</small>
            </article>;
        })}</div>
        <div className="g-force-panel"><div><h3>FORÇA G · ESTIMATIVA DO SIMULADOR</h3><p>Longitudinal: {event?.g_longitudinal?.toFixed(2) ?? "—"} g · lateral: {event?.g_lateral?.toFixed(2) ?? "—"} g</p><p>Pico na janela: {event?.g_peak?.toFixed(2) ?? "—"} g · atualização de 1 segundo</p></div>
            <svg viewBox="0 0 100 100" width="100" height="100" role="img" aria-label="Aceleração lateral e longitudinal estimada"><circle cx="50" cy="50" r="42" fill="none" stroke="#465064" /><path d="M8 50H92M50 8V92" stroke="#465064" /><circle cx={50 + Math.max(-4, Math.min(4, event?.g_lateral ?? 0)) * 10} cy={50 - Math.max(-4, Math.min(4, event?.g_longitudinal ?? 0)) * 10} r="5" fill="#61db9b" /></svg>
        </div>
        <label className="split-reference">Comparar parciais com <select value={reference} onChange={e => setReference(e.target.value as typeof reference)}><option value="personal">melhor pessoal</option><option value="team">melhor da equipe</option><option value="race">melhor da corrida</option></select></label>
        <p className="split-legend">Roxo: melhor da corrida · verde: melhor pessoal · amarelo: sem melhora · cinza: sem medida válida. Pontos de cronometragem simulados.</p>
        {chart.length > 1 && <figure className="split-chart"><figcaption>Parciais por posição na pista · atual em verde, referência em roxo</figcaption>
            <svg viewBox="0 0 640 180" role="img" aria-label="Comparação dos tempos de trecho na mesma posição da pista">
                <path d="M45 15V150H625" fill="none" stroke="#6e7d91" />
                <text x="5" y="20" fill="currentColor" fontSize="12">{(chartMaximum / 1000).toFixed(1)} s</text>
                <text x="45" y="170" fill="currentColor" fontSize="12">0%</text><text x="580" y="170" fill="currentColor" fontSize="12">100%</text>
                <polyline fill="none" stroke="#6de8a1" strokeWidth="2" points={chart.map(p => `${45 + p.x * 570},${150 - p.current / chartMaximum * 130}`).join(" ")} />
                <polyline fill="none" stroke="#d099ff" strokeWidth="2" points={chart.filter(p => p.best != null).map(p => `${45 + p.x * 570},${150 - p.best! / chartMaximum * 130}`).join(" ")} />
            </svg><small>Passagens medidas; linhas apenas ligam os pontos. A tabela identifica a volta de cada parcial.</small>
        </figure>}
        <div className="insights-table-wrap"><table className="insights-table"><thead><tr><th>Ponto</th><th>Volta</th><th>Trecho</th><th>Acumulado</th><th>Referência</th><th>Diferença</th><th>Resultado</th></tr></thead><tbody>{summary?.splits.map(split => {
            const best = reference === "personal" ? split.best_personal_ms : reference === "team" ? split.best_team_ms : split.best_race_ms;
            const delta = best == null || !split.valid ? null : split.segment_time_ms - best;
            return <tr key={split.checkpoint_id} className={`split-${split.color}`}><th>{split.checkpoint_id}</th><td>{split.lap}</td><td>{time(split.segment_time_ms)}</td><td>{time(split.lap_elapsed_ms)}</td><td>{time(best)}</td><td>{delta == null ? "—" : `${delta >= 0 ? "+" : ""}${(delta / 1000).toFixed(3)} s`}</td><td>{{purple: "Melhor da corrida", green: "Melhor pessoal", yellow: "Sem melhora", gray: "Não comparável"}[split.color] ?? "—"}</td></tr>;
        })}</tbody></table>{!summary?.splits.length && <p>Aguardando passagens cronometradas.</p>}</div>
        <details><summary>Histórico de voltas ({laps.length})</summary>{error && <p role="alert">Não foi possível carregar o histórico.</p>}<div className="insights-table-wrap"><table className="insights-table"><thead><tr><th>Volta</th><th>Tempo</th><th>S1</th><th>S2</th><th>S3</th><th>Condição</th></tr></thead><tbody>{laps.map(lap => <tr key={lap.lap}><td>{lap.lap}</td><td>{time(lap.lap_time_ms)}</td>{lap.sectors_ms.map((value, i) => <td key={i}>{time(value)}</td>)}<td>{!lap.valid ? "Incompleta" : lap.pit_lap ? "Com boxes" : "Normal"}</td></tr>)}</tbody></table></div></details>
    </section>;
}
