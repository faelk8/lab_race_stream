import {
    Activity,
    Check,
    ChevronRight,
    CircleHelp,
    Flag,
    Gauge,
    Radio,
    Play,
    Square,
    Save,
    Settings2,
    Timer,
    Trophy,
    Weight,
    Zap,
} from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useState } from "react";
import { getCars, getLatestRace, startRace, stopRace, telemetrySocketUrl, updateCar } from "./api";
import { InterlagosTrack } from "./InterlagosTrack";
import { countryFlag, countryName, formatGap, leaderGapMs, RaceFrameBuffer, rankCars, teamName } from "./racePresentation";
import type { CarConfiguration, RaceSnapshot, RaceTelemetry, TireCompound } from "./types";

type ConnectionState = "connecting" | "connected" | "reconnecting";

function formatRaceClock(seconds: number): string {
    const bounded = Math.max(0, Math.ceil(seconds));
    return `${Math.floor(bounded / 60).toString().padStart(2, "0")}:${(bounded % 60)
        .toString()
        .padStart(2, "0")}`;
}

function formatLapTime(milliseconds: number | null | undefined): string {
    if (milliseconds == null) return "--:--.---";
    const minutes = Math.floor(milliseconds / 60_000);
    const seconds = Math.floor((milliseconds % 60_000) / 1_000);
    const millis = Math.round(milliseconds % 1_000);
    return `${minutes}:${seconds.toString().padStart(2, "0")}.${millis
        .toString()
        .padStart(3, "0")}`;
}

function tireLabel(compound: TireCompound): string {
    return { soft: "MACIO", medium: "MÉDIO", hard: "DURO" }[compound];
}

