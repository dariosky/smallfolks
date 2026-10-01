import { BuildingStatus } from "./BuildingStatus";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import type { World } from "../api/world";
import { BankDetails, HomeDevelopment, ResidentProsperity } from "./ProsperityDetails";
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
  it.each([
    ["05:59", true],
    ["06:00", false],
    ["18:59", false],
    ["19:00", true],
    ["23:59", true],
    ["00:00", true],
  ])("uses the town's day/night appearance at %s", (time, night) => {
    const markup = renderToStaticMarkup(
      <TownMap
        world={{ ...world, clock: `2031-05-21T${time}:00` }}
        selectedId={null}
        onSelect={() => {}}
      />,
    );
    expect(markup.includes("is-night")).toBe(night);
    expect(markup.includes('class="moon-doodle"')).toBe(night);
    expect(markup.includes('class="sun-doodle"')).toBe(!night);
  });

  it("turns normal and sports cars from left to up by 90 degrees", async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      disconnect() {}
    });
    const container = document.createElement("div");
    const root = createRoot(container);
    const renderHeading = (heading: number) => <TownMap world={{ ...world, people: [], vehicles: ["standard", "sports"].map((model, index) => ({
      id: `vehicle:${model}`, kind: "vehicle", name: model, model: model === "sports" ? "sports" as const : undefined,
      position: { x: 300 + index * 60, y: 200 }, heading,
    })) }} selectedId={null} onSelect={() => {}} />;
    try {
      await act(async () => root.render(renderHeading(180)));
      await act(async () => root.render(renderHeading(-90)));
      const cars = container.querySelectorAll<SVGGElement>(".vehicle-body");
      expect(cars.length).toBe(2);
      for (const car of cars) expect(car.style.transform).toBe("rotate(270deg)");
    } finally {
      await act(async () => root.unmount());
      vi.unstubAllGlobals();
    }
  });
  it("shows an in-car resident through the moving vehicle without a second street sprite", () => {
    const markup = renderToStaticMarkup(
      <TownMap
        world={{
          ...world,
          people: [{ ...world.people[0], id: "person:lea", name: "Lea", in_vehicle_id: "vehicle:lea" }],
          vehicles: [{
            id: "vehicle:lea", kind: "vehicle", name: "Lea's car",
            position: { x: 300, y: 200 }, state: "driving", driver_id: "person:lea", heading: 90, palette: "blue",
          }],
        }}
        selectedId="person:lea"
        onSelect={() => {}}
      />,
    );
    expect(markup).toContain("Lea driving");
    expect(markup).toContain("vehicle-driver");
    expect(markup).toContain('class="vehicle-body" transform="rotate(90)"');
    expect(markup).toContain('class="entity-hit vehicle-hit" x="-22" y="-14" width="44" height="28"');
    expect(markup).toContain('class="vehicle-selection-ring" x="-22" y="-14" width="44" height="28"');
    expect(markup).not.toContain('class="entity-hit" r="25"');
    expect(markup).toContain("palette-blue");
    expect((markup.match(/class="vehicle-wheel"/g) ?? []).length).toBe(4);
    expect(markup).toContain("vehicle-windshield");
    expect(markup).not.toContain('class="map-entity person');
  });

  it("renders sports cars from above with jewel paints, a spoiler and four wheels", () => {
    const paints = ["ruby", "sapphire", "emerald", "amethyst", "champagne"];
    const markup = renderToStaticMarkup(
      <TownMap world={{ ...world, people: [], vehicles: paints.map((palette, index) => ({
        id: `vehicle:sports-${index}`, kind: "vehicle", name: "Luxury sports car", model: "sports" as const,
        palette, state: "parked", position: { x: 100 + index * 60, y: 200 }, heading: 90,
      })) }} selectedId={null} onSelect={() => {}} />,
    );
    for (const paint of paints) expect(markup).toContain(`palette-${paint}`);
    expect((markup.match(/class="sports-car-spoiler"/g) ?? []).length).toBe(5);
    expect((markup.match(/class="vehicle-wheel"/g) ?? []).length).toBe(20);
    expect(markup).toContain('class="vehicle-body sports-car-body" transform="rotate(90)"');
    const fallback = renderToStaticMarkup(
      <TownMap world={{ ...world, people: [], vehicles: [{ id: "vehicle:invalid-paint", kind: "vehicle", name: "Luxury", model: "sports", palette: "brown", position: { x: 200, y: 200 } }] }} selectedId={null} onSelect={() => {}} />,
    );
    expect(fallback).toContain("palette-ruby");
    expect(fallback).not.toContain("palette-brown");
  });

  it("uses the server rail path and shows a waiting station queue", () => {
    const markup = renderToStaticMarkup(
      <TownMap
        world={{
          ...world,
          people: [],
          station_queues: [{ station_id: "station:market", entries: [
            { person_id: "person:one", arrived_at_seconds: 0, destination_station_id: "station:eastgate" },
            { person_id: "person:two", arrived_at_seconds: 15, destination_station_id: "station:eastgate" },
          ] }],
          trains: [{
            id: "train:folk-loop",
            name: "Folk Loop",
            stops: ["Market Square", "Eastgate"],
            track: [
              { distance: 0, x: 450, y: 58 },
              { distance: 100, x: 550, y: 58 },
              { distance: 200, x: 450, y: 58 },
            ],
            stations: [{ id: "station:market", name: "Market Square", position: { x: 510, y: 58 }, platform: { x: -120, y: -9, width: 160, height: 18 } }],
            state: {
              distance: 60, at_station: "station:market", service_state: "boarding",
              doors_open: true, service_hours: { starts_at: "06:00", ends_at: "00:00" },
              capacity: 8, car_capacity: 4, passenger_ids: [], stations: [],
              carriages: [],
            },
          }],
        }}
        selectedId={null}
        onSelect={() => {}}
      />,
    );
    expect(markup).toContain('points="450,58 550,58 450,58"');
    expect(markup).toContain("2 waiting");
    expect(markup).toContain("1. person:one in boarding queue");
    expect(markup).toContain("2. person:two in boarding queue");
    expect(markup).toContain("train-open-door");
    expect(markup).not.toContain("train-bogies");
    expect(markup).toContain("train-skylight");
    expect(markup).toContain("train-roof-vents");
  });

  it("renders activity cues and separates residents sharing a position", () => {
    const markup = renderToStaticMarkup(
      <TownMap world={world} selectedId={null} onSelect={() => {}} />,
    );
    expect(markup).toContain("Reading");
    expect(markup).toContain("Sleeping");
    expect(markup).toContain("prop-book");
    expect(markup).toContain("sleep-bed");
    expect(markup).toContain("sleep-zzz");
    expect((markup.match(/class="sleep-z"/g) ?? []).length).toBe(3);
    expect(markup).toContain("translate(107px, 195px)");
    expect(markup).toContain("translate(133px, 205px)");
  });

  it("shows planting props only while the citizen is planting", () => {
    const renderActivity = (activity: string) => renderToStaticMarkup(
      <TownMap world={{ ...world, people: [{ ...world.people[0], activity }] }} selectedId={null} onSelect={() => {}} />,
    );
    const planting = renderActivity("Volunteering: planting trees");
    for (const cue of ["planting-sow", "planting-seed", "planting-can", "planting-water-drops", "planting-sapling"]) {
      expect(planting).toContain(cue);
    }
    expect(planting).toContain("Planting trees");
    expect(renderActivity("Walking to a town hall tree-planting parcel")).not.toContain("planting-scene");
  });

  it("gives civic buildings their own map symbols", () => {
    const places = [
      ["post-office", "Little Post"],
      ["cinema", "Clover Cinema"],
      ["school", "SmallFolks School"],
      ["clinic", "Oak Clinic"],
      ["library", "Willow Library"],
      ["lantern-bar", "The Lantern Bar"],
      ["restaurant", "The Olive Table"],
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
      "landmark-restaurant",
    ]) {
      expect(markup).toContain(symbol);
    }
  });

  it("renders driveway homes as country houses with gardens and an open parking lane", () => {
    const home = {
      id: "place:rowan-2", name: "Rowan House 2", kind: "home",
      position: { x: 190, y: 100 }, house_style: "large" as const,
      driveway: { parking_position: { x: 238, y: 112 }, road_position: { x: 238, y: 170 } },
    };
    const markup = renderToStaticMarkup(
      <TownMap world={{ ...world, places: [home], people: [] }} selectedId={home.id} onSelect={() => {}} />,
    );
    expect(markup).toContain('class="driveway-paving" d="M48 -12V70L48 70"');
    expect(markup).toContain('class="illustrated-building estate-house"');
    expect(markup).toContain("Landscaped front garden");
    expect(markup).toContain("estate-porch-columns");
    expect(markup).toContain("estate-dormer");
    expect(markup).toContain('class="house-selection-ring" x="-55" y="-81" width="118"');
  });

  it("shows persisted building progress and the bank's loan details", () => {
    const home = { id: "place:home", name: "Home", kind: "home", position: { x: 95, y: 100 }, construction_project_id: "construction:home" };
    const developmentWorld: World = {
      ...world,
      places: [home, { id: "place:bank", name: "Willow Bank", kind: "workplace", position: { x: 1010, y: 285 } }],
      people: [{ ...world.people[0], credit_score: 615 }],
      construction_projects: [{ id: "construction:home", home_place_id: home.id, buyer_id: world.people[0].id, worker_id: null, status: "queued", worked_seconds: 3600, required_seconds: 28800, includes_driveway: true, cost_cents: 150000 }],
      loans: [{ id: "loan:one", borrower_id: world.people[0].id, purpose: "home_expansion", principal_cents: 60000, interest_cents: 4800, interest_percent: 8, remaining_cents: 64800, installment_cents: 1080, next_payment_date: "2031-05-14", term_days: 60, status: "overdue", missed_payments: 1, arrears_cents: 1080 }],
    };
    const map = renderToStaticMarkup(<TownMap world={developmentWorld} selectedId={null} onSelect={() => {}} />);
    expect(map).toContain("House construction 13% complete");
    expect(map).toContain("landmark-bank");
    const bank = renderToStaticMarkup(<BankDetails world={developmentWorld} />);
    expect(bank).toContain("Reader");
    expect(bank).toContain("8% fixed interest over 60 days");
    expect(bank).toContain("Overdue:");
    const resident = renderToStaticMarkup(<ResidentProsperity world={developmentWorld} person={developmentWorld.people[0]} />);
    expect(resident).toContain("615");
    expect(resident).toContain("home expansion loan:");
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
        world={{ ...world, places: [home], people: [{ ...world.people[0], target_place_id: home.id }] }}
        selectedId={home.id}
        onSelect={() => {}}
      />,
    );
    expect(markup).toContain('class="house-selection-ring" x="-41" y="-54" width="82" height="94"');
    expect(markup).toContain('class="chimney-smoke"');
  });
});

