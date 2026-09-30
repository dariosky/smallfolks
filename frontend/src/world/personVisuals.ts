export type ActivityKind =
  | "sleep"
  | "read"
  | "garden"
  | "plant"
  | "call"
  | "chores"
  | "hobby"
  | "eat"
  | "shop"
  | "film"
  | "social"
  | "walk"
  | "ride"
  | "work"
  | "wait"
  | "cleanup"
  | "rest";

export function activityKind(activity?: string, role?: string): ActivityKind {
  const value = (activity ?? "").toLowerCase();
  if (value.startsWith("sleeping")) return "sleep";
  if (value.startsWith("reading")) return "read";
  if (value.startsWith("volunteering: planting trees")) return "plant";
  if (value.startsWith("tending the garden")) return "garden";
  if (value.startsWith("calling")) return "call";
  if (value.startsWith("doing household chores")) return "chores";
  if (value.startsWith("practising a hobby")) return "hobby";
  if (value.includes("breakfast") || value.includes("eating") || value.includes("cooking"))
    return "eat";
  if (value.startsWith("shopping")) return "shop";
  if (value.startsWith("watching a film")) return "film";
  if (value.startsWith("socializing")) return "social";
  if (value.startsWith("walking") || value.startsWith("heading home")) return "walk";
  if (value.startsWith("riding")) return "ride";
  if (value.startsWith("working")) return "work";
  if (value.startsWith("waiting")) return "wait";
  if (value.startsWith("needs cleanup")) return "cleanup";
  if (role && value.includes("work")) return "work";
  return "rest";
}

export const activityLabels: Record<ActivityKind, string> = {
  sleep: "Sleeping",
  read: "Reading",
  garden: "Gardening",
  plant: "Planting trees",
  call: "Calling",
  chores: "Chores",
  hobby: "Hobby",
  eat: "Eating",
  shop: "Shopping",
  film: "At the cinema",
  social: "Socializing",
  walk: "Walking",
  ride: "On the train",
  work: "Working",
  wait: "Waiting",
  cleanup: "Needs cleanup",
  rest: "Relaxing",
};

export type Appearance = {
  hair: "crop" | "sweep" | "bob" | "long" | "bun";
  hairColor: string;
  skinColor: string;
  outfit: string;
  outfitDark: string;
  glasses: boolean;
  freckles: boolean;
  skirt: boolean;
};

const hairColors = ["#47352f", "#78503a", "#ad7344", "#e1b46d", "#6e6764", "#2f3439"];
const skinColors = ["#f7cda4", "#eab58e", "#cb946d", "#a97554", "#79523e"];
const outfits = [
  ["#e97973", "#9d4e51"],
  ["#5d9ca9", "#3d6c79"],
  ["#e7b762", "#ae7c42"],
  ["#9d83ad", "#6c5b80"],
  ["#80a96c", "#567751"],
  ["#e39074", "#a96150"],
];
const hairstyles: Appearance["hair"][] = ["crop", "sweep", "bob", "long", "bun"];

function hash(value: string) {
  let result = 2166136261;
  for (const character of value) {
    result ^= character.charCodeAt(0);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
}

export function appearanceFor(personId: string, seed: number): Appearance {
  const base = `${seed}:${personId}`;
  const pick = (salt: string, length: number) => hash(`${base}:${salt}`) % length;
  const [outfit, outfitDark] = outfits[pick("outfit", outfits.length)];
  return {
    hair: hairstyles[pick("hair", hairstyles.length)],
    hairColor: hairColors[pick("hairColor", hairColors.length)],
    skinColor: skinColors[pick("skin", skinColors.length)],
    outfit,
    outfitDark,
    glasses: pick("glasses", 4) === 0,
    freckles: pick("freckles", 3) === 0,
    skirt: pick("silhouette", 2) === 0,
  };
}
