import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { World } from "../api/world";
import { TownMap } from "./TownMap";

const world: World = {
  id: "world:test",
  seed: 7341,
  clock: "2026-09-29T21:00:00",
  generation_version: "test",
  simulation_version: "test",
  revision: 1,
  simulation: { elapsed_seconds: 0, presentation_time_seconds: 0, running: true, speed: 1 },
  places: [],
  households: [],
  roads: [],
  paths: [],
  pets: [],
  vehicles: [],
  events: [],
  people: [
    {
      id: "person:reader",
      kind: "person",
      name: "Reader",
      position: { x: 120, y: 200 },
      activity: "Reading at home",
      role: "Librarian",
    },
    {
      id: "person:sleeper",
      kind: "person",
      name: "Sleeper",
      position: { x: 120, y: 200 },
      activity: "Sleeping at home",
      role: "Teacher",
    },
  ],
};

describe("TownMap resident illustrations", () => {
  it("renders activity cues and separates residents sharing a position", () => {
    const markup = renderToStaticMarkup(
      <TownMap world={world} selectedId={null} onSelect={() => {}} />,
    );
    expect(markup).toContain("Reading");
    expect(markup).toContain("Sleeping");
    expect(markup).toContain("prop-book");
    expect(markup).toContain("sleep-bed");
    expect(markup).toContain("translate(107px, 195px)");
    expect(markup).toContain("translate(133px, 205px)");
  });

  it("gives civic buildings their own map symbols", () => {
    const places = [
      ["post-office", "Little Post"],
      ["cinema", "Clover Cinema"],
      ["school", "SmallFolks School"],
      ["clinic", "Oak Clinic"],
      ["library", "Willow Library"],
      ["lantern-bar", "The Lantern Bar"],
    ].map(([id, name], index) => ({
      id: `place:${id}`,
      name,
      kind: "workplace",
      position: { x: 120 + index * 150, y: 300 },
    }));
    const markup = renderToStaticMarkup(
      <TownMap world={{ ...world, places, people: [] }} selectedId={null} onSelect={() => {}} />,
    );
    for (const symbol of [
      "post-envelope",
      "cinema-marquee",
      "school-clock",
      "clinic-cross",
      "library-book",
      "bar-lantern",
    ]) {
      expect(markup).toContain(symbol);
    }
  });

  it("uses a fixed house selection ring that does not grow with chimney smoke", () => {
    const home = {
      id: "place:rowan-1",
      name: "Rowan House 1",
      kind: "home",
      position: { x: 95, y: 100 },
    };
    const markup = renderToStaticMarkup(
      <TownMap
        world={{ ...world, places: [home], people: [] }}
        selectedId={home.id}
        onSelect={() => {}}
      />,
    );
    expect(markup).toContain('class="house-selection-ring" x="-41" y="-54" width="82" height="94"');
    expect(markup).toContain('class="chimney-smoke"');
  });
});
