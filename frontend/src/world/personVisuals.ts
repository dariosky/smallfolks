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
  if (value.startsWith("town work: planting trees")) return "plant";
  if (value.startsWith("town work: cleaning the park")) return "chores";
  if (value.startsWith("town work: helping at the library")) return "read";
  if (value.startsWith("town work: visiting a resident")) return "social";
  if (value.startsWith("volunteering: planting trees")) return "plant";
  if (value.startsWith("volunteering: community gardening")) return "garden";
  if (value.startsWith("volunteering: cleaning the park")) return "chores";
  if (value.startsWith("volunteering: helping at the library")) return "read";
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

// Authored character designs for the town's named cast, independent of world seed.
const residentDesigns: Record<string, Pick<Appearance, "hair" | "skirt">> = {
  "person:elena": { hair: "bun", skirt: false },
  "person:marco": { hair: "crop", skirt: false },
  "person:lea": { hair: "bob", skirt: true },
  "person:tom": { hair: "sweep", skirt: false },
  "person:ana": { hair: "bun", skirt: false },
  "person:diego": { hair: "crop", skirt: false },
  "person:sofia": { hair: "long", skirt: true },
  "person:lucas": { hair: "crop", skirt: false },
  "person:nora": { hair: "bob", skirt: false },
  "person:bruno": { hair: "sweep", skirt: false },
  "person:marta": { hair: "bun", skirt: false },
  "person:hugo": { hair: "crop", skirt: false },
  "person:irene": { hair: "long", skirt: true },
  "person:paolo": { hair: "sweep", skirt: false },
  "person:clara": { hair: "bob", skirt: true },
  "person:alice": { hair: "bob", skirt: false },
  "person:oliver": { hair: "sweep", skirt: false },
  "person:emma": { hair: "long", skirt: false },
  "person:leo": { hair: "crop", skirt: false },
  "person:isabel": { hair: "bun", skirt: false },
  "person:mateo": { hair: "sweep", skirt: false },
  "person:eva": { hair: "bob", skirt: true },
  "person:felix": { hair: "crop", skirt: false },
  "person:maya": { hair: "bun", skirt: false },
  "person:noah": { hair: "sweep", skirt: false },
  "person:ada": { hair: "bob", skirt: false },
  "person:sara": { hair: "bun", skirt: false },
  "person:oscar": { hair: "crop", skirt: false },
  "person:julia": { hair: "long", skirt: true },
  "person:sam": { hair: "sweep", skirt: false },
  "person:restaurant-lunch": { hair: "bun", skirt: false },
  "person:restaurant-dinner": { hair: "crop", skirt: false },
};

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
  const design = residentDesigns[personId];
  return {
    hair: design?.hair ?? hairstyles[pick("hair", hairstyles.length)],
    hairColor: hairColors[pick("hairColor", hairColors.length)],
    skinColor: skinColors[pick("skin", skinColors.length)],
    outfit,
    outfitDark,
    glasses: pick("glasses", 4) === 0,
    freckles: pick("freckles", 3) === 0,
    skirt: design?.skirt ?? pick("silhouette", 2) === 0,
  };
}
