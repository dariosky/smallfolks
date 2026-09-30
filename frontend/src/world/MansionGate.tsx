import { useEffect, useRef, useState } from "react";
import type { Entity, Position, World } from "../api/world";
import { crossesGate, distanceToGate } from "./mansionGates";

type Observation = {
  at: number;
  entities: Map<string, { position: Position; route: Position[]; at: number }>;
};

export function MansionGate({ world, gate }: { world: World; gate: Position }) {
  const [open, setOpen] = useState(false);
  const previous = useRef<Observation | null>(null);
  const occupied = useRef(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    const at = performance.now();
    const entities = new Map<string, { position: Position; route: Position[]; at: number }>();
    const traffic: Entity[] = [
      ...world.people.filter((person) => !person.on_train && !person.in_vehicle_id),
      ...world.vehicles,
      ...world.pets,
    ];
    let passing = false;
    occupied.current = traffic.some(
      (entity) =>
        Math.abs(entity.position.x - gate.x) <= 20 &&
        Math.abs(entity.position.y - gate.y) <= (entity.kind === "vehicle" ? 26 : 6),
    );
    for (const entity of traffic) {
      const driver = entity.driver_id
        ? world.people.find((person) => person.id === entity.driver_id)
        : undefined;
      const route = driver?.route ?? entity.route ?? [];
      const last = previous.current?.entities.get(entity.id);
      const moved = last
        ? Math.hypot(entity.position.x - last.position.x, entity.position.y - last.position.y)
        : 0;
      entities.set(entity.id, {
        position: { ...entity.position },
        route,
        at: last && moved < 0.01 ? last.at : at,
      });
      if (!last || !world.simulation.running) continue;
      if (moved < 0.01) continue;
      const elapsed = (at - last.at) / 1000;
      const ahead = distanceToGate(entity.position, route, gate);
      // Derive visible speed from observations, so anticipation also follows the speed control.
      const approaching = elapsed > 0 && ahead !== null && ahead <= (moved / elapsed) * 3;
      const crossing =
        crossesGate(last.position, entity.position, gate) &&
        (distanceToGate(last.position, last.route, gate) !== null ||
          distanceToGate(last.position, route, gate) !== null);
      passing ||= approaching || crossing;
    }
    previous.current = { at, entities };
    if (passing || (open && occupied.current) || (open && closeTimer.current === null)) {
      setOpen(true);
      if (closeTimer.current) clearTimeout(closeTimer.current);
      closeTimer.current = setTimeout(() => {
        closeTimer.current = null;
        if (!occupied.current) setOpen(false);
      }, 3000);
    }
  }, [world.people, world.vehicles, world.pets, world.simulation.running, gate.x, gate.y, open]);
  useEffect(
    () => () => {
      if (closeTimer.current) clearTimeout(closeTimer.current);
    },
    [],
  );
  return (
    <g
      className={`mansion-gate ${open ? "is-open" : "is-closed"}`}
      aria-label={`South-facing driveway gate, ${open ? "open" : "closed"}`}
    >
      <path className="mansion-gate-pillar" d="M-29 144H-20V161H-29ZM20 144H29V161H20Z" />
      <circle className="mansion-gate-finial" cx="-24.5" cy="141" r="4" />
      <circle className="mansion-gate-finial" cx="24.5" cy="141" r="4" />
      <g transform="translate(-20 155)">
        <g className="mansion-gate-leaf mansion-gate-left">
          <path d="M0-10H20V2H0ZM5-10V2M10-10V2M15-10V2" />
        </g>
      </g>
      <g transform="translate(20 155)">
        <g className="mansion-gate-leaf mansion-gate-right">
          <path d="M0-10H-20V2H0ZM-5-10V2M-10-10V2M-15-10V2" />
        </g>
      </g>
    </g>
  );
}
