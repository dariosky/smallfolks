import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { World } from "../api/world";
import { CommunityWorkVisuals } from "./CommunityWorkVisuals";

describe("community improvements", () => {
  it("shows saved flowerbeds and park cleanliness on the map", () => {
    const world = {
      places: [
        {
          id: "park",
          name: "Mossy Common",
          kind: "park",
          position: { x: 20, y: 30 },
          cleanliness: 80,
        },
      ],
      community_gardens: [{ id: "garden", position: { x: 40, y: 50 } }],
    } as World;
    const markup = renderToStaticMarkup(
      <svg>
        <CommunityWorkVisuals world={world} />
      </svg>,
    );
    expect(markup).toContain("Community flowerbed");
    expect(markup).toContain("translate(40 50)");
    expect(markup).toContain("Mossy Common cleanliness 80%");
    expect(markup).toContain("Cleanliness 80%");
  });
  it("handles older saves without improvement fields", () => {
    expect(
      renderToStaticMarkup(
        <svg>
          <CommunityWorkVisuals world={{ places: [] } as unknown as World} />
        </svg>,
      ),
    ).not.toContain("Community flowerbed");
  });
});
