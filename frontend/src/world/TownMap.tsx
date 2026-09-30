import { usePageVisible } from "../hooks/usePageVisible";
import {
  memo,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import "./sketch.css";
import { MansionGate } from "./MansionGate";

import type { ConstructionProject, Entity, Place, Train, World } from "../api/world";
import {
  activityKind,
  activityLabels,
  appearanceFor,
  type ActivityKind,
  type Appearance,
} from "./personVisuals";

type Props = {
  zoom?: number;
  onCameraChange?: (camera: { zoom: number; position: { x: number; y: number } }) => void;
  position?: { x: number; y: number };
  onPositionChange?: (position: { x: number; y: number }) => void;
  world: World;
  selectedId: string | null;
  onSelect: (entity: Entity | Place) => void;
};

function activate(event: KeyboardEvent<SVGGElement>, action: () => void) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}

export function TownMap({
  world,
  selectedId,
  onSelect,
  zoom = 1,
  position,
  onPositionChange,
  onCameraChange,
}: Props) {
  const pageVisible = usePageVisible();
  const svgRef = useRef<SVGSVGElement>(null);
  const [viewport, setViewport] = useState<{ width: number; height: number } | null>(null);
  const [localPan, setPan] = useState({ x: 0, y: 0 });
  const pan = position ?? localPan;
  const drag = useRef<{ x: number; y: number; panX: number; panY: number; moved: boolean } | null>(
    null,
  );
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width && entry.contentRect.height)
        setViewport({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(svg);
    return () => observer.disconnect();
  }, []);
  const mapSize = world.map_size ?? {
    width: 1200,
    height: Math.max(
      720,
      ...(world.trains?.flatMap((train) => train.track?.map((point) => point.y + 80) ?? []) ?? []),
    ),
  };
  const grassMargin = 100;
  const framedSize = { width: mapSize.width, height: mapSize.height + grassMargin * 2 };
  const viewportSize = viewport ?? framedSize;
  const scale =
    Math.min(viewportSize.width / framedSize.width, viewportSize.height / framedSize.height) * zoom;
  const cameraWidth = viewportSize.width / scale;
  const cameraHeight = viewportSize.height / scale;
  const limitX = Math.max(0, (mapSize.width - cameraWidth) / 2);
  const limitY = Math.max(0, (framedSize.height - cameraHeight) / 2);
  const panX = Math.max(-limitX, Math.min(limitX, pan.x));
  const panY = Math.max(-limitY, Math.min(limitY, pan.y));
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      const deltaUnit =
        event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewportSize.height : 1;
      const dx = event.deltaX * deltaUnit;
      const dy = event.deltaY * deltaUnit;
      if (event.ctrlKey) {
        if (!onCameraChange) return;
        const nextZoom = Math.max(1, Math.min(4, zoom * Math.exp(-dy * 0.01)));
        const nextScale = (scale * nextZoom) / zoom;
        const rect = svg.getBoundingClientRect();
        const offsetX = event.clientX - rect.left - rect.width / 2;
        const offsetY = event.clientY - rect.top - rect.height / 2;
        const nextLimitX = Math.max(0, (mapSize.width - viewportSize.width / nextScale) / 2);
        const nextLimitY = Math.max(0, (framedSize.height - viewportSize.height / nextScale) / 2);
        onCameraChange({
          zoom: nextZoom,
          position: {
            x: Math.max(
              -nextLimitX,
              Math.min(nextLimitX, panX + offsetX / scale - offsetX / nextScale),
            ),
            y: Math.max(
              -nextLimitY,
              Math.min(nextLimitY, panY + offsetY / scale - offsetY / nextScale),
            ),
          },
        });
      } else {
        const nextPosition = {
          x: Math.max(-limitX, Math.min(limitX, panX + dx / scale)),
          y: Math.max(-limitY, Math.min(limitY, panY + dy / scale)),
        };
        if (onPositionChange) onPositionChange(nextPosition);
        else setPan(nextPosition);
      }
    };
    // A native non-passive listener keeps touchpad gestures on the map.
    svg.addEventListener("wheel", handleWheel, { passive: false });
    return () => svg.removeEventListener("wheel", handleWheel);
  }, [
    zoom,
    scale,
    panX,
    panY,
    limitX,
    limitY,
    mapSize.width,
    framedSize.height,
    viewportSize.width,
    viewportSize.height,
    onPositionChange,
    onCameraChange,
  ]);
  const peopleById = useMemo(
    () => new Map(world.people.map((person) => [person.id, person])),
    [world.people],
  );
  const activeHomes = useMemo(
    () =>
      new Set(
        world.people
          .filter(
            (person) =>
              !person.direct_walk &&
              !person.route &&
              !person.in_vehicle_id &&
              !person.on_train &&
              !person.activity?.startsWith("Sleeping"),
          )
          .map((person) => person.target_place_id),
      ),
    [world.people],
  );
  const projectsById = useMemo(
    () => new Map(world.construction_projects?.map((project) => [project.id, project])),
    [world.construction_projects],
  );
  const cameraLeft = (mapSize.width - cameraWidth) / 2 + panX;
  const cameraTop = (mapSize.height - cameraHeight) / 2 + panY;
  const selected = world.people.find((person) => person.id === selectedId);
  const trainPassengers = world.people.filter((person) => person.on_train);
  const riverX = mapSize.width - 40;
  const riverPath = `M${riverX} -40 ${Array.from(
    { length: Math.ceil((mapSize.height + 80) / 320) },
    (_, index) => {
      const bend = index % 2 === 0 ? -1 : 1;
      return `c${bend * 44} 105 ${bend * 44} 215 0 320`;
    },
  ).join(" ")}`;
  return (
    <svg
      aria-label="SmallFolks town map"
      className={`town-map ${world.simulation.running && pageVisible ? "" : "is-paused"} ${scale < 0.65 ? "is-overview" : ""} ${world.people.length > 150 ? "is-dense" : ""}`}
      ref={svgRef}
      viewBox={`${(mapSize.width - cameraWidth) / 2 + panX} ${(mapSize.height - cameraHeight) / 2 + panY} ${cameraWidth} ${cameraHeight}`}
      onPointerDown={(event) => {
        if (event.button !== 0 || !event.isPrimary) return;
        drag.current = { x: event.clientX, y: event.clientY, panX, panY, moved: false };
      }}
      onPointerMove={(event) => {
        const start = drag.current;
        if (!start) return;
        const dx = event.clientX - start.x;
        const dy = event.clientY - start.y;
        if (!start.moved && Math.hypot(dx, dy) < 5) return;
        start.moved = true;
        event.currentTarget.setPointerCapture(event.pointerId);
        const nextPosition = {
          x: Math.max(-limitX, Math.min(limitX, start.panX - dx / scale)),
          y: Math.max(-limitY, Math.min(limitY, start.panY - dy / scale)),
        };
        if (onPositionChange) onPositionChange(nextPosition);
        else setPan(nextPosition);
      }}
      onPointerUp={(event) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId))
          event.currentTarget.releasePointerCapture(event.pointerId);
        if (drag.current && !drag.current.moved) drag.current = null;
      }}
      onPointerCancel={() => {
        drag.current = null;
      }}
      onClickCapture={(event) => {
        if (drag.current?.moved) {
          event.preventDefault();
          event.stopPropagation();
        }
        drag.current = null;
      }}
    >
      <defs>
        <linearGradient id="river-water" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#65aebc" />
          <stop offset="45%" stopColor="#8ad4de" />
          <stop offset="100%" stopColor="#50a3b6" />
        </linearGradient>
        <pattern id="grass-ink" width="46" height="38" patternUnits="userSpaceOnUse">
          <path
            d="m8 12 2-4 2 4m22 18 2-4 2 3"
            fill="none"
            stroke="#7d9b70"
            strokeWidth=".8"
            opacity=".3"
          />
          <circle cx="26" cy="9" r=".9" fill="#819b69" opacity=".4" />
        </pattern>
        <pattern
          id="field-lines"
          width="12"
          height="12"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(-24)"
        >
          <rect width="12" height="12" fill="#e9d08b" />
          <path d="M2 0v12" stroke="#b7a36c" strokeWidth="1.5" opacity=".5" />
        </pattern>
      </defs>
      <rect
        className="map-ground"
        x={-mapSize.width}
        y={-grassMargin}
        height={framedSize.height}
        width={mapSize.width * 3}
      />
      <rect
        x={-mapSize.width}
        y={-grassMargin}
        width={mapSize.width * 3}
        height={framedSize.height}
        fill="url(#grass-ink)"
        pointerEvents="none"
      />
      <g className="river-water" aria-hidden="true" pointerEvents="none">
        <path className="river-bank" d={riverPath} />
        <path className="river" d={riverPath} />
        <path
          className="river-ripples river-current-left"
          d={riverPath}
          transform="translate(-10 0)"
        />
        <path className="river-ripples" d={riverPath} />
        <path
          className="river-ripples river-current-right"
          d={riverPath}
          transform="translate(10 0)"
        />
      </g>
      <g className="sun-doodle" transform="translate(1170 64)" aria-hidden="true">
        <circle r="17" />
        <path d="M0-29v6m0 46v6M-29 0h6m46 0h6M-20-20l4 4m32 32 4 4M20-20l-4 4m-32 32-4 4" />
      </g>
      <g className="fields">
        <path d="M38 610h285v76H38z" />
        <path d="M900 625h190v60H900z" />
      </g>
      {world.roads.map((road) => (
        <g key={road.id}>
          <polyline
            className={road.id.startsWith("road:access-") ? "road road-access" : "road"}
            points={road.points.map((point) => point.join(",")).join(" ")}
          />
          {!road.id.startsWith("road:access-") && (
            <polyline
              className="road-marking"
              points={road.points.map((point) => point.join(",")).join(" ")}
            />
          )}
        </g>
      ))}
      <g className="sidewalks">
        {world.paths.map((path) => (
          <polyline
            className="path"
            key={path.id}
            points={path.points.map((point) => point.join(",")).join(" ")}
          />
        ))}
      </g>
      <g className="crosswalk">
        <path d="M340 330v40m8-40v40m8-40v40m8-40v40m8-40v40m8-40v40M830 330v40m8-40v40m8-40v40m8-40v40m8-40v40" />
      </g>
      <TrainLoop
        onSelect={onSelect}
        passengers={trainPassengers}
        people={world.people}
        queues={world.station_queues ?? []}
        seed={world.seed}
        train={world.trains?.[0]}
      />
      {selected?.route ? (
        <polyline
          className="active-route"
          points={selected.route.map((point) => `${point.x},${point.y}`).join(" ")}
        />
      ) : null}
      {world.places.map((place) => (
        <Building
          world={world}
          key={place.id}
          onSelect={onSelect}
          place={place}
          selected={place.id === selectedId}
          smokeActive={
            place.kind === "home"
              ? activeHomes.has(place.id)
              : place.operating_state?.is_open === true
          }
          project={projectsById.get(place.construction_project_id ?? "")}
        />
      ))}
      <TownTrees plantedTrees={world.planted_trees} />
      <TownDetails />
      {(() => {
        const visible = [
          ...world.people.filter((person) => !person.on_train && !person.in_vehicle_id),
          ...world.pets,
          ...world.vehicles,
        ].sort((a, b) => a.position.y - b.position.y);
        const seen = new Map<string, number>();
        const counts = new Map<string, number>();
        for (const entity of visible) {
          const key = `${entity.position.x},${entity.position.y}`;
          counts.set(key, (counts.get(key) ?? 0) + 1);
        }
        return visible.map((entity) => {
          const key = `${entity.position.x},${entity.position.y}`;
          const index = seen.get(key) ?? 0;
          seen.set(key, index + 1);
          const count = counts.get(key) ?? 1;
          const offsetX = (index - (count - 1) / 2) * 26;
          const offsetY = index % 2 ? 5 : -5;
          // Keep an overscan margin for props, badges and movement at the viewport edge.
          const x = entity.position.x + offsetX;
          const y = entity.position.y + offsetY;
          if (
            x < cameraLeft - 100 ||
            x > cameraLeft + cameraWidth + 100 ||
            y < cameraTop - 100 ||
            y > cameraTop + cameraHeight + 100
          )
            return null;
          return (
            <EntitySprite
              entity={entity}
              driver={
                entity.kind === "vehicle" ? peopleById.get(entity.driver_id ?? "") : undefined
              }
              driverSelected={entity.kind === "vehicle" && entity.driver_id === selectedId}
              key={entity.id}
              onSelect={onSelect}
              selected={entity.id === selectedId}
              seed={world.seed}
              badgeLift={index * 20}
              offsetX={offsetX}
              offsetY={offsetY}
            />
          );
        });
      })()}
      <g className="map-labels" aria-hidden="true">
        <text x="55" y="690">
          ROWAN HOMES
        </text>
        <text x="580" y="28">
          OLD CENTRE
        </text>
        <text x="970" y="28">
          EASTGATE
        </text>
      </g>
      <text className="map-note" x="42" y="705">
        Rowan homes · Market quarter · Folk Loop Railway
      </text>
      <text className="map-note" x="1020" y="705">
        {world.people.length} neighbours
      </text>
      <title>{`SmallFolks at ${world.clock}`}</title>
    </svg>
  );
}

