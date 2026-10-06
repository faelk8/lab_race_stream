import type { TrackDefinition } from "./types";
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
import { startTransition, useDeferredValue, useEffect, useRef, useState } from "react";
import { getCars, getLatestRace, startRace, stopRace, telemetrySocketUrl, updateCar } from "./api";
import { RaceInsights } from "./RaceInsights";
import { InterlagosTrack } from "./InterlagosTrack";
import { countryFlag, countryName, rankCars, teamName } from "./racePresentation";
import type { AnalyticsEvent, CarAnalytics, CarConfiguration, RaceIncident, RaceSnapshot, RaceStartConfiguration, RaceStateEvent, RaceTelemetry, TireCompound } from "./types";

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
    return { soft: "MACIO", medium: "MÉDIO", hard: "DURO", wet: "CHUVA" }[compound];
}

export function App() {
    const [cars, setCars] = useState<CarConfiguration[]>([]);
    const [analytics, setAnalytics] = useState<Record<string, CarAnalytics>>({});
    const [sessionCars, setSessionCars] = useState<CarConfiguration[]>([]);
    const [sessionTrack, setSessionTrack] = useState<TrackDefinition | null>(null);
    const [selectionMode, setSelectionMode] = useState<"car" | "driver" | "team">("car");
    const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
    const [staleCars, setStaleCars] = useState<string[]>([]);
    const [lastUpdate, setLastUpdate] = useState(0);
    const [now, setNow] = useState(Date.now());
    useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
    const [race, setRace] = useState<RaceSnapshot | null>(null);
    const [telemetryByCar, setTelemetryByCar] = useState<Record<string, RaceTelemetry>>({});
    const [selectedCarId, setSelectedCarId] = useState<string | null>(null);
    const [draft, setDraft] = useState<CarConfiguration | null>(null);
    const [connection, setConnection] = useState<ConnectionState>("connecting");
    const [raceAction, setRaceAction] = useState<"start" | "stop" | null>(null);
    const raceActionLock = useRef(false);
    const [raceSetup, setRaceSetup] = useState<RaceStartConfiguration>({ rain_enabled: false, rain_start_lap: 1, rain_intensity: 0.5, incidents: [] });
    const [incidentType, setIncidentType] = useState<RaceIncident["incident_type"]>("tire_puncture");
    const [incidentLap, setIncidentLap] = useState(5);
    const [incidentCar, setIncidentCar] = useState("CAR-01");
    const [incidentSecondCar, setIncidentSecondCar] = useState("CAR-02");
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
        let stateSequence = -1;
        let analysisRevision = -1;
        setAnalytics({});
        setSessionCars([]);
        setSessionTrack(null);
        setStaleCars([]);
        setLastUpdate(0);
        const receiveState = (event: RaceStateEvent) => {
            if (event.state_sequence <= stateSequence) return;
            stateSequence = event.state_sequence;
            const frame = Object.fromEntries(event.cars.map(car => [car.telemetry.car_id, car.telemetry]));
            setStaleCars(event.cars.filter(car => car.stale).map(car => car.telemetry.car_id));
            setLastUpdate(Date.parse(event.produced_at));
            startTransition(() => setTelemetryByCar(frame));
        };
        const receiveAnalytics = (event: AnalyticsEvent) => {
            if (event.revision <= analysisRevision) return;
            analysisRevision = event.revision;
            setAnalytics(Object.fromEntries(event.cars.map(car => [car.car_id, car])));
        };
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
                const event = JSON.parse(message.data);
                if (event.race_id !== race.race_id) return;
                if (event.kind === "snapshot") {
                    if (event.participants?.length) setSessionCars(event.participants);
                    if (event.control?.track) setSessionTrack(event.control.track);
                    if (event.state) receiveState(event.state);
                    if (event.analytics) receiveAnalytics(event.analytics);
                } else if (event.kind === "state") receiveState(event);
                else if (event.kind === "analytics") receiveAnalytics(event);
                else if (event.kind === "control") {
                    if (event.participants?.length) setSessionCars(event.participants);
                    if (event.track) setSessionTrack(event.track);
                }
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
    const participants = sessionCars.length ? sessionCars : cars;
    const rankedConfigurations = rankCars(participants, telemetry);

    async function controlRace(action: "start" | "stop") {
        if (raceActionLock.current) return;
        raceActionLock.current = true;
        setRaceAction(action);
        setError(null);
        try {
            setRace(action === "start" ? await startRace(raceSetup) : await stopRace(race!.race_id));
        } catch (reason) {
            const fallback = action === "start" ? "Não foi possível iniciar a corrida." : "Não foi possível parar a corrida.";
            const detail = reason instanceof Error && !(reason instanceof TypeError) ? reason.message : "";
            setError(detail || fallback);
        } finally { raceActionLock.current = false; setRaceAction(null); }
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
                    <a className="console-link" href={import.meta.env.VITE_KAFKA_CONSOLE_URL ?? "http://localhost:8080"} target="_blank" rel="noreferrer">VER KAFKA ↗</a>
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
                            <div><span>TEMPO DA CORRIDA</span><strong>{formatRaceClock(elapsed)}</strong></div>
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
                {activeRace && race && <p className="race-conditions" aria-live="polite">
                    Condições atuais: {race.rain_enabled ? `chuva ${race.rain_intensity >= 0.75 ? "forte" : race.rain_intensity <= 0.25 ? "leve" : "moderada"} a partir da volta ${race.rain_start_lap}` : "pista seca"} · {race.incidents.length} incidente(s) programado(s)
                </p>}
                {!activeRace && <section className="race-scenario-panel" aria-label="Configuração de clima e incidentes">
                    <div className="scenario-heading"><div><p className="eyebrow">PRÓXIMA LARGADA</p><h2>CONFIGURAR A CORRIDA</h2></div><span>A chuva reduz velocidade e aderência. Todos os carros fazem uma parada individual, espaçada por 2 a 6 voltas, para pneus e combustível.</span></div>
                    <div className="scenario-weather">
                        <label className="scenario-toggle"><input type="checkbox" checked={raceSetup.rain_enabled} onChange={(event) => setRaceSetup((current) => ({ ...current, rain_enabled: event.target.checked }))} /> Chuva durante a prova</label>
                        {raceSetup.rain_enabled && <>
                            <label>Começa na volta <input type="number" min="1" max={Math.max(1, (race?.target_laps ?? 60) - 1 - 2 * (cars.length - 1))} value={raceSetup.rain_start_lap} onChange={(event) => setRaceSetup((current) => ({ ...current, rain_start_lap: Number(event.target.value) }))} /></label>
                            <label>Intensidade <select value={raceSetup.rain_intensity} onChange={(event) => setRaceSetup((current) => ({ ...current, rain_intensity: Number(event.target.value) }))}><option value="0.25">Leve</option><option value="0.5">Moderada</option><option value="1">Forte</option></select></label>
                            <small>Para {cars.length} carros e {race?.target_laps ?? 60} voltas, inicie até a volta {Math.max(1, (race?.target_laps ?? 60) - 1 - 2 * (cars.length - 1))}.</small>
                        </>}
                    </div>
                    <form className="scenario-form" onSubmit={(event) => { event.preventDefault(); const scenario: RaceIncident = { incident_type: incidentType, lap: incidentLap, car_id: incidentCar, second_car_id: incidentType === "collision" ? incidentSecondCar : "" }; setRaceSetup((current) => ({ ...current, incidents: [...current.incidents, scenario] })); }}>
                        <label>Evento <select value={incidentType} onChange={(event) => setIncidentType(event.target.value as RaceIncident["incident_type"])}><option value="tire_puncture">Furo de pneu · parada emergencial</option><option value="collision">Colisão · abandono dos envolvidos</option></select></label>
                        <label>Volta <input type="number" min="1" max={race?.target_laps ?? 60} value={incidentLap} onChange={(event) => setIncidentLap(Number(event.target.value))} required /></label>
                        <label>Carro {incidentType === "collision" ? "1" : "afetado"}<select value={incidentCar} onChange={(event) => setIncidentCar(event.target.value)}>{cars.map((car) => <option key={car.car_id} value={car.car_id}>{car.car_id} · {car.driver_name}</option>)}</select></label>
                        {incidentType === "collision" && <label>Carro 2<select value={incidentSecondCar} onChange={(event) => setIncidentSecondCar(event.target.value)}>{cars.filter((car) => car.car_id !== incidentCar).map((car) => <option key={car.car_id} value={car.car_id}>{car.car_id} · {car.driver_name}</option>)}</select></label>}
                        <button type="submit" disabled={!cars.length}>Adicionar evento</button>
                    </form>
                    {raceSetup.incidents.length > 0 && <ul className="scenario-list">{raceSetup.incidents.map((scenario, index) => <li key={`${scenario.incident_type}-${scenario.lap}-${scenario.car_id}-${index}`}><span>Volta {scenario.lap} · {scenario.incident_type === "collision" ? `Colisão ${scenario.car_id} / ${scenario.second_car_id}` : `Furo em ${scenario.car_id}`}</span><button type="button" aria-label="Remover evento" onClick={() => setRaceSetup((current) => ({ ...current, incidents: current.incidents.filter((_, itemIndex) => itemIndex !== index) }))}>Remover</button></li>)}</ul>}
                </section>}
                <section className="race-follow" aria-label="Selecionar acompanhamento">
                    <label>Acompanhar por <select value={selectionMode} onChange={e => { setSelectionMode(e.target.value as typeof selectionMode); setSelectedTeam(null); }}><option value="car">Carro</option><option value="driver">Piloto</option><option value="team">Equipe</option></select></label>
                    {selectionMode === "team" ? <select aria-label="Equipe acompanhada" value={selectedTeam ?? ""} onChange={e => { setSelectedTeam(e.target.value); setSelectedCarId(participants.find(c => c.team_id === e.target.value)?.car_id ?? null); }}><option value="">Selecione a equipe</option>{[...new Set(participants.map(c => c.team_id))].map(id => <option key={id} value={id}>{teamName(id)}</option>)}</select> : <select aria-label="Participante acompanhado" value={selectedCarId ?? ""} onChange={e => setSelectedCarId(e.target.value)}>{participants.map(c => <option key={c.car_id} value={c.car_id}>{selectionMode === "driver" ? c.driver_name : c.car_id} · {teamName(c.team_id)}</option>)}</select>}
                    <span>{lastUpdate ? `Quadro produzido há ${Math.max(0, Math.floor((now - lastUpdate) / 1000))} s` : "Aguardando quadro da corrida"}{activeRace && lastUpdate > 0 && now - lastUpdate > 3000 ? " · TELEMETRIA ATRASADA" : ""}{staleCars.length ? ` · ${staleCars.length} carro(s) com dados antigos` : ""}</span>
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
                                trackDefinition={sessionTrack}
                                highlightedCarIds={selectionMode === "team" ? participants.filter(c => c.team_id === selectedTeam).map(c => c.car_id) : []}
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
                        <div className="leaderboard-columns"><span>POS</span><span>PILOTO / EQUIPE</span><span>VOLTA</span><span>ÚLTIMA VOLTA</span></div>
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
                                            <span className="driver-identity"><span className="country-flag" role="img" aria-label={`País: ${countryName(car.driver_country_code)}`} title={countryName(car.driver_country_code)}>{countryFlag(car.driver_country_code)}</span><strong>{event?.driver_name || car.driver_name || car.driver_id}</strong></span>
                                            <small>{teamName(car.team_id)} · {car.car_id}</small>
                                        </span>
                                        <span className="lap-cell" title="Volta atual sobre total de voltas">{event ? `${Math.min(event.lap, event.target_laps)}/${event.target_laps}` : `--/${race?.target_laps ?? 60}`}</span>
                                        <span className="last-lap-cell" title="Última volta concluída">{formatLapTime(event?.last_lap_time_ms ?? analytics[car.car_id]?.last_lap_time_ms)}</span>
                                    </button>
                                );
                            })}
                            {cars.length === 0 && <div className="empty-list">CARREGANDO GRID...</div>}
                        </div>
                        <p className="leaderboard-note">Diferença medida na última passagem comum. “—” indica referência ainda indisponível.</p>
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
                                {(["soft", "medium", "hard", "wet"] as const).map((compound) => (
                                    <label className={`tire-option tire-${compound}${draft?.tire_compound === compound ? " active" : ""}`} key={compound}>
                                        <input type="radio" name="tire" value={compound} checked={draft?.tire_compound === compound} onChange={() => setDraft((current) => current ? { ...current, tire_compound: compound } : current)} />
                                        <span>{tireLabel(compound)}</span>
                                        <small>{compound === "soft" ? "ADERÊNCIA +1%" : compound === "hard" ? "ADERÊNCIA −1%" : compound === "wet" ? "PISTA MOLHADA" : "BASE"}</small>
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
                    <span><CircleHelp size={13} /> COMPOSTO E PRESSÃO DISPONÍVEIS NA TELEMETRIA</span>
                </footer>
                <RaceInsights trackDefinition={sessionTrack} raceId={race?.race_id} selectedCarId={selectedCarId} selectedTeam={selectionMode === "team" ? selectedTeam : null} cars={participants} telemetry={telemetry} analytics={analytics} />
            </main>
        </div>
    );
}
