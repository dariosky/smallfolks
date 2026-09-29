import type { CSSProperties, KeyboardEvent } from "react";
import "./sketch.css";

import type { Entity, Place, Train, World } from "../api/world";

type Props = {
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

export function TownMap({ world, selectedId, onSelect }: Props) {
  const selected = world.people.find((person) => person.id === selectedId);
  const trainPassengers = world.people.filter((person) => person.on_train);
  return (
    <svg
      aria-label="SmallFolks town map"
      className={`town-map ${world.simulation.running ? "" : "is-paused"}`}
      viewBox="0 0 1200 720"
    >
      <defs>
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
      <rect className="map-ground" height="720" width="1200" />
      <rect width="1200" height="720" fill="url(#grass-ink)" pointerEvents="none" />
      <path className="river" d="M1160 -20c-55 145 36 245-17 390s24 225-35 370" />
      <path className="river-ripples" d="M1160 -20c-55 145 36 245-17 390s24 225-35 370" />
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
      <TrainLoop onSelect={onSelect} passengers={trainPassengers} train={world.trains?.[0]} />
      {selected?.route ? (
        <polyline
          className="active-route"
          points={selected.route.map((point) => `${point.x},${point.y}`).join(" ")}
        />
      ) : null}
      {world.places.map((place) => (
        <Building
          key={place.id}
          onSelect={onSelect}
          place={place}
          selected={place.id === selectedId}
        />
      ))}
      <TownTrees />
      <TownDetails />
      {[
        ...world.people.filter((person) => !trainPassengers.includes(person)),
        ...world.pets,
        ...world.vehicles,
      ]
        .sort((a, b) => a.position.y - b.position.y)
        .map((entity) => (
          <EntitySprite
            entity={entity}
            key={entity.id}
            onSelect={onSelect}
            selected={entity.id === selectedId}
          />
        ))}
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
  onSelect,
}: {
  train?: Train;
  passengers: Entity[];
  onSelect: Props["onSelect"];
}) {
  const loop =
    "M450 58H1090Q1120 58 1120 88V630Q1120 660 1090 660H450Q420 660 420 630V88Q420 58 450 58Z";
  const frontDistance = train?.state?.distance ?? 60;
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
      <TrainCar
        distance={frontDistance - 48}
        kind="coach"
        onSelect={onSelect}
        passengers={passengers.filter((person) => person.train_car_index === 0)}
      />
      <TrainCar
        distance={frontDistance - 96}
        kind="coach"
        onSelect={onSelect}
        passengers={passengers.filter((person) => person.train_car_index === 1)}
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
  kind,
  passengers = [],
  onSelect,
}: {
  distance: number;
  kind: "locomotive" | "coach";
  passengers?: Entity[];
  onSelect?: Props["onSelect"];
}) {
  const { x, y, heading } = railPosition(distance);
  return (
    <g
      className={`folk-train folk-train-${kind}`}
      style={{ transform: `translate(${x}px, ${y}px) rotate(${heading}deg)` }}
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
          {passengers.map((passenger) => (
            <TrainPassenger key={passenger.id} onSelect={onSelect} passenger={passenger} />
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
}: {
  passenger: Entity;
  onSelect?: Props["onSelect"];
}) {
  const seatPositions = [
    [-13, -2],
    [-5, -2],
    [5, -2],
    [13, -2],
  ];
  const [x, y] = seatPositions[passenger.train_seat_index ?? 0] ?? seatPositions[0];
  return (
    <g
      aria-label={`${passenger.name}, seated on Folk Loop`}
      className={`train-passenger train-passenger-${passenger.palette ?? "blue"}`}
      onClick={() => onSelect?.(passenger)}
      onKeyDown={(event) => activate(event, () => onSelect?.(passenger))}
      role="button"
      tabIndex={0}
      transform={`translate(${x} ${y})`}
    >
      <circle cy="-3" r="2.5" />
      <path d="M-2 0Q0-2 2 0v5h-4z" />
    </g>
  );
}

const RAIL_TOP = 640;
const RAIL_SIDE = 542;
const RAIL_CURVE = (Math.PI * 30) / 2;
const RAIL_LENGTH = RAIL_TOP * 2 + RAIL_SIDE * 2 + RAIL_CURVE * 4;
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

function Building({
  place,
  onSelect,
  selected,
}: {
  place: Place;
  onSelect: Props["onSelect"];
  selected: boolean;
}) {
  const { x, y } = place.position;
  const isHome = place.kind === "home";
  const isPark = place.kind === "park";
  const variant = [...place.id].reduce((sum, letter) => sum + letter.charCodeAt(0), 0) % 5;
  return (
    <g
      className={`place place-${place.kind} building-color-${variant} ${selected ? "place-selected" : ""}`}
      aria-label={`${place.name}, ${place.kind}`}
      aria-pressed={selected}
      onClick={() => onSelect(place)}
      onKeyDown={(event) => activate(event, () => onSelect(place))}
      role="button"
      tabIndex={0}
      transform={`translate(${x} ${y})`}
    >
      <title>{place.name}</title>
      <rect
        className="place-hit"
        x={isHome ? -40 : -64}
        y="-59"
        width={isHome ? 80 : 128}
        height="106"
        rx="12"
      />
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
      ) : (
        <g className="illustrated-building">
          <ellipse className="house-shadow" cx="7" cy="30" rx={isHome ? 37 : 56} ry="9" />
          <g transform={isHome ? undefined : "scale(1.42 1.12)"}>
            <path className="house-side" d="M28-11l10-10v43L28 31Z" />
            <path className="house-wall" d="M-30-13L28-12V31L-29 30Z" />
            <path className="house-roof-side" d="M-3-51 9-57 41-21 29-11Z" />
            <path className="house-roof" d="M-36-12-3-51 32-12Z" />
            <path className="roof-pencil" d="M-25-19h45M-19-27h31M-12-35H5M-5-43h4" />
            <path className="house-chimney" d="M16-32v-20h8v28" />
            <path className="chimney-smoke" d="M20-58q-8-8 0-15t0-14" />
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
                <circle className="shop-emblem" cy="-26" r="9" />
                <text className="shop-emblem-letter" y="-23">
                  {place.kind === "bakery"
                    ? "B"
                    : place.kind === "bar"
                      ? "L"
                      : place.name.charAt(0)}
                </text>
              </>
            )}
          </g>
          {isHome && (
            <path
              className="little-fence"
              d="M-38 24v15m8-15v15m8-15v15m-18-10h21m40 0h17m-14-5v15m10-15v15"
            />
          )}
        </g>
      )}
      {!isHome && (
        <text className="place-name" x="0" y={isPark ? 65 : 56}>
          {place.name}
        </text>
      )}
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
  const walking = entity.activity?.startsWith("Walking") || false;
  const eating =
    entity.activity?.includes("Breakfast") || entity.activity?.includes("eating") || false;
  const socializing = entity.activity?.startsWith("Socializing") || false;
  const sleeping = entity.activity?.startsWith("Sleeping") || false;
  const working = entity.activity?.startsWith("Working as") || false;
  const workStyle = working ? workStyleFor(entity.role) : undefined;
  const className = `map-entity ${entity.kind} palette-${entity.palette ?? "blue"} ${walking ? "is-walking" : ""} ${eating ? "is-eating" : ""} ${workStyle ? `is-working work-${workStyle}` : ""} ${selected ? "is-selected" : ""}`;
  return (
    <g
      className={className}
      aria-label={`${entity.name}, ${entity.activity ?? entity.state ?? entity.kind}`}
      aria-pressed={selected}
      onClick={() => onSelect(entity)}
      onKeyDown={(event) => activate(event, () => onSelect(entity))}
      style={
        {
          transform: `translate(${entity.position.x}px, ${entity.position.y}px)`,
          "--motion-delay": `${-entity.id.length * 0.17}s`,
        } as CSSProperties
      }
      role="button"
      tabIndex={0}
      transform={`translate(${entity.position.x} ${entity.position.y})`}
    >
      <g>
        <circle className="entity-hit" r="21" />
        {selected && <ellipse className="selection-ring" cy="10" rx="17" ry="9" />}
        <ellipse className="entity-shadow" cy="12" rx={entity.kind === "vehicle" ? 17 : 8} ry="3" />
        {entity.kind === "person" ? (
          <PersonSprite
            carryingGroceries={entity.carrying_groceries === true}
            eating={eating}
            socializing={socializing}
            sleeping={sleeping}
            workStyle={workStyle}
          />
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

function PersonSprite({
  carryingGroceries,
  eating,
  socializing,
  sleeping,
  workStyle,
}: {
  carryingGroceries: boolean;
  eating: boolean;
  socializing: boolean;
  sleeping: boolean;
  workStyle?: WorkStyle;
}) {
  return (
    <g className="person-body">
      {eating ? (
        <>
          <ellipse className="breakfast-plate" cx="0" cy="12" rx="8" ry="3" />
          <path className="breakfast-spoon" d="M8 4 12-1" />
        </>
      ) : null}
      {carryingGroceries ? (
        <g className="grocery-bags">
          <path className="grocery-bag" d="M4 6h13l2 13H2z" />
          <path className="grocery-bag-handle" d="M7 6c0-6 7-6 7 0" />
          <circle className="grocery-produce" cx="7" cy="8" r="2.5" />
          <circle className="grocery-produce" cx="14" cy="9" r="2.5" />
        </g>
      ) : null}
      {socializing ? (
        <g className="beer-mug">
          <path className="beer-glass" d="M8 2h7v11H8z" />
          <path className="beer-foam" d="M8 2q2-3 4 0q2-3 4 0" />
          <path className="beer-handle" d="M15 5h4v6h-4" />
        </g>
      ) : null}
      {workStyle ? <WorkActivity style={workStyle} /> : null}
      {sleeping ? (
        <text className="sleep-z" x="8" y="-12">
          zZ
        </text>
      ) : null}
      <path className="person-legs leg-left" d="M-4 10v7l-2 1" />
      <path className="person-legs leg-right" d="M4 10v7l2 1" />
      <path className="person-torso" d="M-7 0Q0-5 7 0v12H-7z" />
      <circle className="person-head" cy="-8" r="7" />
      <path className="person-hair" d="M-7-9Q-3-17 5-14Q8-11 6-6Q1-10-7-7z" />
      <path className="person-face" d="M-3-8h.1M3-8h.1M-2-4q2 2 4 0" />
      <path className="person-arm" d="M-7 2-11 9M7 2l4 7" />
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
function PetSprite() {
  return (
    <g className="pet-body">
      <ellipse cx="0" cy="3" rx="9" ry="5" />
      <circle cx="8" cy="0" r="4" />
      <path d="m10-4 3-4 1 5M-5 6v5M5 6v5" />
      <path className="pet-tail" d="M-8 4q-9-1-7-8" />
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

function TownDetails() {
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
