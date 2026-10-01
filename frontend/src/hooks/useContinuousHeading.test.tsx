import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";
import { useContinuousHeading } from "./useContinuousHeading";

describe("useContinuousHeading", () => {
  it("takes short turns across the angle seam in both directions and around repeated laps", async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    const container = document.createElement("div");
    const root = createRoot(container);
    function Heading({ heading }: { heading: number }) {
      return <span>{useContinuousHeading(heading)}</span>;
    }
    async function turn(heading: number, expected: number) {
      await act(async () => root.render(<Heading heading={heading} />));
      expect(Number(container.textContent)).toBe(expected);
    }
    try {
      await turn(180, 180);
      await turn(-90, 270); // Left to up is +90°, not -270°.
      await turn(180, 180); // Reverse across the same seam.
      for (let lap = 0; lap < 3; lap++) {
        for (const [heading, offset] of [[-90, 270], [0, 360], [90, 450], [180, 540]]) {
          await turn(heading, lap * 360 + offset);
        }
      }
      await turn(1260, 1260); // An equivalent angle should not cause a full spin.
    } finally {
      await act(async () => root.unmount());
    }
  });
});
