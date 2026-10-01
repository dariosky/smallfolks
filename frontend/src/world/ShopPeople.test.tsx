import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Entity, Place } from "../api/world";
import { ShopPeople } from "./ShopPeople";

const place: Place = { id: "shop:test", kind: "shop", name: "Shop", position: { x: 100, y: 100 } };
const person = (name: string, fields: Partial<Entity> = {}): Entity => ({
  id: name, name, kind: "person", position: { x: 100, y: 131 }, activity: "Shopping", ...fields,
});
const render = (people: Entity[]) => renderToStaticMarkup(<ShopPeople place={place} people={people} onSelect={() => {}} />);

describe("ShopPeople", () => {
  it("shows assigned employees even away, and visitors only after arrival", () => {
    const markup = render([
      person("Worker", { workplace_id: place.id, role: "Florist" }),
      person("Customer", { target_place_id: place.id }),
      person("Walker", { target_place_id: place.id, route: [{ x: 100, y: 131 }] }),
      person("Direct walker", { target_place_id: place.id, direct_walk: {} }),
      person("Driver", { target_place_id: place.id, in_vehicle_id: "car" }),
      person("Train rider", { target_place_id: place.id, on_train: true }),
      person("Distant", { target_place_id: place.id, position: { x: 900, y: 900 } }),
      person("Unemployed", { workplace_id: place.id, employment_status: "out of work" }),
    ]);
    expect(markup).toContain("Worker");
    expect(markup).toContain("Florist · Away");
    expect(markup).toContain("Customer");
    for (const name of ["Walker", "Direct walker", "Driver", "Train rider", "Distant", "Unemployed"]) expect(markup).not.toContain(name);
  });

  it("marks an employee present and provides clear empty states", () => {
    const markup = render([person("Worker", { workplace_id: place.id, target_place_id: place.id })]);
    expect(markup).toContain("Employee · Here now");
    expect(markup.match(/<span>Worker<\/span>/g)).toHaveLength(1);
    expect(markup).toContain("No visitors are here right now.");
    expect(render([])).toContain("No current employees.");
    expect(render([])).toContain("No visitors are here right now.");
  });

  it("lists present employees once while keeping visitors in Here now", () => {
    const markup = render([
      person("Worker", { workplace_id: place.id, target_place_id: place.id }),
      person("Customer", { target_place_id: place.id }),
    ]);
    const [employees, visitors] = markup.split('<p class="eyebrow">Here now</p>');
    expect(employees).toContain("Worker");
    expect(employees).toContain("Employee · Here now");
    expect(visitors).toContain("Customer");
    expect(visitors).not.toContain("Worker");
  });
});