function TrainLoop({
  train,
  passengers,
  people,
  queues,
  onSelect,
  seed,
}: {
  train?: Train;
  passengers: Entity[];
  people: Entity[];
  queues: NonNullable<World["station_queues"]>;
  onSelect: Props["onSelect"];
  seed: number;
}) {
  if (!train?.track?.length) return null;
  const track = train.track;
  const loop = track.map((point) => `${point.x},${point.y}`).join(" ");
  const frontDistance = train?.state?.distance ?? 60;
  const stations = train.stations ?? [];
  return (
    <g className="railway">
      <polyline className="rail-bed" fill="none" points={loop} />
      <polyline className="rail-ties" fill="none" points={loop} />
      <polyline className="rail-line" fill="none" points={loop} />
      {stations.map((station) => {
        const entries = queues.find((queue) => queue.station_id === station.id)?.entries ?? [];
        const horizontal = station.platform.width > station.platform.height;
        return (
          <g
            aria-label={`${station.name}, ${entries.length} waiting`}
            className="station"
            key={station.id}
            onClick={() => onSelect({ ...station, kind: "station" })}
            onKeyDown={(event) => activate(event, () => onSelect({ ...station, kind: "station" }))}
            role="button"
            tabIndex={0}
            transform={`translate(${station.position.x} ${station.position.y})`}
          >
            <rect {...station.platform} rx="3" />
            <text y={station.platform.y - 6}>{station.name.toUpperCase()}</text>
            {entries.map((entry, index) => {
              const person = people.find((resident) => resident.id === entry.person_id);
              const x = horizontal
                ? station.platform.x + 9 + (index % 10) * 15
                : station.platform.x + station.platform.width + 10 + Math.floor(index / 10) * 15;
              const y = horizontal
                ? station.platform.y + station.platform.height + 8 + Math.floor(index / 10) * 15
                : station.platform.y + 9 + (index % 10) * 15;
              return (
                <g className="station-queue-place" key={entry.person_id} transform={`translate(${x} ${y})`}>
                  <title>{`${index + 1}. ${person?.name ?? entry.person_id} in boarding queue`}</title>
                  <circle r="6" />
                  <text textAnchor="middle" y="2">{index + 1}</text>
                </g>
              );
            })}
            {entries.length ? <text className="station-queue-count" y={station.platform.y + station.platform.height + (horizontal ? 34 : 16)}>{entries.length} waiting</text> : null}
          </g>
        );
      })}
      <TrainCar
        distance={frontDistance}
        kind="locomotive"
        onSelectTrain={() => onSelect({ id: train.id, kind: "train", name: train.name, position: railPosition(track, frontDistance) })}
        track={track}
      />
      <TrainCar
        distance={frontDistance - 48}
        kind="coach"
        doorsOpen={train.state?.doors_open}
        onSelect={onSelect}
        seed={seed}
        passengers={passengers.filter((person) => person.train_car_index === 0)}
        track={track}
      />
      <TrainCar
        distance={frontDistance - 96}
        kind="coach"
        doorsOpen={train.state?.doors_open}
        onSelect={onSelect}
        seed={seed}
        passengers={passengers.filter((person) => person.train_car_index === 1)}
        track={track}
      />
      {passengers.length ? (
        <text className="train-passenger-count" x="760" y="43">
          {passengers.length} aboard
        </text>
      ) : null}
    </g>
  );
}