export function App() {
    const [cars, setCars] = useState<CarConfiguration[]>([]);
    const [race, setRace] = useState<RaceSnapshot | null>(null);
    const [telemetryByCar, setTelemetryByCar] = useState<Record<string, RaceTelemetry>>({});
    const [selectedCarId, setSelectedCarId] = useState<string | null>(null);
    const [draft, setDraft] = useState<CarConfiguration | null>(null);
    const [connection, setConnection] = useState<ConnectionState>("connecting");
    const [raceAction, setRaceAction] = useState<"start" | "stop" | null>(null);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const telemetry = useDeferredValue(telemetryByCar);

    useEffect(() => {
        let active = true;
        const refresh = async () => {
            try {
                const [loadedCars, latestRace] = await Promise.all([getCars(), getLatestRace()]);
                if (!active) return;
                setCars(loadedCars);
                setSelectedCarId((current) => current ?? loadedCars[0]?.car_id ?? null);
                setRace(latestRace);
                setError(null);
            } catch {
                if (active) setError("API indisponível. Verifique os serviços do RaceStream.");
            }
        };
        void refresh();
        const refreshTimer = window.setInterval(() => {
            void getLatestRace().then(setRace).catch(() => undefined);
        }, 2_000);
        return () => {
            active = false;
            window.clearInterval(refreshTimer);
        };
    }, []);

    useEffect(() => {
        const selected = cars.find((car) => car.car_id === selectedCarId);
        if (selected) setDraft({ ...selected });
    }, [cars, selectedCarId]);

    useEffect(() => {
        if (!race?.race_id || cars.length === 0) return;
        const frameBuffer = new RaceFrameBuffer(race.race_id, cars.map((car) => car.car_id));
        let stopped = false;
        let socket: WebSocket | null = null;
        let reconnectTimer = 0;
        setTelemetryByCar({});
        setConnection("connecting");

        const connect = () => {
            if (stopped) return;
            socket = new WebSocket(telemetrySocketUrl(race.race_id));
            socket.onopen = () => setConnection("connected");
            socket.onmessage = (message) => {
                const event = JSON.parse(message.data) as RaceTelemetry;
                const frame = frameBuffer.push(event);
                if (frame) startTransition(() => setTelemetryByCar(frame));
            };
            socket.onclose = () => {
                if (!stopped) {
                    setConnection("reconnecting");
                    reconnectTimer = window.setTimeout(connect, 1_000);
                }
            };
            socket.onerror = () => socket?.close();
        };

        connect();
        return () => {
            stopped = true;
            window.clearTimeout(reconnectTimer);
            socket?.close();
        };
    }, [race?.race_id, cars.length]);

    const liveCars = Object.values(telemetry);
    const leader = [...liveCars].sort((left, right) => left.race_position - right.race_position)[0];
    const elapsed = leader?.elapsed_race_seconds ?? 0;
    const currentStatus = race?.status === "running" ? leader?.race_status ?? "running" : race?.status ?? "idle";
    const activeRace = ["queued", "running", "stopping"].includes(currentStatus);
    const statusLabel = { idle: "PRONTA", queued: "AGUARDANDO INÍCIO", running: "CORRIDA", stopping: "PARANDO", stopped: "PARADA", finished: "FINALIZADA", failed: "FALHA" }[currentStatus];
    const selectedTelemetry = selectedCarId ? telemetry[selectedCarId] : undefined;
    const selectedConfiguration = cars.find((car) => car.car_id === selectedCarId);
    const rankedConfigurations = rankCars(cars, telemetry);

    async function controlRace(action: "start" | "stop") {
        setRaceAction(action);
        setError(null);
        try {
            setRace(action === "start" ? await startRace() : await stopRace(race!.race_id));
        } catch {
            setError(action === "start" ? "Não foi possível iniciar a corrida." : "Não foi possível parar a corrida.");
        } finally { setRaceAction(null); }
    }

    async function saveConfiguration(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!draft) return;
        setSaving(true);
        setSaved(false);
        setError(null);
        try {
            const updated = await updateCar(draft);
            setCars((current) =>
                current.map((car) => (car.car_id === updated.car_id ? updated : car)),
            );
            setDraft(updated);
            setSaved(true);
            window.setTimeout(() => setSaved(false), 2_000);
        } catch {
            setError("Não foi possível salvar a configuração do carro.");
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="app-shell">
            <header className="topbar">
                <a className="brand" href="#top" aria-label="RaceStream início">
                    <span className="brand-mark"><Flag size={19} strokeWidth={2.6} /></span>
                    <span className="brand-name">RACESTREAM</span>
                    <span className="brand-divider" />
                    <span className="brand-track">INTERLAGOS</span>
                </a>
                <div className="topbar-meta">
                    <span className={`connection-state ${connection}`}>
                        <Radio size={15} />
                        {connection === "connected" ? "AO VIVO" : connection === "reconnecting" ? "RECONECTANDO" : "CONECTANDO"}
                    </span>
                    <span className="race-id">{race?.race_id ?? "AGUARDANDO CORRIDA"}</span>
                </div>
            </header>

            <main id="top" className="dashboard">
                <section className="race-heading" aria-label="Estado da corrida">
                    <div className="race-title-block">
                        <p className="eyebrow"><span /> SÃO PAULO · BRASIL · 4.309 KM</p>
                        <h1>GRANDE PRÊMIO <span>INTERLAGOS</span></h1>
                    </div>
                    <div className="race-metrics">
                        <div className="race-clock metric-cell">
                            <Timer size={18} />
                            <div><span>TEMPO RESTANTE</span><strong>{formatRaceClock((race?.duration_seconds ?? 120) - elapsed)}</strong></div>
                        </div>
                        <div className="metric-cell">
                            <Flag size={17} />
                            <div><span>VOLTA DO LÍDER</span><strong>{Math.min(leader?.lap ?? 1, race?.target_laps ?? 60).toString().padStart(2, "0")} <small>/ {race?.target_laps ?? 60}</small></strong></div>
                        </div>
                        <div className="metric-cell status-cell">
                            <Activity size={17} />
                            <div><span>STATUS</span><strong>{statusLabel}</strong></div>
                        </div>
                    </div>
                </section>

                <section className="race-controls" aria-label="Controle da corrida">
                    <button id="start-race" disabled={activeRace || raceAction !== null} onClick={() => void controlRace("start")}><Play size={16} />{raceAction === "start" ? "Iniciando..." : "Iniciar corrida"}</button>
                    <button id="stop-race" className="stop-race" disabled={!race || !["queued", "running"].includes(currentStatus) || raceAction !== null} onClick={() => void controlRace("stop")}><Square size={16} />{raceAction === "stop" ? "Parando..." : "Parar corrida"}</button>
                    <span>Parar encerra a prova atual. Iniciar cria uma nova corrida.</span>
                </section>
                {error && <div className="error-banner" role="alert">{error}</div>}

                <div className="dashboard-grid">
                    <section className="track-panel" aria-labelledby="track-heading">
                        <div className="panel-heading track-heading-row">
                            <div>
                                <p className="eyebrow">AUTÓDROMO JOSÉ CARLOS PACE</p>
                                <h2 id="track-heading">MAPA DA CORRIDA</h2>
                            </div>
                            <div className="track-length"><span>4.309</span> KM</div>
                        </div>
                        <div className="track-stage">
                            <InterlagosTrack
                                cars={liveCars}
                                selectedCarId={selectedCarId}
                                onSelectCar={setSelectedCarId}
                            />
                            {liveCars.length === 0 && (
                                <div className="track-waiting"><Activity size={18} /> Aguardando telemetria</div>
                            )}
                        </div>
                        <div className="track-footer">
                            <span><i className="legend-dot leader-dot" /> LÍDER P{leader?.race_position ?? "--"}</span>
                            <span>{liveCars.length.toString().padStart(2, "0")} CARROS</span>
                            <span>SENTIDO ANTI-HORÁRIO</span>
                        </div>
                    </section>

                    <section className="leaderboard-panel" aria-labelledby="leaderboard-heading">
                        <div className="panel-heading">
                            <div>
                                <p className="eyebrow">CLASSIFICAÇÃO</p>
                                <h2 id="leaderboard-heading">PELOTÃO</h2>
                            </div>
                            <span className="field-count">{cars.length.toString().padStart(2, "0")} CARROS</span>
                        </div>
                        <div className="leaderboard-columns"><span>POS</span><span>PILOTO / EQUIPE</span><span>VOLTA</span><span title="Diferença estimada para o líder">DIF. LÍDER*</span></div>
                        <div className="leaderboard-list">
                            {rankedConfigurations.map((car, index) => {
                                const event = telemetry[car.car_id];
                                const position = event?.race_position ?? index + 1;
                                const selected = selectedCarId === car.car_id;
                                return (
                                    <button
                                        className={`leaderboard-row${selected ? " selected" : ""}${position === 1 ? " first-place" : ""}`}
                                        key={car.car_id}
                                        onClick={() => setSelectedCarId(car.car_id)}
                                        type="button"
                                    >
                                        <span className="position-cell">{position === 1 && <Trophy size={12} />}{position.toString().padStart(2, "0")}</span>
                                        <span className="car-identity">
                                            <span className="driver-identity"><span className="country-flag" role="img" aria-label={`País: ${countryName(car.driver_country_code)}`} title={countryName(car.driver_country_code)}>{countryFlag(car.driver_country_code)}</span><strong>{car.driver_name || car.driver_id}</strong></span>
                                            <small>{teamName(car.team_id)} · {car.car_id}</small>
                                        </span>
                                        <span className="lap-cell">{event ? Math.min(event.lap, event.target_laps).toString().padStart(2, "0") : "--"}</span>
                                        <span className="time-cell">{event?.race_position === 1 ? "LÍDER" : formatGap(leaderGapMs(event, leader))}</span>
                                    </button>
                                );
                            })}
                            {cars.length === 0 && <div className="empty-list">CARREGANDO GRID...</div>}
                        </div>
                        <p className="leaderboard-note">* Diferença estimada para o líder. Tempos de volta no painel do carro.</p>
                    </section>

                    <aside className="car-panel" aria-labelledby="car-heading">
                        <div className="panel-heading">
                            <div>
                                <p className="eyebrow">TELEMETRIA · SETUP</p>
                                <h2 id="car-heading">{selectedCarId ?? "SELECIONE UM CARRO"}</h2>
                            </div>
                            <button className="icon-button" type="button" title="Dados do carro" aria-label="Dados do carro">
                                <CircleHelp size={17} />
                            </button>
                        </div>

                        <div className="telemetry-grid">
                            <div className="telemetry-stat speed-stat">
                                <Gauge size={17} />
                                <span>VELOCIDADE</span>
                                <strong>{selectedTelemetry?.speed_kmh.toFixed(0) ?? "---"}<small> km/h</small></strong>
                            </div>
                            <div className="telemetry-stat">
                                <Zap size={17} />
                                <span>MARCHA</span>
                                <strong>{selectedTelemetry?.gear ?? "-"}<small>ª</small></strong>
                            </div>
                            <div className="telemetry-stat">
                                <Timer size={17} />
                                <span>ÚLTIMA VOLTA</span>
                                <strong className="time-value">{formatLapTime(selectedTelemetry?.last_lap_time_ms)}</strong>
                            </div>
                            <div className="telemetry-stat">
                                <Trophy size={17} />
                                <span>MELHOR VOLTA</span>
                                <strong className="time-value">{formatLapTime(selectedTelemetry?.best_lap_time_ms)}</strong>
                            </div>
                        </div>

                        <div className="car-readout">
                            <span><Weight size={15} /> PESO TOTAL</span>
                            <strong>{selectedTelemetry?.car_weight_kg.toFixed(0) ?? "---"} kg</strong>
                            <span className="compound-readout">PNEU <b className={`compound-${selectedTelemetry?.tire_compound ?? selectedConfiguration?.tire_compound ?? "medium"}`}>{tireLabel(selectedTelemetry?.tire_compound ?? selectedConfiguration?.tire_compound ?? "medium")}</b></span>
                        </div>
                        <div className={`driving-phase phase-${selectedTelemetry?.driving_phase ?? "straight"}`}>
                            <Activity size={15} />
                            <span>PILOTAGEM</span>
                            <strong>{selectedTelemetry?.driving_phase === "braking" ? "FREANDO PARA A CURVA" : selectedTelemetry?.driving_phase === "corner" ? "CONTORNANDO A CURVA" : "ACELERANDO NA RETA"}</strong>
                        </div>

                        <p>{selectedConfiguration?.team_id} · Estratégia {selectedConfiguration?.strategy} · {selectedTelemetry?.pit_status === "in_pit" ? "NOS BOXES" : selectedTelemetry?.pit_status === "out_of_fuel" ? "SEM COMBUSTÍVEL" : selectedTelemetry?.pit_status === "tire_burst" ? "PNEU ESTOURADO" : "NA PISTA"}</p>
                        <p>Pressão {selectedTelemetry?.tire_pressure_psi?.toFixed(1) ?? "38.0"} psi · Paradas {selectedTelemetry?.pit_stops ?? 0}</p>
                        <form className="setup-form" onSubmit={saveConfiguration}>
                            <div className="setup-title">
                                <span><Settings2 size={16} /> CONFIGURAÇÃO</span>
                                <span className="next-race-label">PRÓXIMA CORRIDA</span>
                            </div>
                            <label className="field-label" htmlFor="driver-name">NOME DO PILOTO</label>
                            <input id="driver-name" value={draft?.driver_name ?? ""} maxLength={100} onChange={(event) => setDraft((current) => current ? { ...current, driver_name: event.target.value } : current)} required />
                            <div className="form-row">
                                <label className="field-label" htmlFor="driver-country">PAÍS DO PILOTO</label>
                                <select id="driver-country" value={draft?.driver_country_code ?? ""} onChange={(event) => setDraft((current) => current ? { ...current, driver_country_code: event.target.value } : current)}>
                                    <option value="">Não informado</option>
                                    {Array.from(new Set([...cars.map((car) => car.driver_country_code), draft?.driver_country_code ?? "", "BR", "AR", "PT", "GB", "IT", "ES", "FR", "DE", "JP", "CA"])).filter(Boolean).sort((left, right) => countryName(left).localeCompare(countryName(right), "pt-BR")).map((code) => <option key={code} value={code}>{countryName(code)}</option>)}
                                </select>
                            </div>
                            <label className="field-label" htmlFor="driver-id">IDENTIFICADOR DO PILOTO</label>
                            <input
                                id="driver-id"
                                value={draft?.driver_id ?? ""}
                                onChange={(event) => setDraft((current) => current ? { ...current, driver_id: event.target.value } : current)}
                                required
                            />
                            <div className="form-row">
                                <label className="field-label" htmlFor="car-weight">PESO DO CARRO <small>kg</small></label>
                                <input id="car-weight" type="number" min="450" max="1000" step="1" value={draft?.car_weight_kg ?? ""} onChange={(event) => setDraft((current) => current ? { ...current, car_weight_kg: Number(event.target.value) } : current)} />
                            </div>
                            <div className="form-row">
                                <label className="field-label" htmlFor="driver-weight">PESO DO PILOTO <small>kg</small></label>
                                <input id="driver-weight" type="number" min="45" max="150" step="1" value={draft?.driver_weight_kg ?? ""} onChange={(event) => setDraft((current) => current ? { ...current, driver_weight_kg: Number(event.target.value) } : current)} />
                            </div>
                            <div className="form-row">
                                <label className="field-label" htmlFor="top-speed">VELOCIDADE FINAL <small>km/h</small></label>
                                <input id="top-speed" type="number" min="250" max="380" step="1" value={draft?.top_speed_kmh ?? ""} onChange={(event) => setDraft((current) => current ? { ...current, top_speed_kmh: Number(event.target.value) } : current)} />
                            </div>
                            <div className="form-row">
                                <label className="field-label" htmlFor="strategy">ESTRATÉGIA</label>
                                <select id="strategy" value={draft?.strategy ?? "A"} onChange={(event) => setDraft((current) => current ? { ...current, strategy: event.target.value as CarConfiguration["strategy"] } : current)}>
                                    <option value="A">A · tanque cheio</option>
                                    <option value="B">B · parada a 10%</option>
                                    <option value="C">C · parada a 20%</option>
                                </select>
                            </div>
                            <fieldset className="tire-selector">
                                <legend>COMPOSTO DE PNEU</legend>
                                {(["soft", "medium", "hard"] as const).map((compound) => (
                                    <label className={`tire-option tire-${compound}${draft?.tire_compound === compound ? " active" : ""}`} key={compound}>
                                        <input type="radio" name="tire" value={compound} checked={draft?.tire_compound === compound} onChange={() => setDraft((current) => current ? { ...current, tire_compound: compound } : current)} />
                                        <span>{tireLabel(compound)}</span>
                                        <small>{compound === "soft" ? "−250 ms" : compound === "hard" ? "+300 ms" : "BASE"}</small>
                                    </label>
                                ))}
                            </fieldset>
                            <button className="save-button" type="submit" disabled={!draft || saving}>
                                {saved ? <Check size={16} /> : <Save size={16} />}
                                {saving ? "SALVANDO" : saved ? "SALVO" : "SALVAR SETUP"}
                                <ChevronRight size={16} />
                            </button>
                        </form>
                    </aside>
                </div>

                <footer className="dashboard-footer">
                    <span>RACESTREAM LAB <b>·</b> SIMULAÇÃO 60 VOLTAS</span>
                    <span><CircleHelp size={13} /> TEMPOS DE PNEU: MACIO −250 ms · MÉDIO BASE · DURO +300 ms</span>
                </footer>
            </main>
        </div>
    );
}