import { useEffect, useRef, useState } from "react";

import type { Entity, Place, World } from "../api/world";

type Props = {
  world: World;
  selectedId: string | null;
  onSelect: (entity: Entity | Place) => void;
  running?: boolean;
};

export function TownMap({ world, selectedId, onSelect, running = false }: Props) {
  const selected = world.people.find((person) => person.id === selectedId);
  const trainPassengers = world.people.filter((person) =>
    person.activity?.startsWith("Riding Folk Loop"),
  );
  const waitingForTrain = world.people.filter((person) =>
    person.activity?.startsWith("Waiting for Folk Loop"),
  );
  return (
    <svg aria-label="Smallfolk town map" className="town-map" viewBox="0 0 1200 720">
      <defs>
        <pattern height="16" id="paving" patternUnits="userSpaceOnUse" width="16">
          <path d="M0 0h16v16H0z" fill="#eadfcb" />
          <path d="M0 8h16M8 0v8M0 8v8" fill="none" stroke="#d5c4ac" strokeWidth=".7" />
        </pattern>
      </defs>
      <rect className="map-ground" height="720" width="1200" />
      <path className="river" d="M1160 -20c-55 145 36 245-17 390s24 225-35 370" />
      <circle className="sun-glow" cx="1040" cy="90" r="86" />
      <g className="fields">
        <path d="M38 610h285v76H38z" />
        <path d="M900 625h190v60H900z" />
      </g>
      {world.roads.map((road) => (
        <g key={road.id}>
          <polyline
            className="road"
            points={road.points.map((point) => point.join(",")).join(" ")}
          />
          <polyline
            className="road-marking"
            points={road.points.map((point) => point.join(",")).join(" ")}
          />
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
        passengerCount={trainPassengers.length}
        running={running}
        startingStationId={trainPassengers[0]?.train_departure_id}
        waitingStationId={waitingForTrain[0]?.train_departure_id}
      />
      {selected?.route ? (
        <polyline
          className="active-route"
          points={selected.route.map((point) => `${point.x},${point.y}`).join(" ")}
        />
      ) : null}
      {world.places.map((place) => (
        <Building key={place.id} onSelect={onSelect} place={place} />
      ))}
      <TownTrees />
      {[
        ...world.people.filter((person) => !trainPassengers.includes(person)),
        ...world.pets,
        ...world.vehicles,
      ].map((entity) => (
        <EntitySprite
          entity={entity}
          key={entity.id}
          onSelect={onSelect}
          selected={entity.id === selectedId}
        />
      ))}
      <g className="map-labels">
        <text x="45" y="650">
          ROWAN HOMES
        </text>
        <text x="450" y="55">
          OLD CENTRE
        </text>
        <text x="930" y="55">
          EASTGATE
        </text>
      </g>
      <text className="map-note" x="42" y="705">
        Rowan homes · Market quarter · Folk Loop Railway
      </text>
      <text className="map-note" x="1020" y="705">
        {world.people.length} neighbours
      </text>
      <title>{`Smallfolk at ${world.clock}`}</title>
    </svg>
  );
}

function TrainLoop({
  passengerCount,
  running,
  startingStationId,
  waitingStationId,
}: {
  passengerCount: number;
  running: boolean;
  startingStationId?: string;
  waitingStationId?: string;
}) {
  const loop =
    "M450 58H1090Q1120 58 1120 88V630Q1120 660 1090 660H450Q420 660 420 630V88Q420 58 450 58Z";
  const journeyKey = startingStationId ? `riding:${startingStationId}` : "service";
  const elapsed = useSimulationClock(running, journeyKey);
  const startingDistance = startingStationId ? STATION_DISTANCES[startingStationId] : undefined;
  const waitingDistance = waitingStationId ? STATION_DISTANCES[waitingStationId] : undefined;
  const frontDistance =
    startingDistance === undefined
      ? (waitingDistance ?? trainDistance(elapsed))
      : startingDistance + elapsed * 92;
  return (
    <g className="railway">
      <path className="rail-bed" d={loop} />
      <path className="rail-ties" d={loop} />
      <path className="rail-line" d={loop} />
      <g className="station" transform="translate(510 58)">
        <rect height="18" rx="3" width="78" x="-39" y="-9" />
        <text y="-15">MARKET SQUARE</text>
      </g>
      <g className="station" transform="translate(1120 260)">
        <rect height="78" rx="3" width="18" x="-9" y="-39" />
        <text transform="rotate(90)" x="14" y="-15">
          EASTGATE
        </text>
      </g>
      <g className="station" transform="translate(650 660)">
        <rect height="18" rx="3" width="78" x="-39" y="-9" />
        <text y="-15">ROWAN HALT</text>
      </g>
      <TrainCar distance={frontDistance} kind="locomotive" />
      <TrainCar distance={frontDistance - 48} kind="coach" passengers={passengerCount} />
      <TrainCar distance={frontDistance - 96} kind="coach" />
      {passengerCount ? (
        <text className="train-passenger-count" x="760" y="43">
          {passengerCount} aboard
        </text>
      ) : null}
    </g>
  );
}

function TrainCar({
  distance,
  kind,
  passengers = 0,
}: {
  distance: number;
  kind: "locomotive" | "coach";
  passengers?: number;
}) {
  const { x, y, heading } = railPosition(distance);
  return (
    <g
      className={`folk-train folk-train-${kind}`}
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
          {passengers ? <circle className="train-passenger" cx="1" cy="0" r="4" /> : null}
          <path className="train-bogies" d="M-15 11h12M4 11h12" />
        </>
      )}
    </g>
  );
}

function useSimulationClock(running: boolean, resetKey = "") {
  const [elapsed, setElapsed] = useState(0);
  const lastFrame = useRef<number | null>(null);
  useEffect(() => {
    setElapsed(0);
    lastFrame.current = null;
  }, [resetKey]);
  useEffect(() => {
    if (!running) {
      lastFrame.current = null;
      return undefined;
    }
    let frame = 0;
    const update = (now: number) => {
      const delta = lastFrame.current === null ? 0 : now - lastFrame.current;
      lastFrame.current = now;
      setElapsed((value) => value + delta / 1000);
      frame = requestAnimationFrame(update);
    };
    frame = requestAnimationFrame(update);
    return () => cancelAnimationFrame(frame);
  }, [running, resetKey]);
  return elapsed;
}

const RAIL_TOP = 640;
const RAIL_SIDE = 542;
const RAIL_CURVE = (Math.PI * 30) / 2;
const RAIL_LENGTH = RAIL_TOP * 2 + RAIL_SIDE * 2 + RAIL_CURVE * 4;
const STATION_DISTANCES: Record<string, number> = {
  "station:market": 60,
  "station:eastgate": RAIL_TOP + RAIL_CURVE + 172,
  "station:rowan": RAIL_TOP + RAIL_CURVE + RAIL_SIDE + RAIL_CURVE + 440,
};

function trainDistance(elapsed: number) {
  const stops = [
    60,
    RAIL_TOP + RAIL_CURVE + 172,
    RAIL_TOP + RAIL_CURVE + RAIL_SIDE + RAIL_CURVE + 440,
  ];
  const speed = 88;
  const dwellSeconds = 2.2;
  const spans = stops.map((stop, index) => ({ start: index ? stops[index - 1] : 0, end: stop }));
  spans.push({ start: stops[stops.length - 1] ?? 0, end: RAIL_LENGTH });
  const cycleSeconds = spans.reduce(
    (total, span) => total + (span.end - span.start) / speed + dwellSeconds,
    0,
  );
  let remaining = elapsed % cycleSeconds;
  let distance = 0;
  for (const span of spans) {
    const travelSeconds = (span.end - span.start) / speed;
    if (remaining <= travelSeconds) {
      distance = span.start + remaining * speed;
      break;
    }
    remaining -= travelSeconds;
    if (remaining <= dwellSeconds) {
      distance = span.end;
      break;
    }
    remaining -= dwellSeconds;
  }
  return distance;
}

function railPosition(distance: number) {
  let position = ((distance % RAIL_LENGTH) + RAIL_LENGTH) % RAIL_LENGTH;
  if (position <= RAIL_TOP) return { x: 450 + position, y: 58, heading: 0 };
  position -= RAIL_TOP;
  if (position <= RAIL_CURVE) return roundedCorner(1090, 88, -90, position / RAIL_CURVE, 0);
  position -= RAIL_CURVE;
  if (position <= RAIL_SIDE) return { x: 1120, y: 88 + position, heading: 90 };
  position -= RAIL_SIDE;
  if (position <= RAIL_CURVE) return roundedCorner(1090, 630, 0, position / RAIL_CURVE, 90);
  position -= RAIL_CURVE;
  if (position <= RAIL_TOP) return { x: 1090 - position, y: 660, heading: 180 };
  position -= RAIL_TOP;
  if (position <= RAIL_CURVE) return roundedCorner(450, 630, 90, position / RAIL_CURVE, 180);
  position -= RAIL_CURVE;
  if (position <= RAIL_SIDE) return { x: 420, y: 630 - position, heading: 270 };
  position -= RAIL_SIDE;
  return roundedCorner(450, 88, 180, position / RAIL_CURVE, 270);
}

function roundedCorner(
  centerX: number,
  centerY: number,
  startAngle: number,
  progress: number,
  heading: number,
) {
  const angle = ((startAngle + progress * 90) * Math.PI) / 180;
  return {
    x: centerX + 30 * Math.cos(angle),
    y: centerY + 30 * Math.sin(angle),
    heading: heading + progress * 90,
  };
}

function Building({ place, onSelect }: { place: Place; onSelect: Props["onSelect"] }) {
  const { x, y } = place.position;
  const isHome = place.kind === "home";
  const isPark = place.kind === "park";
  return (
    <g
      className={`place place-${place.kind}`}
      onClick={() => onSelect(place)}
      role="button"
      tabIndex={0}
      transform={`translate(${x} ${y})`}
    >
      {isPark ? (
        <>
          <rect className="park-lawn" height="104" rx="18" width="142" x="-71" y="-52" />
          <path className="park-path" d="M-70 10C-25-18 15 38 70-12" />
        </>
      ) : isHome ? (
        <HomeRoof houseId={place.id} />
      ) : (
        <CivicRoof kind={place.kind} />
      )}
      {!isHome && (
        <text className="place-name" x="0" y={isPark ? 66 : 44}>
          {place.name}
        </text>
      )}
    </g>
  );
}

function CivicRoof({ kind }: { kind: string }) {
  return (
    <g className={`civic-roof civic-roof-${kind}`}>
      <rect className="civic-parcel" height="86" rx="10" width="116" x="-58" y="-43" />
      <path className="civic-walk" d="M0 43V27" />
      <rect className="civic-shadow" height="58" rx="4" width="93" x="-41" y="-25" />
      <rect className="civic-plane" height="58" rx="4" width="93" x="-46" y="-30" />
      <path className="civic-ridge" d="M-46-1H47" />
      <path
        className="civic-tiles"
        d="M-44-20H45M-44-10H45M-44 9H45M-44 19H45M-26-29V27M-5-29V27M16-29V27M37-29V27"
      />
      <rect className="civic-skylight" height="15" rx="2" width="17" x="-31" y="-21" />
      <rect className="civic-unit" height="14" rx="2" width="18" x="22" y="8" />
      {kind === "bakery" && (
        <>
          <circle className="bakery-vent" cx="23" cy="-16" r="7" />
          <path className="bakery-vent-line" d="M23-23v-11" />
        </>
      )}
      {kind === "shop" && (
        <>
          <rect className="shop-canopy" height="12" rx="2" width="54" x="-27" y="15" />
          <path className="shop-stripes" d="M-20 15v12M-6 15v12M8 15v12M22 15v12" />
        </>
      )}
    </g>
  );
}

function HomeRoof({ houseId }: { houseId: string }) {
  const variant = Number(houseId.slice(-1)) % 3;
  return (
    <g className={`home-roof home-roof-${variant}`}>
      <rect className="home-parcel" height="74" rx="8" width="78" x="-39" y="-37" />
      <path className="garden-path" d="M0 37V18" />
      <path className="garden-fence" d="M-37-34v68M37-34v68M-37 34h74" />
      <rect className="roof-shadow" height="48" rx="3" width="57" x="-25" y="-21" />
      <rect className="roof-plane" height="48" rx="3" width="57" x="-29" y="-25" />
      <path className="roof-ridge" d="M-29-1H28" />
      <path
        className="roof-tiles"
        d="M-27-17H26M-27-9H26M-27 7H26M-27 15H26M-15-24V22M-2-24V22M11-24V22M24-24V22"
      />
      <rect className="chimney" height="13" rx="1" width="7" x="15" y="-31" />
      <rect className="skylight" height="11" rx="1" width="13" x="-17" y="-18" />
      <circle className="garden-tree" cx="-27" cy="24" r="8" />
      <rect className="garden-shed" height="11" rx="1" width="13" x="17" y="24" />
    </g>
  );
}

function EntitySprite({
  entity,
  onSelect,
  selected,
}: {
  entity: Entity;
  onSelect: Props["onSelect"];
  selected: boolean;
}) {
  const previousPosition = usePreviousPosition(entity.position);
  const walking = entity.activity?.startsWith("Walking") || false;
  const eating = entity.activity?.includes("Breakfast") || false;
  const className = `map-entity ${entity.kind} ${walking ? "is-walking" : ""} ${eating ? "is-eating" : ""} ${selected ? "is-selected" : ""}`;
  const delta = {
    x: previousPosition.x - entity.position.x,
    y: previousPosition.y - entity.position.y,
  };
  return (
    <g
      className={className}
      onClick={() => onSelect(entity)}
      role="button"
      tabIndex={0}
      transform={`translate(${entity.position.x} ${entity.position.y})`}
    >
      <g>
        <animateTransform
          attributeName="transform"
          begin="0s"
          dur="1.15s"
          fill="freeze"
          from={`translate(${delta.x} ${delta.y})`}
          key={`${entity.id}-${entity.position.x}-${entity.position.y}`}
          to="translate(0 0)"
          type="translate"
        />
        <ellipse className="entity-shadow" cy="12" rx={entity.kind === "vehicle" ? 17 : 8} ry="3" />
        {entity.kind === "person" ? (
          <PersonSprite eating={eating} />
        ) : entity.kind === "pet" ? (
          <PetSprite />
        ) : (
          <VehicleSprite />
        )}
        {selected ? (
          <text className="entity-label" y="-29">
            {entity.name.split(" ")[0]}
          </text>
        ) : null}
      </g>
    </g>
  );
}

function usePreviousPosition(position: { x: number; y: number }) {
  const previous = useRef(position);
  const value = previous.current;
  useEffect(() => {
    previous.current = position;
  }, [position]);
  return value;
}

function PersonSprite({ eating }: { eating: boolean }) {
  return (
    <g className="person-body">
      {eating ? (
        <>
          <ellipse className="breakfast-plate" cx="0" cy="12" rx="8" ry="3" />
          <path className="breakfast-spoon" d="M8 4 12-1" />
        </>
      ) : null}
      <path className="person-legs" d="M-4 10v7M4 10v7" />
      <path className="person-torso" d="M-7 0Q0-5 7 0v12H-7z" />
      <circle className="person-head" cy="-8" r="7" />
      <path className="person-hair" d="M-7-9Q-3-17 5-14Q8-11 6-6Q1-10-7-7z" />
      <path className="person-arm" d="M-7 2-11 9M7 2l4 7" />
    </g>
  );
}
function PetSprite() {
  return (
    <g className="pet-body">
      <ellipse cx="0" cy="3" rx="9" ry="5" />
      <circle cx="8" cy="0" r="4" />
      <path d="m10-4 3-4 1 5M-8 4l-6 3" />
    </g>
  );
}
function VehicleSprite() {
  return (
    <g className="vehicle-body">
      <rect height="13" rx="4" width="28" x="-14" y="-5" />
      <path d="M-7-5-2-10h10l6 5z" />
      <circle cx="-8" cy="8" r="3" />
      <circle cx="8" cy="8" r="3" />
    </g>
  );
}
function TownTrees() {
  return (
    <g className="trees">
      {[
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
          <rect height="9" width="4" x="-2" y="3" />
          <circle r="11" />
          <circle cx="7" cy="3" r="8" />
        </g>
      ))}
    </g>
  );
}