function TrainCar({
  distance,
  doorsOpen,
  kind,
  passengers = [],
  onSelect,
  onSelectTrain,
  seed,
  track,
}: {
  distance: number;
  doorsOpen?: boolean;
  kind: "locomotive" | "coach";
  passengers?: Entity[];
  onSelect?: Props["onSelect"];
  onSelectTrain?: () => void;
  seed?: number;
  track: NonNullable<Train["track"]>;
}) {
  const { x, y, heading } = railPosition(track, distance);
  return (
    <g
      aria-label={kind === "locomotive" ? "Inspect Folk Loop train" : undefined}
      className={`folk-train folk-train-${kind}`}
      onClick={onSelectTrain}
      onKeyDown={onSelectTrain ? (event) => activate(event, onSelectTrain) : undefined}
      role={onSelectTrain ? "button" : undefined}
      style={{ transform: `translate(${x}px, ${y}px) rotate(${heading}deg)` }}
      tabIndex={onSelectTrain ? 0 : undefined}
      transform={`translate(${x} ${y}) rotate(${heading})`}
    >
      {kind === "locomotive" ? (
        <>
          <path className="train-locomotive" d="M-21-10H11l11 5v10l-11 5h-32l-7-10z" />
          <rect className="train-roof-kit" height="10" rx="1" width="10" x="-9" y="-5" />
          <path className="train-windows" d="M-16-7v14M-5-7v14M6-7v14" />
          <path className="train-bogies" d="M-16 11h12M5 11h12" />
        </>
      ) : (
        <>
          <rect className="train-coach" height="20" rx="3" width="40" x="-20" y="-10" />
          <rect className="train-roof-kit" height="10" rx="1" width="11" x="-5" y="-5" />
          <path className="train-windows" d="M-14-7v14M-4-7v14M6-7v14M16-7v14" />
          {doorsOpen ? <rect className="train-open-door" x="-3" y="9" width="6" height="4" /> : null}
          {passengers.map((passenger) => (
            <TrainPassenger
              key={passenger.id}
              onSelect={onSelect}
              passenger={passenger}
              seed={seed ?? 0}
            />
          ))}
          <path className="train-bogies" d="M-15 11h12M4 11h12" />
        </>
      )}
    </g>
  );
}

function TrainPassenger({
  passenger,
  onSelect,
  seed,
}: {
  passenger: Entity;
  onSelect?: Props["onSelect"];
  seed: number;
}) {
  const seatPositions = [
    [-13, -2],
    [-5, -2],
    [5, -2],
    [13, -2],
  ];
  const [x, y] = seatPositions[passenger.train_seat_index ?? 0] ?? seatPositions[0];
  const appearance = appearanceFor(passenger.id, seed);
  return (
    <g
      aria-label={`${passenger.name}, seated on Folk Loop`}
      className={`train-passenger train-passenger-${passenger.palette ?? "blue"}`}
      style={
        {
          "--skin": appearance.skinColor,
          "--hair": appearance.hairColor,
          "--outfit": appearance.outfit,
        } as CSSProperties
      }
      onClick={() => onSelect?.(passenger)}
      onKeyDown={(event) => activate(event, () => onSelect?.(passenger))}
      role="button"
      tabIndex={0}
      transform={`translate(${x} ${y})`}
    >
      <circle cy="-3" r="2.5" />
      <path d="M-2 0Q0-2 2 0v5h-4z" />
      <path
        className="train-passenger-hair"
        d={
          appearance.hair === "long" || appearance.hair === "bob"
            ? "M-3-4q0-4 3-4t3 4v4H2v-4H-2v4h-1Z"
            : "M-3-4q0-4 3-4t3 4q-3-2-6 0Z"
        }
      />
    </g>
  );
}

function railPosition(track: NonNullable<Train["track"]>, distance: number) {
  const length = track[track.length - 1].distance;
  const position = ((distance % length) + length) % length;
  const index = track.findIndex((point) => point.distance >= position);
  const end = track[Math.max(1, index)];
  const start = track[Math.max(0, index - 1)];
  const fraction = (position - start.distance) / (end.distance - start.distance);
  return {
    x: start.x + (end.x - start.x) * fraction,
    y: start.y + (end.y - start.y) * fraction,
    heading: (Math.atan2(end.y - start.y, end.x - start.x) * 180) / Math.PI,
  };
}

