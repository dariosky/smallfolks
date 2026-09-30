import { describe, expect, it } from "vitest";
import type { World } from "./world";
import { applyWorldPatch, type WorldPatch } from "./worldStream";

describe("world patches", () => {
  const world = {
    revision: 1,
    roads: [{ id: "road" }],
    people: [
      { id: "a", position: { x: 1, y: 2 }, route: [] },
      { id: "b", position: { x: 3, y: 4 } },
    ],
  } as unknown as World;
  const patch: WorldPatch = {
    type: "patch",
    base_revision: 1,
    revision: 2,
    operations: [
      { path: ["revision"], value: 2 },
      { path: ["people", 0, "position", "x"], value: 5 },
      { path: ["people", 0, "position", "y"], value: 6 },
      { path: ["people", 0, "route"], deleted: true },
    ],
  };
  it("updates only touched containers and preserves the original state", () => {
    const next = applyWorldPatch(world, patch);
    expect(next.people[0].position).toEqual({ x: 5, y: 6 });
    expect(next.people[0]).not.toHaveProperty("route");
    expect(next.roads).toBe(world.roads);
    expect(next.people[1]).toBe(world.people[1]);
    expect(world.people[0].position).toEqual({ x: 1, y: 2 });
    expect(world.people[0]).toHaveProperty("route");
  });
  it("rejects missing revisions and invalid paths", () => {
    expect(() => applyWorldPatch(world, { ...patch, base_revision: 0 })).toThrow();
    expect(() => applyWorldPatch(world, { ...patch, operations: [] })).toThrow();
    expect(() =>
      applyWorldPatch(world, { ...patch, operations: [{ path: ["__proto__", "x"], value: 1 }] }),
    ).toThrow();
  });
});
