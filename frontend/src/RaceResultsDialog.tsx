import { X } from "lucide-react";
import type { RaceMedallionDriverResult, RaceMedallionResults } from "./types";
import { countryFlag } from "./racePresentation";

function formatLapTime(milliseconds: number | null): string {
    if (milliseconds === null || !Number.isFinite(milliseconds)) return "—";
    const minutes = Math.floor(milliseconds / 60_000);
    const seconds = Math.floor((milliseconds % 60_000) / 1_000);
    const millis = Math.round(milliseconds % 1_000);
    return `${minutes}:${seconds.toString().padStart(2, "0")}.${millis
        .toString()
        .padStart(3, "0")}`;
}

function Medalha({ resultado }: { resultado: RaceMedallionDriverResult }) {
    if (!resultado.podium_medal) return <span className="results-no-medal">—</span>;
    return (
        <span className={`results-medal results-medal-${resultado.podium_medal}`}>
            <span aria-hidden="true">{resultado.trophy ?? "🏆"}</span>
            <small>{resultado.podium_medal}</small>
        </span>
    );
}

export function RaceResultsDialog({
    results,
    loading,
    onClose,
}: {
    results: RaceMedallionResults | null;
    loading: boolean;
    onClose: () => void;
}) {
    return (
        <div className="results-backdrop" role="presentation">
            <section
                className="results-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="results-title"
            >
                <button className="results-close" type="button" onClick={onClose} aria-label="Fechar resultados">
                    <X size={18} />
                </button>
                <header className="results-header">
                    <span>FIM DE PROVA · {results?.race_id ?? "CLASSIFICAÇÃO"}</span>
                    <h2 id="results-title">Resultado da corrida</h2>
                    <p>Classificação oficial calculada a partir das voltas e paradas arquivadas no MinIO.</p>
                </header>
                {loading && !results ? (
                    <p className="results-loading" role="status">Consolidando a classificação no Spark…</p>
                ) : (
                    <div className="results-table-wrap">
                        <table className="results-table">
                            <thead>
                                <tr>
                                    <th>Pos.</th>
                                    <th>Piloto</th>
                                    <th>Melhor volta</th>
                                    <th>Pior volta</th>
                                    <th>Média</th>
                                    <th>Boxes</th>
                                    <th>Pódio</th>
                                </tr>
                            </thead>
                            <tbody>
                                {results?.classification.map((item) => (
                                    <tr className={`results-row results-row-${item.podium_medal ?? "normal"}`} key={item.car_id}>
                                        <td className="results-position">{item.position}<small>{item.car_id}</small></td>
                                        <td>
                                            <span className="results-driver">
                                                <span className="results-flag" aria-label={item.driver_country_code || "País não informado"}>
                                                    {item.country_flag || countryFlag(item.driver_country_code)}
                                                </span>
                                                <span><strong>{item.driver_name || item.driver_id}</strong><small>{item.team_id}</small></span>
                                            </span>
                                        </td>
                                        <td>{formatLapTime(item.best_lap_time_ms)}</td>
                                        <td>{formatLapTime(item.worst_lap_time_ms)}</td>
                                        <td>{formatLapTime(item.average_lap_time_ms)}</td>
                                        <td>{item.pit_stop_count}</td>
                                        <td><Medalha resultado={item} /></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>
        </div>
    );
}