function Building({
  world,
  smokeActive,
  project,
  place,
  onSelect,
  selected,
}: {
  place: Place;
  smokeActive: boolean;
  world: World;
  project?: ConstructionProject;
  onSelect: Props["onSelect"];
  selected: boolean;
}) {
  const { x, y } = place.position;
  const isHome = place.kind === "home";
  const isPark = place.kind === "park";
  const mansionHome = isHome && place.house_style === "mansion";
  const estateHome = isHome && Boolean(place.driveway) && !mansionHome;
  const largeHome = isHome && (estateHome || mansionHome || place.house_style === "large");
  const variant = [...place.id].reduce((sum, letter) => sum + letter.charCodeAt(0), 0) % 5;
  return (
    <g
      className={`place place-${place.kind} building-color-${variant} ${selected ? "place-selected" : ""}`}
      aria-label={`${place.name}, ${place.kind}${place.operating_state ? `, ${place.operating_state.status}` : ""}`}
      aria-pressed={selected}
      onClick={() => onSelect(place)}
      onKeyDown={(event) => activate(event, () => onSelect(place))}
      role="button"
      tabIndex={0}
      transform={`translate(${x} ${y})`}
    >
      <title>{`${place.name}${place.operating_state ? `: ${place.operating_state.status}. ${place.operating_state.reason}` : ""}`}</title>
      <rect
        className="place-hit"
        x={isHome ? (mansionHome ? -160 : estateHome ? -54 : largeHome ? -50 : -40) : -64}
        y={mansionHome ? -130 : estateHome ? -80 : -59}
        width={isHome ? (mansionHome ? 320 : estateHome ? 116 : largeHome ? 112 : 80) : 128}
        height={mansionHome ? 292 : estateHome ? 132 : 106}
        rx="12"
      />
      {isHome && selected && (
        <g className="house-selection" pointerEvents="none" aria-hidden="true">
          <rect className="house-selection-halo" x={mansionHome ? -160 : estateHome ? -55 : largeHome ? -51 : -41} y={mansionHome ? -130 : estateHome ? -81 : largeHome ? -65 : -54} width={mansionHome ? 320 : estateHome ? 118 : largeHome ? 114 : 82} height={mansionHome ? 292 : estateHome ? 134 : largeHome ? 105 : 94} rx="8" />
          <rect className="house-selection-ring" x={mansionHome ? -160 : estateHome ? -55 : largeHome ? -51 : -41} y={mansionHome ? -130 : estateHome ? -81 : largeHome ? -65 : -54} width={mansionHome ? 320 : estateHome ? 118 : largeHome ? 114 : 82} height={mansionHome ? 292 : estateHome ? 134 : largeHome ? 105 : 94} rx="8" />
        </g>
      )}
      {estateHome && <EstateGarden />}
      {place.driveway && !mansionHome && (
        <g className="home-driveway" aria-label="Side driveway with parking">
          <path className="driveway-paving" d={`M48 -12V${place.driveway.road_position.y - y}L${place.driveway.road_position.x - x} ${place.driveway.road_position.y - y}`} />
          <path className="driveway-parking" d="M37-10h22v44H37" />
        </g>
      )}
      {isPark ? (
        <>
          <path className="park-lawn" d="M-66-46Q-8-56 62-46Q77-10 66 45Q8 56-68 44Q-78 4-66-46Z" />
          <path className="park-path" d="M-70 24Q-25-18 4 7T70-16" />
          <ellipse className="fountain-basin" cx="18" cy="-12" rx="23" ry="14" />
          <ellipse className="fountain-water" cx="18" cy="-14" rx="18" ry="10" />
          <path className="fountain-jet" d="M18-14v-24m0 9q-12-10-14 3m14-3q12-10 14 3" />
          <path className="park-bench" d="M-49 24h27m-27 5h27m-23 0v7m20-7v7" />
          <path className="flower-bed" d="M-51-28h23m-19 5h15" />
        </>
      ) : mansionHome ? (
        <Mansion place={place} world={world} />
      ) : estateHome ? (
        <EstateHome />
      ) : (
        <g className="illustrated-building">
          <ellipse className="house-shadow" cx="7" cy="30" rx={isHome ? 37 : 56} ry="9" />
          <g transform={isHome ? (largeHome ? "translate(-8 -5) scale(1.12 1.15)" : undefined) : "scale(1.42 1.12)"}>
            <path className="house-side" d="M28-11l10-10v43L28 31Z" />
            <path className="house-wall" d="M-30-13L28-12V31L-29 30Z" />
            <path className="house-roof-side" d="M-3-51 9-57 41-21 29-11Z" />
            <path className="house-roof" d="M-36-12-3-51 32-12Z" />
            <path className="roof-pencil" d="M-25-19h45M-19-27h31M-12-35H5M-5-43h4" />
            <path className="house-chimney" d="M16-32v-20h8v28" />
            {smokeActive && <path className="chimney-smoke" d="M20-58q-8-8 0-15t0-14" />}
            <path className="house-door" d="M-6 30V10Q1 3 8 10v20Z" />
            <circle className="door-knob" cx="5" cy="20" r="1" />
            <path className="house-window" d="M-23-3h12v14h-12Zm36 0h10v14H13Z" />
            <path className="window-cross" d="M-17-3v14m-6-7h12M18-3v14m-5-7h10" />
            <path className="window-planter" d="M-25 12h16m2 0h1M11 12h14" />
            {!isHome && (
              <>
                <path className="store-awning" d="M-31-8h60l5 12h-70Z" />
                <path
                  className="awning-stripes"
                  d="m-22-8-2 12M-10-8l-1 12M2-8V4m12-12 1 12m11-12 2 12"
                />
                <BuildingFeature placeId={place.id} />
              </>
            )}
          </g>
          {isHome && (
            <path
              className="little-fence"
              d={largeHome ? "M-46 24v15m8-15v15m8-15v15m-18-10h21" : "M-38 24v15m8-15v15m8-15v15m-18-10h21m40 0h17m-14-5v15m10-15v15"}
            />
          )}
        </g>
      )}
      {!isHome && !isPark && (
        <path className="entrance-steps" aria-label="South-facing entrance" d="M-7 35h14m-14 5h14m-14 5h14" />
      )}
      {project && (
        <g className="construction-site" aria-label={`House construction ${Math.round(project.worked_seconds / project.required_seconds * 100)}% complete`}>
          <path className="construction-scaffold" d="M-39-48v84M31-48v84M-39-35h70M-39-10h70M-39 15h70M-39-35l70 50M31-35l-70 50" />
          <path className="construction-barrier" d="M-40 40h68v9h-68z" />
          <path className="construction-stripes" d="m-35 40 9 9m6-9 9 9m6-9 9 9m6-9 9 9" />
          <text className="construction-progress" x="-5" y="63">{Math.round(project.worked_seconds / project.required_seconds * 100)}%</text>
        </g>
      )}
      {place.operating_state && !place.operating_state.is_open && (
        <g className="building-closed-sign" aria-label={place.operating_state.status}>
          <rect x="-27" y="13" width="54" height="18" rx="3" />
          <text x="0" y="26">Closed</text>
        </g>
      )}
      {(!isHome || mansionHome) && (
        <text className="place-name" x="0" y={mansionHome ? 185 : isPark ? 65 : 56}>
          {place.name}
        </text>
      )}
    </g>
  );
}

function Mansion({ place, world }: { place: Place; world: World }) {
  const roadY = (place.driveway?.road_position.y ?? place.position.y + 210) - place.position.y;
  return (
    <g className="mansion-estate" aria-label="Walled mansion with a vast garden and two parking spaces">
      <rect className="mansion-lawn" x="-151" y="-121" width="302" height="272" rx="8" />
      <path className="mansion-wall" d="M-155 155V-125H155V155" />
      <path className="mansion-wall-cap" d="M-155-128H155M-158-125V155M158-125V155" />
      <path className="mansion-garden-path" d="M-112-65Q-145 25-85 95Q-30 130 0 100M105-70Q142-15 113 22" />
      <path className="mansion-driveway" d={`M0 ${roadY}V43M0 100H114M82 100V68M114 100V68`} />
      <g className="mansion-parking" aria-label="Two driveway parking spaces">
        <rect x="68" y="49" width="28" height="39" rx="2" />
        <rect x="100" y="49" width="28" height="39" rx="2" />
        <text x="82" y="73">P</text><text x="114" y="73">P</text>
      </g>
      <ellipse className="mansion-flower-bed" cx="-88" cy="109" rx="34" ry="11" />
      <ellipse className="mansion-flower-bed" cx="87" cy="-89" rx="25" ry="9" />
      {[-112, -100, -88, -76, -64].map((x, index) => <circle key={x} className={index % 2 ? "estate-flower estate-flower-gold" : "estate-flower"} cx={x} cy="107" r="3" />)}
      <g className="mansion-fountain" transform="translate(-87 58)">
        <ellipse className="fountain-basin" rx="28" ry="18" />
        <ellipse className="fountain-water" cy="-2" rx="22" ry="13" />
        <path className="fountain-jet" d="M0-3V-32M0-21q-12-12-16 2M0-21q12-12 16 2" />
      </g>
      {[[-123, -67], [123, -63], [-126, 130], [135, 133]].map(([x, y]) => (
        <g key={`${x}:${y}`} transform={`translate(${x} ${y})`}>
          <path className="estate-tree-trunk" d="M0 7V-12" />
          <path className="estate-tree-crown" d="M-11-5Q-23-13-13-22Q-16-37 0-39Q17-39 14-24Q27-13 12-5Z" />
        </g>
      ))}
      <path className="mansion-hedge" d="M-143-108H-98M-143-22V24M144-20V18M-136 142H-44M44 142H112" />
      <g className="mansion-house">
        <ellipse className="house-shadow" cy="34" rx="87" ry="14" />
        <path className="mansion-wing" d="M-83-39H-40V32H-83ZM40-39H83V32H40Z" />
        <path className="mansion-wing-roof" d="M-89-39L-61-66L-35-39ZM35-39L61-66L89-39Z" />
        <path className="mansion-facade" d="M-43-70H43V34H-43Z" />
        <path className="mansion-roof" d="M-51-70L-28-102H28L51-70Z" />
        <path className="mansion-roof-lines" d="M-38-79H38M-32-89H32" />
        <path className="mansion-dormer" d="M-12-78V-96L0-108L12-96V-78Z" />
        <path className="mansion-dormer-roof" d="M-16-95L0-112L16-95" />
        <path className="mansion-window" d="M-6-96H6V-82H-6ZM-31-57H-16V-35H-31ZM16-57H31V-35H16ZM-73-25H-59V-6H-73ZM59-25H73V-6H59ZM-73 6H-59V23H-73ZM59 6H73V23H59Z" />
        <path className="mansion-window-bars" d="M0-96V-82M-6-89H6M-23-57V-35M-31-46H-16M23-57V-35M16-46H31M-66-25V-6M-73-16H-59M66-25V-6M59-16H73M-66 6V23M-73 15H-59M66 6V23M59 15H73" />
        <path className="mansion-floor-trim" d="M-43-29H43M-83-1H-43M43-1H83" />
        <path className="mansion-door" d="M-10 34V9Q0-3 10 9V34Z" />
        <path className="mansion-door-trim" d="M-14 34V7Q0-9 14 7V34M0 8V34" />
        <circle className="door-knob" cx="4" cy="22" r="1.3" />
        <path className="mansion-porch-floor" d="M-32 31H32L37 41H-37Z" />
        <path className="mansion-columns" d="M-27-13V32M-18-13V32M18-13V32M27-13V32" />
        <path className="mansion-portico" d="M-37-13L0-36L37-13Z" />
        <path className="mansion-portico-trim" d="M-26-18L0-29L26-18M-36-11H36" />
        <path className="mansion-balustrade" d="M-83 27H-43M43 27H83M-78 27V33M-67 27V33M-56 27V33M56 27V33M67 27V33M78 27V33" />
        <path className="estate-steps" d="M-19 44H19M-16 48H16" />
      </g>
      <path className="mansion-wall mansion-front-wall" d="M-155 155H-22M22 155H155" />
      <path className="mansion-wall-cap" d="M-155 151H-22M22 151H155" />
      <MansionGate world={world} gate={place.estate_gate ?? { x: place.position.x, y: place.position.y + 155 }} />
    </g>
  );
}

