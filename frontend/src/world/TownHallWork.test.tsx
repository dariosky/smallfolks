import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { World } from "../api/world";
import { TownHallWork } from "./TownHallWork";

const world = {
  people: [
    {
      id: "person:one",
      name: "Elena",
      kind: "person",
      position: { x: 0, y: 0 },
    },
  ],
  volunteering_projects: Array.from({ length: 10 }, (_, i) => ({
    id: `project:${i}`,
    person_id: "person:one",
    parcel_id: `parcel:${i}`,
    position: { x: 0, y: 0 },
    status: i === 9 ? "completed" : "active",
    worked_seconds: 3600,
    required_seconds: 14400,
    wage_cents: 2400,
    started_at: `2031-05-${String(i + 1).padStart(2, "0")}T09:00:00`,
  })),
} as World;

describe("TownHallWork", () => {
  it("shows the latest choices first with clickable names, progress, and payment", () => {
    const markup = renderToStaticMarkup(
      <TownHallWork world={world} onSelect={() => {}} />,
    );
    expect((markup.match(/<li>/g) ?? []).length).toBe(8);
    expect(markup).not.toContain("Chosen 2031-05-01");
    expect(markup.indexOf("Chosen 2031-05-10")).toBeLessThan(
      markup.indexOf("Chosen 2031-05-09"),
    );
    expect(markup).toContain("Elena");
    expect(markup).toContain("<button");
    expect(markup).toContain("60/240 minutes worked");
    expect(markup).toContain("€24.00 paid");
  });

  it("shows grants, support recipients, and the new task kinds", () => {
    const funded = {
      ...world,
      clock: "2031-05-10T12:00:00",
      economy: {
        treasury_cents: 10000,
        household_contribution_percent: 50,
        ledger: [],
        public_budget_date: "2031-05-10",
        regional_grant_today_cents: 30000,
        regional_grant_total_cents: 50000,
        support_today_cents: 2400,
        support_total_cents: 4800,
        community_work_cents: 600,
      },
      people: [{ ...world.people[0], support_paid_date: "2031-05-10" }],
      volunteering_projects: [
        {
          ...world.volunteering_projects![0],
          kind: "library_help" as const,
          required_seconds: 3600,
          worked_seconds: 900,
          wage_cents: 600,
        },
      ],
    };
    const markup = renderToStaticMarkup(
      <TownHallWork world={funded} onSelect={() => {}} />,
    );
    expect(markup).toContain("€300.00 today");
    expect(markup).toContain("€500.00 total");
    expect(markup).toContain("Received today:");
    expect(markup).toContain("€24.00 today");
    expect(markup).toContain("Library help · 15/60 minutes worked");
    expect(markup).toContain("Park cleanup · 1 hour · €6");
    expect(markup).toContain("Community gardening · 2 hours · €12");
    expect(markup).toContain("Optional work earns extra");
    const nextDay = renderToStaticMarkup(
      <TownHallWork
        world={{ ...funded, clock: "2031-05-11T00:00:00" }}
        onSelect={() => {}}
      />,
    );
    expect(nextDay).toContain("€0.00 today");
    expect(nextDay).toContain("No unemployment support paid today.");
  });

  it("shows paid handymen and municipal progress separately from volunteer stipends", () => {
    const municipal = {
      ...world,
      volunteering_projects: [],
      people: [
        {
          ...world.people[0],
          role: "Town handyman",
          workplace_id: "place:townhall",
          activity: "Town work: cleaning the park",
        },
      ],
      municipal_projects: [
        {
          id: "municipal:1",
          person_id: "person:one",
          kind: "park_cleanup" as const,
          site_id: "place:park",
          position: { x: 0, y: 0 },
          status: "active" as const,
          worked_seconds: 900,
          required_seconds: 3600,
          started_at: "2031-05-19T09:00:00",
        },
      ],
    };
    const markup = renderToStaticMarkup(
      <TownHallWork world={municipal} onSelect={() => {}} />,
    );
    expect(markup).toContain("Town handymen");
    expect(markup).toContain("€12/hour for work on site");
    expect(markup).toContain("below 50%");
    expect(markup).toContain("Park cleanup · 15/60 minutes worked");
    expect(markup).toContain("Town work: cleaning the park");
    expect(markup).toContain("No one has chosen sponsored work yet.");
  });

  it("handles older snapshots with no projects or choice timestamps", () => {
    expect(
      renderToStaticMarkup(
        <TownHallWork
          world={{ ...world, volunteering_projects: undefined }}
          onSelect={() => {}}
        />,
      ),
    ).toContain("No one has chosen sponsored work yet.");
    const legacy = {
      ...world,
      volunteering_projects: [
        { ...world.volunteering_projects![0], started_at: undefined },
      ],
    };
    const markup = renderToStaticMarkup(
      <TownHallWork world={legacy} onSelect={() => {}} />,
    );
    expect(markup).toContain("Elena");
    expect(markup).not.toContain("Chosen");
  });
});
