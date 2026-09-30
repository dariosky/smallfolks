import type { World } from "./world";

export type WorldPatch = {
  type: "patch";
  base_revision: number;
  revision: number;
  operations: { path: (string | number)[]; value?: unknown; deleted?: boolean }[];
};

export function applyWorldPatch(world: World, patch: WorldPatch): World {
  if (patch.base_revision !== world.revision || patch.revision <= world.revision) {
    throw new Error("World stream revision mismatch");
  }
  // Clone each touched container once, retaining every untouched object reference.
  const copies = new Map<object, Record<string | number, unknown>>();
  function copy(value: unknown): Record<string | number, unknown> {
    if (!value || typeof value !== "object") throw new Error("Invalid patch path");
    const existing = copies.get(value);
    if (existing) return existing;
    const next = (Array.isArray(value) ? value.slice() : { ...value }) as Record<
      string | number,
      unknown
    >;
    copies.set(value, next);
    copies.set(next, next);
    return next;
  }
  const next = copy(world);
  for (const operation of patch.operations) {
    const path = operation.path;
    if (
      !path.length ||
      path.some((key) => ["__proto__", "constructor", "prototype"].includes(String(key)))
    ) {
      throw new Error("Invalid patch path");
    }
    let container = next;
    for (const key of path.slice(0, -1)) {
      container[key] = copy(container[key]);
      container = container[key] as Record<string | number, unknown>;
    }
    const key = path[path.length - 1];
    if (operation.deleted) delete container[key];
    else container[key] = operation.value;
  }
  if (next.revision !== patch.revision) throw new Error("Invalid patch revision");
  return next as World;
}