function EstateGarden() {
  return (
    <g className="estate-garden" aria-label="Landscaped front garden" pointerEvents="none">
      <path className="estate-lawn" d="M-51-17Q-52-23-45-23H29V27H35V46H-50Z" />
      <path className="estate-garden-walk" d="M-7 32H7V48H-7Z" />
      <path className="estate-hedge" d="M-49-9V38Q-49 44-43 44H-15M15 44H29" />
      <path className="estate-flower-bed" d="M-39 36H-19M18 35H29" />
      {[-36, -28, -20, 20, 28].map((x, index) => (
        <g key={x} transform={`translate(${x} 35)`}>
          <path className="estate-flower-stem" d="M0 3V-3" />
          <circle className={index % 2 ? "estate-flower estate-flower-gold" : "estate-flower"} cy="-3" r="2.5" />
        </g>
      ))}
      <path className="estate-tree-trunk" d="M-43 17V-1" />
      <path className="estate-tree-crown" d="M-49 3Q-57-3-50-10Q-52-20-43-21Q-33-22-33-12Q-25-4-34 2Z" />
    </g>
  );
}

function EstateHome() {
  return (
    <g className="illustrated-building estate-house" aria-label="Two-storey country house with front porch">
      <ellipse className="house-shadow" cx="-5" cy="30" rx="43" ry="9" />
      <path className="estate-side" d="M27-31L35-40V22L27 30Z" />
      <path className="estate-wall" d="M-43-34H27V30H-43Z" />
      <path className="estate-wing" d="M-46-7H-25V29H-46Z" />
      <path className="estate-roof-side" d="M-8-71L1-77L38-39L29-30Z" />
      <path className="estate-roof" d="M-49-32L-8-71L32-32Z" />
      <path className="estate-roof-lines" d="M-37-39H20M-28-48H11M-18-57H1" />
      <path className="estate-wing-roof" d="M-49-7L-36-22L-22-7Z" />
      <path className="estate-chimney" d="M16-49V-70H24V-41" />
      <path className="estate-dormer" d="M-18-40V-53L-8-63L2-53V-40Z" />
      <path className="estate-dormer-roof" d="M-21-52L-8-66L5-52" />
      <path className="estate-window" d="M-13-53H-3V-42H-13ZM-34-24H-22V-8H-34ZM9-24H21V-8H9ZM-39 2H-29V17H-39ZM12 3H24V18H12Z" />
      <path className="estate-window-bars" d="M-8-53V-42M-13-48H-3M-28-24V-8M-34-16H-22M15-24V-8M9-16H21M-34 2V17M-39 10H-29M18 3V18M12 11H24" />
      <path className="estate-shutters" d="M-38-24V-8M-18-24V-8M5-24V-8M25-24V-8M-43 2V17M-25 2V17M8 3V18M28 3V18" />
      <path className="estate-door" d="M-8 30V8Q0 1 8 8V30Z" />
      <circle className="door-knob" cx="4" cy="19" r="1.2" />
      <path className="estate-porch-floor" d="M-18 28H17L20 34H-21Z" />
      <path className="estate-porch-columns" d="M-17 4V29M16 4V29" />
      <path className="estate-porch-roof" d="M-23 5L-1-9L22 5Z" />
      <path className="estate-porch-rail" d="M-18 21H-10M10 21H17M-14 21V28M13 21V28" />
      <path className="estate-steps" d="M-10 36H10M-8 40H8" />
    </g>
  );
}

function BuildingFeature({ placeId }: { placeId: string }) {
  switch (placeId) {
    case "place:bank":
      return (
        <g className="landmark landmark-bank" aria-hidden="true">
          <path className="bank-front" d="M-24-8 0-25 24-8ZM-22 20h44M-20 16h40M-16-5v19M0-5v19M16-5v19" />
          <text className="bank-sign" x="0" y="-9">€</text>
        </g>
      );
    case "place:clinic":
      return (
        <g className="landmark landmark-clinic" aria-hidden="true">
          <path className="clinic-sign" d="M-12-39h24v23h-24z" />
          <path className="clinic-cross" d="M-3-35h6v6h6v6H3v6h-6v-6h-6v-6h6z" />
          <path className="clinic-window" d="M-25 14h12m26 0h12" />
        </g>
      );
    case "place:school":
      return (
        <g className="landmark landmark-school" aria-hidden="true">
          <path className="school-belfry" d="M-11-38v-14h22v14m-25-14 14-12 14 12" />
          <circle className="school-clock" cy="-45" r="7" />
          <path className="school-hands" d="M0-49v4l3 2" />
          <path className="school-board" d="M-26 11h14v13h-14z" />
          <text className="school-letters" x="-19" y="20">
            ABC
          </text>
        </g>
      );
    case "place:restaurant":
      return (
        <g className="landmark landmark-restaurant" aria-hidden="true">
          <circle cx="0" cy="-18" r="11" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M-18-29v11m-3-11v7h6v-7m-3 11v12M18-29v23m0-23q-8 10 0 11" fill="none" stroke="currentColor" strokeWidth="2" />
        </g>
      );
    case "place:lantern-bar":
      return (
        <g className="landmark landmark-bar" aria-hidden="true">
          <path className="bar-bracket" d="M20-25h17v6" />
          <g className="bar-lantern">
            <path d="M31-19h12l-2 17H33zM36-24v5m-3 6h8" />
            <path className="bar-flame" d="M37-6q-5-6 0-10 5 4 0 10" />
          </g>
          <path className="bar-table" d="M-27 25h16m-8 0v7m-7-7-3-5m16 5 3-5" />
        </g>
      );
    case "place:cinema":
      return (
        <g className="landmark landmark-cinema" aria-hidden="true">
          <circle className="cinema-reel" cy="-32" r="12" />
          <path className="cinema-reel-holes" d="M-3-36h.1m7 2h.1m-7 6h.1m-3-4h.1" />
          <path className="cinema-marquee" d="M-31-7h62v15h-62z" />
          <text className="cinema-word" y="4">
            CINEMA
          </text>
          <path className="cinema-bulbs" d="M-27 10h.1m8 0h.1m8 0h.1m20 0h.1m8 0h.1m8 0h.1" />
        </g>
      );
    case "place:post-office":
      return (
        <g className="landmark landmark-post" aria-hidden="true">
          <path className="post-plaque" d="M-17-35h34v20h-34z" />
          <path className="post-envelope" d="M-12-31h24v12h-24zM-12-31 0-23l12-8" />
          <path className="post-box" d="M23 8h10v20H23zM21 8q7-8 14 0M25 13h6" />
        </g>
      );
    case "place:library":
      return (
        <g className="landmark landmark-library" aria-hidden="true">
          <path className="library-pediment" d="M-26-17 0-38l26 21z" />
          <path
            className="library-book"
            d="M-12-24q6-3 12 1 6-4 12-1v11q-6-4-12 1-6-5-12-1zM0-23v11"
          />
          <path className="library-columns" d="M-24 8v18m7-18v18m34-18v18m7-18v18" />
        </g>
      );
    case "place:townhall":
      return (
        <g className="landmark landmark-townhall" aria-hidden="true">
          <path className="townhall-flagpole" d="M0-42v-23" />
          <path className="townhall-flag" d="M0-65q8-4 15 0v12q-8-3-15 1z" />
          <path className="townhall-columns" d="M-25 8v18m8-18v18m34-18v18m8-18v18" />
        </g>
      );
    case "place:workshop":
      return (
        <g className="landmark landmark-workshop" aria-hidden="true">
          <circle className="workshop-gear" cy="-29" r="10" />
          <circle className="workshop-gear-centre" cy="-29" r="3" />
          <path className="workshop-wrench" d="m-24 17 14-14m-5-4-5 4m5-4 2 6" />
        </g>
      );
    case "place:bakery":
      return (
        <g className="landmark landmark-bakery" aria-hidden="true">
          <path className="bakery-loaf" d="M-15-18q0-16 15-16t15 16z" />
          <path className="bakery-cuts" d="m-8-27 3 6m5-8 2 7m6-5 2 5" />
        </g>
      );
    case "place:supermarket":
      return (
        <g className="landmark landmark-market" aria-hidden="true">
          <path className="market-crate" d="M-15-28h30l-3 16h-24zM-13-23h26" />
          <circle className="market-fruit" cx="-6" cy="-28" r="4" />
          <circle className="market-fruit" cx="4" cy="-29" r="5" />
        </g>
      );
    case "place:florist":
      return (
        <g className="landmark landmark-florist" aria-hidden="true">
          <path className="florist-pot" d="M-10-17h20l-3 10H-7z" />
          <path className="florist-stems" d="M0-17v-18m0 13-10-8m10 6 10-7" />
          <circle className="florist-bloom" cy="-36" r="5" />
          <circle className="florist-bloom" cx="-11" cy="-30" r="4" />
          <circle className="florist-bloom" cx="11" cy="-32" r="4" />
        </g>
      );
    default:
      return (
        <g className="landmark landmark-generic" aria-hidden="true">
          <circle className="shop-emblem" cy="-26" r="9" />
          <path className="generic-star" d="M0-32v12m-6-6H6" />
        </g>
      );
  }
}

