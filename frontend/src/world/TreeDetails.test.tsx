import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { TreeDetails } from "./TreeDetails";
import type { Tree } from "../api/world";

const tree: Tree = {
  id: "tree:test",
  kind: "tree",
  name: "Town tree",
  position: { x: 45, y: 65 },
  planted_at: "2031-05-12T09:00:00",
  planted_by_id: "person:maya",
  planted_by_name: "Maya Chen",
  planting_reason: "town_employee",
};

describe("tree history", () => {
  it("uses the simulation clock for age and keeps the recorded planter name", () => {
    const markup = renderToStaticMarkup(
      <TreeDetails tree={tree} clock="2031-05-15T09:00:00" people={[]} onSelect={() => {}} />,
    );
    expect(markup).toContain("3 days since planting");
    expect(markup).toContain("Maya Chen");
    expect(markup).toContain("Town employee");
  });
  it("shows volunteering and honest unknown history", () => {
    const volunteer = renderToStaticMarkup(
      <TreeDetails
        tree={{ ...tree, planting_reason: "volunteering" }}
        clock="2031-05-12T10:00:00"
        people={[]}
        onSelect={() => {}}
      />,
    );
    expect(volunteer).toContain("Planted today");
    expect(volunteer).toContain("Volunteering work");
    const existing = renderToStaticMarkup(
      <TreeDetails
        tree={{
          ...tree,
          planted_at: null,
          planted_by_id: null,
          planted_by_name: null,
          planting_reason: "existing_landscape",
        }}
        clock="2031-05-12T10:00:00"
        people={[]}
        onSelect={() => {}}
      />,
    );
    expect(existing).toContain("planting date was not recorded");
    expect(existing).toContain("planting history unknown");
    expect(existing).not.toContain("Maya Chen");
  });
});
