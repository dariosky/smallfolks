import { getInitials } from "./getInitials";

describe("getInitials", () => {
  it("builds initials from the first two words", () => {
    expect(getInitials("North Star")).toBe("NS");
  });

  it("handles extra whitespace", () => {
    expect(getInitials("  Signal   Forge  ")).toBe("SF");
  });
});