const EntitySprite = memo(function EntitySprite({
  entity,
  driver,
  driverSelected,
  onSelect,
  selected,
  seed,
  offsetX,
  offsetY,
  badgeLift,
}: {
  entity: Entity;
  driver?: Entity;
  driverSelected: boolean;
  onSelect: Props["onSelect"];
  selected: boolean;
  seed: number;
  offsetX: number;
  offsetY: number;
  badgeLift: number;
}) {
  const activity = activityKind(entity.activity, entity.role);
  const appearance = entity.kind === "person" ? appearanceFor(entity.id, seed) : null;
  const working = activity === "work";
  const workStyle = working ? workStyleFor(entity.role) : undefined;
  const x = entity.position.x + offsetX;
  const y = entity.position.y + offsetY;
  const vehiclePaint =
    entity.model === "sports"
      ? ["ruby", "sapphire", "emerald", "amethyst", "champagne"].includes(entity.palette ?? "")
        ? entity.palette
        : "ruby"
      : (entity.palette ?? "coral");
  const className = `map-entity ${entity.kind} palette-${vehiclePaint} activity-${activity} ${selected || driverSelected ? "is-selected" : ""}`;
  const visualStyle = {
    transform: `translate(${x}px, ${y}px)`,
    "--motion-delay": `${(-(seed + entity.id.length) % 21) * 0.13}s`,
    ...(appearance
      ? {
          "--skin": appearance.skinColor,
          "--hair": appearance.hairColor,
          "--outfit": appearance.outfit,
          "--outfit-dark": appearance.outfitDark,
        }
      : {}),
  } as CSSProperties;
  return (
    <g
      className={className}
      aria-label={`${entity.name}, ${entity.activity ?? entity.state ?? entity.kind}`}
      aria-pressed={selected}
      onClick={() => onSelect(entity)}
      onKeyDown={(event) => activate(event, () => onSelect(entity))}
      style={visualStyle}
      role="button"
      tabIndex={0}
      transform={`translate(${x} ${y})`}
    >
      {entity.kind !== "vehicle" && <circle className="entity-hit" r="25" />}
      {entity.kind !== "vehicle" && (selected || driverSelected) && (
        <ellipse className="selection-ring" cy="13" rx="19" ry="9" />
      )}
      {entity.kind !== "vehicle" && <ellipse className="entity-shadow" cy="14" rx="9" ry="3" />}
      {entity.kind === "person" && appearance ? (
        <>
          <PersonSprite
            appearance={appearance}
            activity={activity}
            carryingGroceries={entity.carrying_groceries === true}
            workStyle={workStyle}
          />
          <ActivityBadge kind={activity} selected={selected} lift={badgeLift} />
        </>
      ) : entity.kind === "pet" ? (
        <PetSprite activity={activity} />
      ) : (
        <VehicleSprite
          sports={entity.model === "sports"}
          driver={driver}
          heading={entity.heading ?? 0}
          highlighted={selected || driverSelected}
          onSelect={onSelect}
        />
      )}
      {(selected || driverSelected) && (
        <text className="entity-label" y={entity.kind === "vehicle" ? -25 : -63 - badgeLift}>
          {driverSelected ? driver?.name.split(" ")[0] : entity.name.split(" ")[0]}
        </text>
      )}
    </g>
  );
});

function ActivityBadge({
  kind,
  selected,
  lift,
}: {
  kind: ActivityKind;
  selected: boolean;
  lift: number;
}) {
  const label = activityLabels[kind];
  const width = label.length * 5.3 + 18;
  return (
    <g
      className={`activity-badge ${selected ? "is-highlighted" : ""}`}
      transform={`translate(0 ${-39 - lift})`}
      aria-hidden="true"
      pointerEvents="none"
    >
      <rect x={-width / 2} y="-10" width={width} height="17" rx="8" />
      <text y="2">{label}</text>
    </g>
  );
}

function PersonSprite({
  appearance,
  activity,
  carryingGroceries,
  workStyle,
}: {
  appearance: Appearance;
  activity: ActivityKind;
  carryingGroceries: boolean;
  workStyle?: WorkStyle;
}) {
  const sleeping = activity === "sleep";
  return (
    <>
      {sleeping && (
        <g className="sleep-bed" aria-hidden="true">
          <rect x="-23" y="-8" width="47" height="19" rx="5" />
          <rect className="sleep-pillow" x="-20" y="-5" width="12" height="13" rx="3" />
        </g>
      )}
      <g className={`person-body hair-${appearance.hair} ${appearance.skirt ? "wears-skirt" : ""}`}>
        <path className="person-legs leg-left" d="M-4 10v8l-2 1" />
        <path className="person-legs leg-right" d="M4 10v8l2 1" />
        <path className="person-torso" d="M-7 0Q0-5 7 0v12H-7z" />
        {appearance.skirt && <path className="person-skirt" d="M-6 7h12l3 8H-9Z" />}
        <circle className="person-head" cy="-8" r="7" />
        <Hair style={appearance.hair} />
        {sleeping ? (
          <path className="person-sleep-face" d="M-5-8q2 2 4 0m3 0q2 2 4 0" />
        ) : (
          <path className="person-face" d="M-3-8h.1M3-8h.1M-2-4q2 2 4 0" />
        )}
        {appearance.freckles && !sleeping && (
          <path className="person-freckles" d="M-5-5h.1m1 1h.1M4-5h.1m1 1h.1" />
        )}
        {appearance.glasses && !sleeping && (
          <path className="person-glasses" d="M-6-10h5v4h-5Zm7 0h5v4H1Zm-2 2h2" />
        )}
        <path className="person-arm arm-left" d="M-7 2-11 9" />
        <path className="person-arm arm-right" d="M7 2l4 7" />
      </g>
      <ActivityProp kind={activity} workStyle={workStyle} carryingGroceries={carryingGroceries} />
    </>
  );
}