it("shows south-facing shop steps and narrow access lanes without street markings", () => {
  const markup = renderToStaticMarkup(
    <TownMap
      world={{ ...world, people: [],
        places: [{ id: "place:bakery", name: "Bakery", kind: "bakery", position: { x: 510, y: 135 } }],
        roads: [{ id: "road:access-place:bakery", points: [[510, 235], [510, 169]] }],
      }}
      selectedId={null}
      onSelect={() => {}}
    />,
  );
  expect(markup).toContain('class="road road-access"');
  expect(markup).not.toContain('class="road-marking"');
  expect(markup).toContain('aria-label="South-facing entrance"');
});

it("renders a walled mansion with two parking bays and shows its villa price and saving goal", () => {
  const mansion = {
    id: "place:cedar-villa", name: "Cedar Grove Villa", kind: "home", house_style: "mansion" as const,
    position: { x: 250, y: 1160 }, sale_price_cents: 1_500_000,
    driveway: { parking_position: { x: 332, y: 1228 }, parking_positions: [{ x: 332, y: 1228 }, { x: 364, y: 1228 }], road_position: { x: 250, y: 1370 } },
  };
  const mansionWorld = { ...world, places: [mansion], map_size: { width: 1200, height: 1450 }, people: [] };
  const markup = renderToStaticMarkup(<TownMap world={mansionWorld} selectedId={mansion.id} onSelect={() => {}} />);
  expect(markup).toContain('viewBox="0 -100 1200 1650"');
  expect(markup).toContain('class="mansion-estate"');
  expect(markup).toContain("Two driveway parking spaces");
  expect(markup).toContain("South-facing driveway gate");
  expect(markup).toContain("mansion-front-wall");
  expect(markup).toContain('class="house-selection-ring" x="-160"');
  const details = renderToStaticMarkup(<HomeDevelopment world={mansionWorld} home={mansion} />);
  expect(details).toContain("Upper-class villa");
  expect(details).toContain("Vast walled garden");
  expect(details).toContain("€15,000.00");
  const buyer = { ...world.people[0], investment_goal: "mansion" as const, investment_target_cents: 1_500_000, aspiration: "Saving for an upper-class villa." };
  const saving = renderToStaticMarkup(<ResidentProsperity world={mansionWorld} person={buyer} />);
  expect(saving).toContain("Villa price:");
  expect(saving).toContain("€15,000.00");
});


