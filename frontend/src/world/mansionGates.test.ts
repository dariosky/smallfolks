import { describe, expect, it } from "vitest";
import { crossesGate, distanceToGate } from "./mansionGates";

const gate = { x: 800, y: 1315 };
describe("mansion gate route detection", () => {
  it("finds the gate ahead on entry and exit routes, including corners", () => {
    const entry = [
      { x: 700, y: 1370 },
      { x: 800, y: 1370 },
      { x: 800, y: 1208 },
    ];
    expect(distanceToGate({ x: 750, y: 1370 }, entry, gate)).toBe(105);
    expect(distanceToGate({ x: 800, y: 1300 }, entry, gate)).toBeNull();
    expect(distanceToGate({ x: 800, y: 1300 }, [...entry].reverse(), gate)).toBe(15);
    expect(crossesGate({ x: 800, y: 1320 }, { x: 800, y: 1310 }, gate)).toBe(true);
  });
  it("ignores nearby roads, routes through the wall, and positions off a route", () => {
    expect(
      distanceToGate(
        { x: 800, y: 1370 },
        [
          { x: 60, y: 1370 },
          { x: 1080, y: 1370 },
        ],
        gate,
      ),
    ).toBeNull();
    expect(crossesGate({ x: 840, y: 1370 }, { x: 840, y: 1208 }, gate)).toBe(false);
    expect(
      distanceToGate(
        { x: 900, y: 1320 },
        [
          { x: 800, y: 1370 },
          { x: 800, y: 1208 },
        ],
        gate,
      ),
    ).toBeNull();
  });
});