function Hair({ style }: { style: Appearance["hair"] }) {
  const shape = {
    crop: "M-7-9Q-6-17 1-16Q8-15 7-9Q2-13-7-9Z",
    sweep: "M-8-8Q-6-18 3-17Q11-15 7-5L4-10Q-2-6-8-8Z",
    bob: "M-8-9Q-8-17 0-17Q9-17 9-7L7 2H4L5-8Q0-12-6-7L-5 2H-8Z",
    long: "M-8-9Q-7-18 1-17Q10-16 9-7L11 7H6L5-8Q0-12-5-7L-6 7H-11Z",
    bun: "M-7-8Q-7-16 0-16Q8-16 8-7Q0-12-7-8ZM6-14Q7-21 12-18Q16-13 9-11Z",
  }[style];
  return <path className="person-hair" d={shape} />;
}

function ActivityProp({
  kind,
  workStyle,
  carryingGroceries,
}: {
  kind: ActivityKind;
  workStyle?: WorkStyle;
  carryingGroceries: boolean;
}) {
  return (
    <g className={`activity-prop prop-${kind}`} aria-hidden="true">
      {kind === "sleep" && (
        <>
          <path className="sleep-blanket" d="M-2-7h24v18H-2q5-8 0-18Z" />
          <g className="sleep-zzz" aria-hidden="true">
            <text className="sleep-z" x="20" y="-13">
              Z
            </text>
            <text className="sleep-z" x="28" y="-20">
              Z
            </text>
            <text className="sleep-z" x="36" y="-27">
              Z
            </text>
          </g>
        </>
      )}
      {kind === "read" && (
        <>
          <path
            className="prop-book"
            d="M-1 4q6-3 12 1v10q-6-3-12 0zm12 1q6-4 12-1v10q-6-3-12 1Z"
          />
          <path className="book-lines" d="M2 7h6m-6 3h6m6-3h6m-6 3h6" />
        </>
      )}
      {kind === "garden" && (
        <>
          <path className="prop-watering-can" d="M8 2h12v10H8Zm12 3h5q2 5-5 6M10 2V0h8" />
          <path className="garden-drops" d="m25 12 2 3m2-2 2 3" />
          <path className="garden-sprout" d="M29 20v-5m0 2q-4-5-6-3m6 2q3-5 6-3" />
        </>
      )}
      {kind === "plant" && (
        <g className="planting-scene">
          <ellipse className="planting-soil" cx="30" cy="23" rx="14" ry="4" />
          <g className="planting-sow">
            <path className="planting-arm" d="M9 0q8 3 13 12" />
            <path className="planting-trowel" d="m19 9 6 7-3 5-5-8Z" />
            <circle className="planting-seed" cx="25" cy="13" r="2" />
          </g>
          <g className="planting-water">
            <path className="planting-arm" d="M8 0 16 5" />
            <g className="planting-can">
              <path d="M13 1h12v11H13Zm2 0v-5h8v5m2 3 7 5-2 3-5-4" />
              <path className="planting-can-handle" d="M13 3q-7-3-6 4q0 5 6 3" />
            </g>
            <g className="planting-water-drops">
              <path d="m30 13 1 3m4-1 1 3m-6 1 1 3" />
            </g>
          </g>
          <g className="planting-sapling">
            <path className="planting-stem" d="M30 23V7" />
            <path className="planting-leaves" d="M30 15Q17 16 20 7Q29 6 30 15ZM30 11Q31 1 40 3Q43 12 30 11Z" />
          </g>
        </g>
      )}
      {kind === "call" && (
        <>
          <rect className="prop-phone" x="8" y="-11" width="7" height="14" rx="2" />
          <path className="phone-signal" d="M18-11q6 4 0 8m3-11q9 7 0 14" />
        </>
      )}
      {kind === "chores" && (
        <>
          <path className="prop-broom" d="M16-16 12 11m-5 0h10l2 7H5Z" />
          <path className="chores-sparkle" d="M23 4v6m-3-3h6" />
        </>
      )}
      {kind === "hobby" && (
        <>
          <rect className="prop-canvas" x="9" y="-11" width="17" height="17" rx="2" />
          <path className="canvas-doodle" d="m12 2 4-5 4 4 3-6" />
          <path className="prop-brush" d="m7 13 14-19" />
        </>
      )}
      {kind === "eat" && (
        <>
          <ellipse className="breakfast-plate" cx="13" cy="13" rx="12" ry="5" />
          <circle className="plate-food" cx="13" cy="12" r="4" />
          <path className="breakfast-spoon" d="M7 5 10-2" />
          <path className="steam-lines" d="M10 2q-3-3 0-6m8 6q-3-3 0-6" />
        </>
      )}
      {kind === "shop" && (
        <>
          <path className="prop-basket" d="M7 6h17l-3 13H10Zm3 0q1-9 6-9t6 9" />
          <circle className="basket-produce" cx="12" cy="7" r="3" />
          <circle className="basket-produce" cx="19" cy="6" r="3" />
        </>
      )}
      {kind === "film" && (
        <>
          <rect className="prop-screen" x="9" y="-14" width="22" height="18" rx="2" />
          <path className="screen-play" d="m18-10 7 5-7 5Z" />
          <path className="screen-rays" d="M12 8v3m6-2v4m6-4v3" />
        </>
      )}
      {kind === "social" && (
        <>
          <path className="beer-glass" d="M9 2h10v13H9z" />
          <path className="beer-foam" d="M9 2q3-4 5 0q3-4 5 0" />
          <path className="beer-handle" d="M19 5h5v7h-5" />
          <path className="social-chatter" d="M-17-16h15v9l-4-3h-11Z" />
        </>
      )}
      {kind === "walk" && (
        <>
          <path className="walking-trail" d="M-16 19h3m4 2h3m4-2h3" />
          {carryingGroceries && (
            <g className="grocery-bags">
              <path className="grocery-bag" d="M7 6h13l2 13H5z" />
              <path className="grocery-bag-handle" d="M10 6q3-8 7 0" />
            </g>
          )}
        </>
      )}
      {kind === "ride" && <path className="ride-ticket" d="M9-3h18v13H9q2-3 0-6t0-7Z" />}
      {kind === "work" && workStyle && <WorkActivity style={workStyle} />}
      {kind === "wait" && (
        <path className="wait-clock" d="M19-9a9 9 0 1 0 0 18 9 9 0 1 0 0-18Zm0 4v5l4 2" />
      )}
      {kind === "rest" && <path className="rest-mug" d="M8 3h12v12H8Zm12 2h4v7h-4" />}
    </g>
  );
}

type WorkStyle =
  | "bakery"
  | "tools"
  | "book"
  | "care"
  | "shop"
  | "plan"
  | "garden"
  | "bar"
  | "cinema";

function workStyleFor(role?: string): WorkStyle {
  switch (role) {
    case "Chef":
    case "Baker":
      return "bakery";
    case "Mechanic":
    case "Carpenter":
      return "tools";
    case "Librarian":
    case "Teacher":
    case "Student":
      return "book";
    case "Nurse":
      return "care";
    case "Shopkeeper":
      return "shop";
    case "Planner":
      return "plan";
    case "Gardener":
      return "garden";
    case "Bartender":
    case "Server":
      return "bar";
    case "Projectionist":
    case "Box office host":
    case "Usher":
      return "cinema";
    default:
      return "book";
  }
}

