import type { CSSProperties, KeyboardEvent } from "react";
import "./sketch.css";

import type { Entity, Place, Train, World } from "../api/world";
import {
  activityKind,
  activityLabels,
  appearanceFor,
  type ActivityKind,
  type Appearance,
} from "./personVisuals";

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
      <TrainLoop
        onSelect={onSelect}
        passengers={trainPassengers}
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
          key={place.id}
          onSelect={onSelect}
          place={place}
          selected={place.id === selectedId}
        />
      ))}
      <TownTrees />
      <TownDetails />
      {(() => {
        const visible = [
          ...world.people.filter((person) => !person.on_train),
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
          return (
            <EntitySprite
              entity={entity}
              key={entity.id}
              onSelect={onSelect}
              selected={entity.id === selectedId}
              seed={world.seed}
              badgeLift={index * 20}
              visualOffset={{ x: (index - (count - 1) / 2) * 26, y: index % 2 ? 5 : -5 }}
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
  queues,
  onSelect,
  seed,
}: {
  train?: Train;
  passengers: Entity[];
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
        const waiting = queues.find((queue) => queue.station_id === station.id)?.entries.length ?? 0;
        return (
          <g
            aria-label={`${station.name}, ${waiting} waiting`}
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
            {waiting ? <text className="station-queue-count" y={station.platform.y + station.platform.height + 16}>{waiting} waiting</text> : null}
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
      {isHome && selected && (
        <g className="house-selection" pointerEvents="none" aria-hidden="true">
          <rect className="house-selection-halo" x="-41" y="-54" width="82" height="94" rx="8" />
          <rect className="house-selection-ring" x="-41" y="-54" width="82" height="94" rx="8" />
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
                <BuildingFeature placeId={place.id} />
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

function BuildingFeature({ placeId }: { placeId: string }) {
  switch (placeId) {
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

function EntitySprite({
  entity,
  onSelect,
  selected,
  seed,
  visualOffset,
  badgeLift,
}: {
  entity: Entity;
  onSelect: Props["onSelect"];
  selected: boolean;
  seed: number;
  visualOffset: { x: number; y: number };
  badgeLift: number;
}) {
  const activity = activityKind(entity.activity, entity.role);
  const appearance = entity.kind === "person" ? appearanceFor(entity.id, seed) : null;
  const working = activity === "work";
  const workStyle = working ? workStyleFor(entity.role) : undefined;
  const x = entity.position.x + visualOffset.x;
  const y = entity.position.y + visualOffset.y;
  const className = `map-entity ${entity.kind} activity-${activity} ${selected ? "is-selected" : ""}`;
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
      <circle className="entity-hit" r="25" />
      {selected && <ellipse className="selection-ring" cy="13" rx="19" ry="9" />}
      <ellipse className="entity-shadow" cy="14" rx={entity.kind === "vehicle" ? 17 : 9} ry="3" />
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
        <VehicleSprite />
      )}
      {selected && (
        <text className="entity-label" y={-63 - badgeLift}>
          {entity.name.split(" ")[0]}
        </text>
      )}
    </g>
  );
}

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
      <circle cx="8" cy="0" r="4" />
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
