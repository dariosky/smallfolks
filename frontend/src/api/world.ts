// Vite development uses a separate origin. Production is served by FastAPI,
// so it deliberately retains the same-origin /api contract.
const API_PREFIX =
  import.meta.env.VITE_API_PREFIX || (import.meta.env.DEV ? "http://127.0.0.1:5340/api" : "/api");

export type Position = { x: number; y: number };
export type Place = { id: string; name: string; kind: string; position: Position };
export type Household = {
  id: string;
  home_place_id: string;
  member_ids: string[];
  food_servings: number;
};
export type Train = {
  id: string;
  name: string;
  stops: string[];
  state?: {
    distance: number;
    at_station: string | null;
    passenger_ids: string[];
    carriages: { id: string; passenger_ids: string[] }[];
  };
};
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
  revision: number;
  simulation: {
    elapsed_seconds: number;
    presentation_time_seconds: number;
    running: boolean;
    speed: number;
  };
  places: Place[];
  households: Household[];
  roads: { id: string; points: number[][] }[];
  paths: { id: string; points: number[][] }[];
  people: Entity[];
  pets: Entity[];
  vehicles: Entity[];
  trains?: Train[];
  events: { at: string; summary: string }[];
};
export type Entity = {
  id: string;
  kind: string;
  name: string;
  position: Position;
  palette?: string;
  activity?: string;
  state?: string;
  target_place_id?: string;
  explanation?: string;
  next_commitment?: string;
  needs?: Record<string, number>;
  walk_status?: string;
  accident_at_home?: boolean;
  social_inclination?: number;
  cinema_inclination?: number;
  household_id?: string;
  carrying_groceries?: boolean;
  role?: string;
  route?: Position[];
  train_departure_id?: string;
  train_arrival_id?: string;
  on_train?: boolean;
  train_car_index?: number;
  train_seat_index?: number;
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

export function advanceWorld(worldId: string, minutes: number, expectedRevision?: number) {
  return request<World>(`/worlds/${worldId}/advance`, {
    method: "POST",
    body: JSON.stringify({ minutes, expected_revision: expectedRevision }),
  });
}

export function getWorld(worldId: string) {
  return request<World>(`/worlds/${worldId}`);
}

export function setWorldRunning(
  worldId: string,
  running: boolean,
  speed: number,
  expectedRevision: number,
) {
  return request<World>(`/worlds/${worldId}/run`, {
    method: "POST",
    body: JSON.stringify({ running, speed, expected_revision: expectedRevision }),
  });
}