function WorkActivity({ style }: { style: WorkStyle }) {
  switch (style) {
    case "bakery":
      return <path className="work-tool work-loaf" d="M8 3q7-5 10 1v7H8zM11 5h4M11 8h4" />;
    case "tools":
      return <path className="work-tool work-wrench" d="m8 2 3 3-5 5-3-3 5-5m0 0 3-1 1 3" />;
    case "book":
      return (
        <path
          className="work-tool work-book"
          d="M7 3q4-2 8 1v10q-4-3-8-1zM15 4q3-3 6-1v10q-3-2-6 1z"
        />
      );
    case "care":
      return <path className="work-tool work-care" d="M12 2v12M6 8h12" />;
    case "shop":
      return (
        <path className="work-tool work-box" d="m7 4 6-3 6 3v9l-6 3-6-3zM7 4l6 3 6-3M13 7v9" />
      );
    case "plan":
      return <path className="work-tool work-plan" d="M6 2h12v12H6zM8 5h8M8 8h5M8 11h7" />;
    case "garden":
      return <path className="work-tool work-water" d="M7 7h9v7H7zM16 9h4v4h-4M10 7V4h4" />;
    case "bar":
      return <path className="work-tool work-tray" d="M6 10h15M13 10v5M10 15h7" />;
    case "cinema":
      return (
        <path
          className="work-tool work-reel"
          d="M12 8a6 6 0 1 0 0 .1M12 8l5-3M12 8l5 4M12 8l-4 5"
        />
      );
  }
}
function PetSprite({ activity }: { activity: ActivityKind }) {
  return (
    <g className="pet-body">
      <ellipse cx="0" cy="3" rx="9" ry="5" />
      <circle className="pet-head" cx="8" cy="0" r="4" />
      <path d="m10-4 3-4 1 5M-5 6v5M5 6v5" />
      <path className="pet-tail" d="M-8 4q-9-1-7-8" />
      {activity === "rest" && (
        <text className="pet-sleep-z" x="8" y="-10">
          z
        </text>
      )}
      {activity === "wait" && <path className="pet-wait-mark" d="M12-17v8m0 4v2" />}
      {activity === "cleanup" && (
        <path className="pet-cleanup-mark" d="M12-15 21 0H3Zm0 5v5m0 2v1" />
      )}
    </g>
  );
}
function VehicleSprite({ sports, driver, heading, highlighted, onSelect }: { sports: boolean; driver?: Entity; heading: number; highlighted: boolean; onSelect: Props["onSelect"] }) {
  return (
    <g className={sports ? "vehicle-body sports-car-body" : "vehicle-body"} transform={`rotate(${heading})`}>
      {sports ? (
        <>
          <rect className="entity-hit vehicle-hit" x="-27" y="-14" width="54" height="28" rx="8" />
          {highlighted && <rect className="vehicle-selection-ring" x="-27" y="-14" width="54" height="28" rx="8" />}
          <ellipse className="vehicle-shadow" cx="1" cy="2" rx="26" ry="11" />
          <rect className="vehicle-wheel" x="-18" y="-12" width="9" height="5" rx="1" />
          <rect className="vehicle-wheel" x="11" y="-11" width="8" height="4" rx="1" />
          <rect className="vehicle-wheel" x="-18" y="7" width="9" height="5" rx="1" />
          <rect className="vehicle-wheel" x="11" y="7" width="8" height="4" rx="1" />
          <path className="vehicle-shell sports-car-shell" d="M-22-7Q-20-11-13-10L8-8Q20-7 25-2V2Q20 7 8 8L-13 10Q-20 11-22 7Z" />
          <path className="vehicle-roof" d="M-9-6-2-6 6-4V4L-2 6H-9Q-12 0-9-6Z" />
          <path className="vehicle-windshield" d="M4-6 10-5 12 0 10 5 4 6Q7 0 4-6Z" />
          <path className="vehicle-rear-window" d="M-12-6-17-7-18 0-17 7-12 6Z" />
          <path className="sports-car-spoiler" d="M-22-11h3v22h-3z" />
          <path className="sports-car-vents" d="M-16-4v8m-3-7v6M13-4l5 1m-5 7 5-1" />
          <path className="sports-car-highlight" d="M-11-8 7-6 19-3M-11 8 7 6 19 3" />
          <path className="vehicle-lights" d="m21-5 2 2m-2 8 2-2" />
          <path className="vehicle-tail-lights" d="M-22-6v3m0 6v3" />
        </>
      ) : (
        <>
      <rect className="entity-hit vehicle-hit" x="-22" y="-14" width="44" height="28" rx="7" />
      {highlighted && <rect className="vehicle-selection-ring" x="-22" y="-14" width="44" height="28" rx="7" />}
      <ellipse className="vehicle-shadow" cx="1" cy="2" rx="20" ry="11" />
      <rect className="vehicle-wheel" x="-14" y="-12" width="8" height="5" rx="1" />
      <rect className="vehicle-wheel" x="8" y="-12" width="8" height="5" rx="1" />
      <rect className="vehicle-wheel" x="-14" y="7" width="8" height="5" rx="1" />
      <rect className="vehicle-wheel" x="8" y="7" width="8" height="5" rx="1" />
      <path className="vehicle-shell" d="M-17-8Q-19-7-19-4v8q0 3 2 4h30q6 0 7-5V-3q-1-5-7-5Z" />
      <rect className="vehicle-roof" x="-9" y="-6" width="18" height="12" rx="4" />
      <path className="vehicle-windshield" d="M7-5q5 0 6 5-1 5-6 5Z" />
      <path className="vehicle-rear-window" d="M-9-5q-4 1-5 5 1 4 5 5Z" />
      <path className="vehicle-hood" d="M14-5v10" />
      <path className="vehicle-lights" d="M17-6h2M17 6h2" />
      <path className="vehicle-tail-lights" d="M-18-6h2M-18 6h2" />
        </>
      )}
      {driver ? (
        <g
          aria-label={`${driver.name} driving`}
          className="vehicle-driver"
          onClick={(event) => { event.stopPropagation(); onSelect(driver); }}
          onKeyDown={(event) => { event.stopPropagation(); activate(event, () => onSelect(driver)); }}
          role="button"
          tabIndex={0}
          transform={`rotate(${-heading})`}
        >
          <circle className="vehicle-driver-hit" r="8" />
          <circle className="vehicle-driver-head" r="4" />
          <text textAnchor="middle" y="2">{driver.name.charAt(0)}</text>
        </g>
      ) : null}
    </g>
  );
}
function TownTreesContent({ plantedTrees = [] }: { plantedTrees?: { position: { x: number; y: number } }[] }) {
  return (
    <g className="trees">
      {[
        ...plantedTrees.map(({ position }) => [position.x, position.y]),
        [45, 65],
        [335, 80],
        [330, 290],
        [410, 130],
        [445, 320],
        [675, 180],
        [755, 260],
        [910, 120],
        [1110, 410],
        [920, 550],
        [1090, 610],
        [380, 610],
      ].map(([x, y]) => (
        <g key={`${x}-${y}`} transform={`translate(${x} ${y})`}>
          <ellipse className="tree-shadow" cy="12" rx="20" ry="7" />
          <path className="tree-trunk" d="M0 14V-15m0 16-9-9M0-4l8-9" />
          <g className="tree-crown" style={{ animationDelay: `${-x / 100}s` }}>
            <path d="M-16-6Q-26-19-13-26Q-12-42 2-37Q18-40 19-25Q31-17 18-6Q6 5-16-6Z" />
            <path className="tree-pencil" d="M-13-20q1-9 9-8M8-25q8 0 7 7M-10-9q9 4 17-1" />
          </g>
        </g>
      ))}
    </g>
  );
}

function TownDetailsContent() {
  return (
    <g className="town-details" aria-hidden="true" pointerEvents="none">
      {[
        [48, 530],
        [340, 550],
        [815, 210],
        [935, 450],
        [350, 120],
        [790, 470],
      ].map(([x, y], index) => (
        <g key={x} transform={`translate(${x} ${y})`}>
          <path className="flower-stems" d="M0 0v-9m7 12v-8m-14 4v-6" />
          <g className={`flowers flowers-${index % 3}`}>
            <circle cy="-10" r="3" />
            <circle cx="7" cy="-6" r="3" />
            <circle cx="-7" cy="-4" r="3" />
          </g>
        </g>
      ))}
      <g className="bunting" transform="translate(590 192)">
        <path d="M0 0q95 34 190 0" />
        {[15, 40, 65, 90, 115, 140, 165].map((x, i) => (
          <path
            key={x}
            className={`flag flag-${i % 3}`}
            d={`M${x} ${17 * Math.sin((x / 190) * Math.PI)}l12 2-7 15Z`}
          />
        ))}
      </g>
      <g className="birds">
        <path d="M870 88q5-7 10 0 5-7 10 0m-45 16q4-6 8 0 4-6 8 0" />
      </g>
      <g className="compass" transform="translate(1170 615)">
        <path d="M0-20v38m-10-26L0-20 10-8" />
        <text y="-28">N</text>
      </g>
    </g>
  );
}
const TownTrees = memo(TownTreesContent);

const TownDetails = memo(TownDetailsContent);
