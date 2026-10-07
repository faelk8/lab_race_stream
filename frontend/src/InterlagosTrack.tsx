import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { RaceTelemetry, TrackDefinition } from "./types";

const trackPath =
    "M 191.75,559.61218 C 212.75,558.11218 211,565.11218 211,565.11218 C 214,585.11218 229.26932,624.26544 271.75,627.36218 C 287.89429,628.74606 304.23625,617.35494 318.31469,610.32998 C 332.09391,603.45433 442.25826,548.61643 464.21744,537.2039 C 483.14534,527.36677 507.50123,515.62839 510.70711,508.71573 C 518.98528,489.2222 490.6857,448.80491 480.31066,443.1854 C 462.17005,429.14467 430.40488,438.56386 400.08112,442.11824 C 382.75736,444.17262 331.0233,445.68655 319,444.36218 C 296.75,436.86218 296.5,405.86813 296.5,400.61218 C 296.5,395.36218 336.74457,350.80974 342.25,350.86218 C 354.38058,350.86218 346.30953,378.36773 357.27903,389.46009 C 367.08348,399.65974 380.25,386.11218 380.25,386.11218 C 391.5,375.11218 389.25,375.36218 388.5,340.11218 C 389.5,334.23718 403.5,314.98718 407.1875,309.61218 C 414.625,298.98718 419.78475,295.64693 425.5,301.36218 C 428.75,306.73718 424.30534,352.4349 425.25,358.64343 C 426.375,378.54968 447.44864,388.85191 456.25,390.61218 C 470,391.86218 522.3125,382.04968 522.3125,382.04968 C 538.5625,379.23718 540.625,371.98718 542,368.61218 C 544.50816,360.13932 528,326.36218 528,326.36218 C 511,307.86218 480.5625,291.73718 462.09375,282.89343 C 452.375,277.79968 428.80696,278.02338 423,279.11218 C 418.75758,279.90763 319.5,332.11218 304.75,343.36218 L 191.625,505.86218 C 181.75,518.36218 170.59375,542.48718 175.40625,553.48718 C 181.21875,561.48718 191.75,559.61218 191.75,559.61218 z";

const carColors = [
    "#ff4b36",
    "#f0c23b",
    "#23b8a6",
    "#64a7ff",
    "#ff77a8",
    "#b3dc4d",
    "#a78bfa",
    "#ff934f",
    "#4ed3d0",
    "#d6e25e",
    "#fc6582",
    "#70c987",
    "#da9dff",
    "#ffbf69",
    "#8fb7ff",
    "#e9ebef",
    "#4bc0eb",
    "#d5aa44",
    "#9fda9f",
    "#f18e72",
];

interface InterlagosTrackProps {
    cars: RaceTelemetry[];
    selectedCarId: string | null;
    onSelectCar: (carId: string) => void;
    highlightedCarIds?: string[];
    trackDefinition?: TrackDefinition | null;
}