describe("building operations", () => {
  const state = {
    is_open: false, status: "Closed — day off", reason: "No shifts scheduled today.",
    closed_since: "2031-05-16T17:00:00", next_open_at: "2031-05-19T08:00:00",
  };
  it("shows closure details in the inspector including dates and the next shift", () => {
    const markup = renderToStaticMarkup(<BuildingStatus state={state} />);
    expect(markup).toContain("Closed — day off");
    expect(markup).toContain("No shifts scheduled today.");
    expect(markup).toContain("May 16, 2031");
    expect(markup).toContain("May 19, 2031");
    expect(markup).toContain("Next scheduled opening:");
    const unknown = renderToStaticMarkup(<BuildingStatus state={{ ...state, closed_since: null }} />);
    expect(unknown).toContain("Closure time was not recorded.");
  });
  it("removes smoke and adds a sign when a working building closes", () => {
    const library = { id: "place:library", name: "Willow Library", kind: "workplace", position: { x: 535, y: 590 }, operating_state: state };
    const closed = renderToStaticMarkup(<TownMap world={{ ...world, places: [library] }} selectedId={null} onSelect={() => {}} />);
    expect(closed).not.toContain('class="chimney-smoke"');
    expect(closed).toContain('class="building-closed-sign"');
    expect(closed).toContain("Willow Library, workplace, Closed — day off");
    const open = renderToStaticMarkup(<TownMap world={{ ...world, places: [{ ...library, operating_state: { ...state, is_open: true, status: "Open", closed_since: null, next_open_at: null } }] }} selectedId={null} onSelect={() => {}} />);
    expect(open).toContain('class="chimney-smoke"');
    expect(open).not.toContain('class="building-closed-sign"');
  });
});


