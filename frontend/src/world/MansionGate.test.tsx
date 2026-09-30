import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const roots: Root[] = [];
function render(node: ReactNode) {
  const container = document.createElement("div");
  const root = createRoot(container);
  roots.push(root);
  act(() => root.render(node));
  return {
    container,
    rerender(next: ReactNode) {
      act(() => root.render(next));
    },
  };
}
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { World } from "../api/world";
import { MansionGate } from "./MansionGate";

const gate = { x: 0, y: 0 };
const route = [
  { x: 0, y: 50 },
  { x: 0, y: -50 },
];
function traffic(y: number, vehicle = false): World {
  return {
    id: "gate-test",
    seed: 1,
    clock: "2031-05-12T09:00:00",
    generation_version: "test",
    simulation_version: "test",
    revision: 0,
    simulation: { elapsed_seconds: 0, presentation_time_seconds: 0, running: true, speed: 1 },
    places: [],
    households: [],
    roads: [],
    paths: [],
    events: [],
    pets: [],
    people: [
      {
        id: "person:visitor",
        kind: "person",
        name: "Visitor",
        position: { x: 0, y },
        route,
        ...(vehicle ? { in_vehicle_id: "vehicle:visitor" } : {}),
      },
    ],
    vehicles: vehicle
      ? [
          {
            id: "vehicle:visitor",
            kind: "vehicle",
            name: "Car",
            position: { x: 0, y },
            driver_id: "person:visitor",
            state: "driving",
          },
        ]
      : [],
  };
}
describe("mansion gate timing", () => {
  let now = 0;
  beforeEach(() => {
    vi.useFakeTimers();
    now = 0;
    vi.spyOn(performance, "now").mockImplementation(() => now);
  });
  afterEach(() => {
    act(() => roots.splice(0).forEach((root) => root.unmount()));
    vi.useRealTimers();
    vi.restoreAllMocks();
  });
  it.each([false, true])(
    "opens before a %s vehicle passage and closes after the last crossing",
    (vehicle) => {
      const view = render(
        <svg>
          <MansionGate world={traffic(40, vehicle)} gate={gate} />
        </svg>,
      );
      expect(view.container.querySelector(".mansion-gate")?.classList.contains("is-closed")).toBe(
        true,
      );
      now = 1000;
      view.rerender(
        <svg>
          <MansionGate world={traffic(30, vehicle)} gate={gate} />
        </svg>,
      );
      expect(view.container.querySelector(".mansion-gate")?.classList.contains("is-open")).toBe(
        true,
      );
      act(() => vi.advanceTimersByTime(2000));
      now = 3000;
      view.rerender(
        <svg>
          <MansionGate world={traffic(vehicle ? -40 : -10, vehicle)} gate={gate} />
        </svg>,
      );
      act(() => vi.advanceTimersByTime(2999));
      expect(view.container.querySelector(".mansion-gate")?.classList.contains("is-open")).toBe(
        true,
      );
      act(() => vi.advanceTimersByTime(1));
      expect(view.container.querySelector(".mansion-gate")?.classList.contains("is-closed")).toBe(
        true,
      );
    },
  );
  it("keeps the gate open when the simulation pauses with someone in the opening", () => {
    const view = render(
      <svg>
        <MansionGate world={traffic(40)} gate={gate} />
      </svg>,
    );
    now = 1000;
    view.rerender(
      <svg>
        <MansionGate world={traffic(30)} gate={gate} />
      </svg>,
    );
    const paused = traffic(0);
    paused.simulation.running = false;
    now = 2000;
    view.rerender(
      <svg>
        <MansionGate world={paused} gate={gate} />
      </svg>,
    );
    act(() => vi.advanceTimersByTime(4000));
    expect(view.container.querySelector(".mansion-gate")?.classList.contains("is-open")).toBe(true);
    now = 6000;
    view.rerender(
      <svg>
        <MansionGate world={traffic(-10)} gate={gate} />
      </svg>,
    );
    act(() => vi.advanceTimersByTime(3000));
    expect(view.container.querySelector(".mansion-gate")?.classList.contains("is-closed")).toBe(
      true,
    );
  });
  it("stays closed for stationary people beside the gate", () => {
    const view = render(
      <svg>
        <MansionGate world={traffic(1)} gate={gate} />
      </svg>,
    );
    now = 1000;
    view.rerender(
      <svg>
        <MansionGate world={traffic(1)} gate={gate} />
      </svg>,
    );
    expect(view.container.querySelector(".mansion-gate")?.classList.contains("is-closed")).toBe(
      true,
    );
  });
});
