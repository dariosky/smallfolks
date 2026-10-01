import { describe, expect, it } from "vitest";
import { activityKind, appearanceFor } from "./personVisuals";

describe("resident visuals", () => {
  it.each([
    "marco", "tom", "diego", "lucas", "bruno", "hugo", "paolo",
    "oliver", "leo", "mateo", "felix", "noah", "oscar", "sam", "restaurant-dinner",
  ])("keeps %s's authored short hairstyle and trousers across world seeds", (resident) => {
    for (const seed of [42, 7341, 98765]) {
      const appearance = appearanceFor(`person:${resident}`, seed);
      expect(["crop", "sweep"]).toContain(appearance.hair);
      expect(appearance.skirt).toBe(false);
    }
  });

  it("gives Lucas a cropped hairstyle", () => {
    expect(appearanceFor("person:lucas", 7341).hair).toBe("crop");
  });

  it.each([
    ["Sleeping at home", "sleep"],
    ["Reading at home", "read"],
    ["Tending the garden", "garden"],
    ["Volunteering: planting trees", "plant"],
    ["Walking to a town hall tree-planting parcel", "walk"],
    ["Calling a friend", "call"],
    ["Doing household chores", "chores"],
    ["Practising a hobby", "hobby"],
    ["Cooking and eating at home", "eat"],
    ["Shopping at Hearth Market", "shop"],
    ["Watching a film at Clover Cinema", "film"],
    ["Socializing at The Lantern Bar", "social"],
    ["Walking Pippin home", "walk"],
    ["Riding Folk Loop to Rowan Halt", "ride"],
    ["Working as baker", "work"],
    ["Waiting for Folk Loop", "wait"],
  ] as const)("maps %s to %s", (activity, expected) => {
    expect(activityKind(activity)).toBe(expected);
  });

  it("keeps an appearance stable across updates and varies residents", () => {
    const first = appearanceFor("person:elena", 7341);
    expect(appearanceFor("person:elena", 7341)).toEqual(first);
    const neighbours = Array.from({ length: 15 }, (_, i) => appearanceFor(`person:${i}`, 7341));
    expect(new Set(neighbours.map((person) => JSON.stringify(person))).size).toBeGreaterThan(10);
  });
});