export function InterlagosTrack({
    cars,
    selectedCarId,
    onSelectCar,
    highlightedCarIds = [],
    trackDefinition,
}: InterlagosTrackProps) {
    const [displayCars, setDisplayCars] = useState(cars);
    const displayed = useRef(cars);
    const [defaultTrack, setTrack] = useState<TrackDefinition | null>(null);
    const track = trackDefinition ?? defaultTrack;
    useEffect(() => {
        const controller = new AbortController();
        fetch(`${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}/api/tracks/interlagos`, { signal: controller.signal })
            .then(response => { if (!response.ok) throw new Error(); return response.json(); })
            .then(setTrack).catch(() => setTrack(null));
        return () => controller.abort();
    }, []);
    const frameKey = cars.map(car => car.event_id).join(":");
    useEffect(() => {
        const previous = new Map(displayed.current.map(car => [car.car_id, car]));
        const started = performance.now();
        let animation = 0;
        const render = () => {
            const fraction = Math.min(1, (performance.now() - started) / 1000);
            const next = cars.map(car => {
                const old = previous.get(car.car_id);
                if (!old || car.race_status === "stopped" || car.distance_m == null || old.distance_m == null) return car;
                const distance = old.distance_m + (car.distance_m - old.distance_m) * fraction;
                return { ...car, distance_m: distance, track_progress: ((distance / (track?.length_m ?? 4309)) % 1 + 1) % 1 };
            });
            displayed.current = next;
            setDisplayCars(next);
            if (fraction < 1) animation = requestAnimationFrame(render);
        };
        animation = requestAnimationFrame(render);
        return () => cancelAnimationFrame(animation);
    }, [frameKey, track?.length_m]);
    const pathRef = useRef<SVGPathElement>(null);
    const [pathLength, setPathLength] = useState(0);
    useLayoutEffect(() => {
        setPathLength(pathRef.current?.getTotalLength() ?? 0);
    }, []);
    const anchors = pathLength > 0 ? displayCars.map((car) => {
        const distance = ((car.track_progress + (track?.map_start_offset ?? 0)) % 1) * pathLength;
        const point = pathRef.current!.getPointAtLength(distance);
        const ahead = pathRef.current!.getPointAtLength(Math.min(distance + 1, pathLength));
        const tangentLength = Math.hypot(ahead.x - point.x, ahead.y - point.y) || 1;
        const laneOffset = car.pit_status === "pit_lane" || car.pit_status === "in_pit" ? -10 : (car.overtaking_lane ?? 0) * 6;
        return { carId: car.car_id, x: point.x - (ahead.y - point.y) / tangentLength * laneOffset,
            y: point.y + (ahead.x - point.x) / tangentLength * laneOffset };
    }) : [];

    return (
        <svg
            className="interlagos-svg"
            viewBox="0 0 470 490"
            role="img"
            aria-label="Mapa do Autódromo de Interlagos com posição dos carros"
        >
            <image
                className="track-reference"
                href="/interlagos.svg"
                width="470"
                height="490"
                preserveAspectRatio="xMidYMid meet"
            />
            <g transform="translate(-136.686 -208.815)">
                <path ref={pathRef} d={trackPath} className="track-racing-line" />
                {pathLength > 0 && track && [...track.checkpoints.map((p, i) => ({ progress: p, label: `P${i+1}` })), ...track.sector_ends.map((p, i) => ({ progress: p, label: i === 2 ? "SF" : `S${i+1}` }))].map(line => {
                    const point = pathRef.current!.getPointAtLength(((line.progress + track.map_start_offset) % 1) * pathLength);
                    return <g key={line.label}><circle cx={point.x} cy={point.y} r={line.label.startsWith("S") ? 4 : 2} fill="#6f849f"><title>{line.label} · ponto simulado</title></circle></g>;
                })}
                {pathLength > 0 &&
                    displayCars.map((car, index) => {
                        const { x, y } = anchors[index];
                        const selected = car.car_id === selectedCarId || highlightedCarIds.includes(car.car_id);

                        return (
                            <g
                                key={car.car_id}
                                className={`track-car phase-${car.driving_phase}${selected ? " is-selected" : ""}`}
                                transform={`translate(${x} ${y})`}
                                onClick={() => onSelectCar(car.car_id)}
                                role="button"
                                tabIndex={0}
                                aria-label={`Carro ${car.car_id}, posição ${car.race_position}`}
                                onKeyDown={(event) => {
                                    if (event.key === "Enter" || event.key === " ") {
                                        onSelectCar(car.car_id);
                                    }
                                }}
                            >
                                <circle r={selected ? 4.5 : 3.5} className="car-marker-halo" />
                                <circle
                                    r={selected ? 3 : 2.5}
                                    fill={carColors[(Number(car.car_id.match(/\d+$/)?.[0] ?? index + 1) - 1) % carColors.length]}
                                    className="car-marker"
                                />
                                <title>{`${car.car_id} · P${car.race_position}`}</title>
                            </g>
                        );
                    })}
            </g>
            <text x="18" y="28" className="track-map-label">
                INTERLAGOS
            </text>
            <text x="18" y="45" className="track-map-subtitle">
                4.309 KM · SENTIDO ANTI-HORÁRIO
            </text>
        </svg>
    );
}
