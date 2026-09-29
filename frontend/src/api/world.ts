// Vite development uses a separate origin. Production is served by FastAPI,
// so it deliberately retains the same-origin /api contract.
const API_PREFIX =
  import.meta.env.VITE_API_PREFIX || (import.meta.env.DEV ? "http://127.0.0.1:5340/api" : "/api");

export type Position = { x: number; y: number };
export type Place = { id: string; name: string; kind: string; position: Position };
export type RenderEntity = {
  id: string;
  kind: "person" | "pet" | "vehicle";
  name: string;
  position: Position;
  state: string;
  palette: string;
};
export type World = {
  id: string;
  seed: number;
  clock: string;
  generation_version: string;
  simulation_version: string;
  places: Place[];
  roads: { id: string; points: number[][] }[];
  paths: { id: string; points: number[][] }[];
  people: Entity[];
  pets: Entity[];
  vehicles: Entity[];
  trains?: { id: string; name: string; stops: string[] }[];
  events: { at: string; summary: string }[];
};
export type Entity = {
  id: string;
  kind: string;
  name: string;
  position: Position;
  activity?: string;
  state?: string;
  target_place_id?: string;
  explanation?: string;
  next_commitment?: string;
  needs?: Record<string, number>;
  role?: string;
  route?: Position[];
  train_departure_id?: string;
  train_arrival_id?: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`The town service returned ${response.status}.`);
  }
  return (await response.json()) as T;
}

export function createWorld(seed = 7341) {
  return request<World>("/worlds", {
    method: "POST",
    body: JSON.stringify({ seed }),
  });
}

export function advanceWorld(worldId: string, minutes: number) {
  return request<World>(`/worlds/${worldId}/advance`, {
    method: "POST",
    body: JSON.stringify({ minutes }),
  });
}