it("keeps completed loans visible in the bank history alongside outstanding loans", () => {
  const loan = {
    id: "loan:old", borrower_id: world.people[0].id, purpose: "car", principal_cents: 60000,
    interest_cents: 4800, interest_percent: 8, remaining_cents: 0, installment_cents: 1080,
    next_payment_date: "2031-07-12", term_days: 60, status: "repaid" as const,
    missed_payments: 0, arrears_cents: 0, issued_at: "2031-05-12T10:00:00", repaid_at: "2031-07-11T00:00:00",
  };
  const markup = renderToStaticMarkup(<BankDetails world={{ ...world, loans: [loan, { ...loan, id: "loan:new", status: "active", remaining_cents: 64800, repaid_at: undefined }] }} />);
  expect(markup).toContain("Loan history");
  expect(markup).toContain("2 issued · 1 repaid · 1 outstanding");
  expect(markup).toContain("Completed: 2031-07-11");
  expect(markup).toContain("Issued: 2031-05-12");
  expect(markup).toContain("Borrowed:");
  expect(markup).toContain("car loan:</strong> repaid");
  expect(markup).toContain("car loan:</strong> active");
});

it("culls off-camera sprites in a 500-resident city without losing the population count", () => {
  const people = Array.from({ length: 500 }, (_, index) => ({
    ...world.people[0],
    id: `person:${index}`,
    name: `Resident ${index}`,
    position: { x: 560 + index % 10 * 8, y: index < 20 ? 200 + index : 2200 },
  }));
  const markup = renderToStaticMarkup(
    <TownMap
      world={{ ...world, people, map_size: { width: 1200, height: 3000 } }}
      zoom={4}
      position={{ x: 0, y: -1140 }}
      selectedId={null}
      onSelect={() => {}}
    />,
  );
  expect((markup.match(/class="map-entity /g) ?? []).length).toBe(20);
  expect(markup).toContain("500 neighbours");
  expect(markup).toContain("is-dense");
  expect(markup).not.toContain("Resident 499,");
});

describe("tree selection", () => {
  beforeEach(() => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
  });
  afterEach(() => vi.unstubAllGlobals());
  it("selects planted and scenery trees by mouse and keyboard", async () => {
    const planted = {
      id: "tree:planted",
      kind: "tree" as const,
      name: "Town tree",
      position: { x: 45, y: 65 },
      planted_at: "2026-09-28T08:00:00",
      planted_by_id: "person:reader",
      planting_reason: "volunteering" as const,
    };
    const scenery = { ...planted, id: "tree:scenery:335:80", position: { x: 335, y: 80 } };
    const onSelect = vi.fn();
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    try {
      await act(async () =>
        root.render(
          <TownMap
            world={{ ...world, planted_trees: [planted], scenery_trees: [scenery] }}
            selectedId={planted.id}
            onSelect={onSelect}
          />,
        ),
      );
      const buttons = container.querySelectorAll(".map-tree");
      expect(buttons).toHaveLength(2);
      expect(buttons[0].getAttribute("aria-pressed")).toBe("true");
      await act(async () => buttons[0].dispatchEvent(new MouseEvent("click", { bubbles: true })));
      expect(onSelect).toHaveBeenLastCalledWith(planted);
      await act(async () =>
        buttons[1].dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })),
      );
      expect(onSelect).toHaveBeenLastCalledWith(scenery);
    } finally {
      await act(async () => root.unmount());
      container.remove();
    }
  });

  it("selects garden trees without selecting their house", async () => {
    const onSelect = vi.fn();
    const container = document.createElement("div");
    const root = createRoot(container);
    const home = {
      id: "place:estate",
      name: "Estate",
      kind: "home",
      position: { x: 400, y: 300 },
      house_style: "mansion" as const,
    };
    try {
      await act(async () =>
        root.render(
          <TownMap world={{ ...world, places: [home] }} selectedId={null} onSelect={onSelect} />,
        ),
      );
      const buttons = container.querySelectorAll(".map-tree");
      expect(buttons).toHaveLength(4);
      await act(async () => buttons[0].dispatchEvent(new MouseEvent("click", { bubbles: true })));
      expect(onSelect).toHaveBeenCalledTimes(1);
      expect(onSelect).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "tree", id: "tree:place:estate:0" }),
      );
    } finally {
      await act(async () => root.unmount());
    }
  });
});
