import type { Position } from "../api/world";

// Gates respond to actual traffic on a route through the opening, not garden occupants.
export function crossesGate(start: Position, end: Position, gate: Position): boolean {
  if (start.y === end.y) return false;
  const fraction = (gate.y - start.y) / (end.y - start.y);
  return (
    fraction >= 0 &&
    fraction <= 1 &&
    Math.abs(start.x + (end.x - start.x) * fraction - gate.x) <= 20
  );
}

export function distanceToGate(
  position: Position,
  route: Position[],
  gate: Position,
): number | null {
  let length = 0;
  let currentDistance = 0;
  let nearest = Infinity;
  const crossings: number[] = [];
  for (let index = 1; index < route.length; index++) {
    const start = route[index - 1],
      end = route[index];
    const dx = end.x - start.x,
      dy = end.y - start.y;
    const segment = Math.hypot(dx, dy);
    if (!segment) continue;
    const projection = Math.max(
      0,
      Math.min(
        1,
        ((position.x - start.x) * dx + (position.y - start.y) * dy) / (segment * segment),
      ),
    );
    const distance = Math.hypot(
      position.x - start.x - dx * projection,
      position.y - start.y - dy * projection,
    );
    if (distance < nearest) {
      nearest = distance;
      currentDistance = length + projection * segment;
    }
    if (crossesGate(start, end, gate)) crossings.push(length + (segment * (gate.y - start.y)) / dy);
    length += segment;
  }
  if (nearest > 6) return null;
  return crossings.find((crossing) => crossing >= currentDistance - 1) !== undefined
    ? Math.max(0, crossings.find((crossing) => crossing >= currentDistance - 1)! - currentDistance)
    : null;
}
