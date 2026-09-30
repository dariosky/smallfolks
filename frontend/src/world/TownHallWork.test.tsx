import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { World } from "../api/world";
import { TownHallWork } from "./TownHallWork";

const world = {
  people: [{ id: "person:one", name: "Elena", kind: "person", position: { x: 0, y: 0 } }],
  volunteering_projects: Array.from({ length: 10 }, (_, i) => ({
    id: `project:${i}`, person_id: "person:one", parcel_id: `parcel:${i}`, position: { x: 0, y: 0 },
    status: i === 9 ? "completed" : "active", worked_seconds: 3600, required_seconds: 14400,
    wage_cents: 2400, started_at: `2031-05-${String(i + 1).padStart(2, "0")}T09:00:00`,
  })),
} as World;

describe("TownHallWork", () => {
  it("shows the latest choices first with clickable names, progress, and payment", () => {
    const markup = renderToStaticMarkup(<TownHallWork world={world} onSelect={() => {}} />);
    expect((markup.match(/<li>/g) ?? []).length).toBe(8);
    expect(markup).not.toContain("Chosen 2031-05-01");
    expect(markup.indexOf("Chosen 2031-05-10")).toBeLessThan(markup.indexOf("Chosen 2031-05-09"));
    expect(markup).toContain("Elena");
    expect(markup).toContain("<button");
    expect(markup).toContain("60/240 minutes worked");
    expect(markup).toContain("€24.00 paid");
  });

  it("handles older snapshots with no projects or choice timestamps", () => {
    expect(renderToStaticMarkup(<TownHallWork world={{ ...world, volunteering_projects: undefined }} onSelect={() => {}} />)).toContain("No one has chosen sponsored work yet.");
    const legacy = { ...world, volunteering_projects: [{ ...world.volunteering_projects![0], started_at: undefined }] };
    const markup = renderToStaticMarkup(<TownHallWork world={legacy} onSelect={() => {}} />);
    expect(markup).toContain("Elena");
    expect(markup).not.toContain("Chosen");
  });
});
