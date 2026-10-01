// Vite development uses a separate origin. Production is served by FastAPI,
// so it deliberately retains the same-origin /api contract.
const API_PREFIX =
  import.meta.env.VITE_API_PREFIX || (import.meta.env.DEV ? "http://127.0.0.1:5340/api" : "/api");

export function worldStreamUrl(worldId: string) {
  const url = new URL(`${API_PREFIX}/worlds/${encodeURIComponent(worldId)}/stream`, window.location.href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.href;
}

export type Position = { x: number; y: number };
export type BuildingOperatingState = {
  is_open: boolean;
  status: string;
  reason: string;
  closed_since: string | null;
  next_open_at: string | null;
};
export type Place = { cleanliness?: number; cleanup_sessions?: number; library_help_sessions?: number; operating_state?: BuildingOperatingState; id: string; name: string; kind: string; position: Position; estate_gate?: Position; dealership?: { balance_cents: number; cars_sold: number; standard_price_cents: number; sports_price_cents: number }; house_style?: "large" | "mansion"; owner_household_id?: string | null; sale_price_cents?: number; construction_project_id?: string; driveway?: { parking_position: Position; parking_positions?: Position[]; road_position: Position }; business?: {
  balance_cents: number;
  closed_at?: string | null;
  closure_reason?: string;
  status: string;
  debt_cents: number;
  owner_id: string | null;
  price_percent: number;
  base_unit_price_cents: number;
  unit_price_cents: number;
  regional_visits_today: number;
  regional_sales_cents_today: number;
} };
export type Household = {
  id: string;
  home_place_id: string;
  member_ids: string[];
  food_servings: number;
  money_cents?: number;
};
export type Train = {
  id: string;
  name: string;
  stops: string[];
  track?: { distance: number; x: number; y: number }[];
  stations?: { id: string; name: string; position: Position; platform: { x: number; y: number; width: number; height: number } }[];
  state?: {
    distance: number;
    at_station: string | null;
    service_state: "parked" | "travelling" | "approaching" | "stopped" | "boarding" | "departing";
    doors_open: boolean;
    service_hours: { starts_at: string; ends_at: string };
    capacity: number;
    car_capacity: number;
    stations: { station_id: string; name: string; queue_length: number; next_arrival_at: string; next_departure_at: string }[];
    passenger_ids: string[];
    carriages: { id: string; passenger_ids: string[]; seats: { id: string; passenger_id: string | null }[] }[];
  };
};
export type Loan = {
  id: string; borrower_id: string; purpose: string; principal_cents: number;
  issued_at?: string; repaid_at?: string;
  interest_cents: number; interest_percent: number; remaining_cents: number;
  installment_cents: number; next_payment_date: string; term_days: number;
  status: "active" | "overdue" | "repaid"; missed_payments: number; arrears_cents: number;
};
export type ConstructionProject = {
  id: string; home_place_id: string; buyer_id: string; worker_id: string | null;
  status: "queued" | "building" | "completed"; worked_seconds: number;
  required_seconds: number; includes_driveway: boolean; cost_cents: number;
};
export type RenderEntity = {
  id: string;
  kind: "person" | "pet" | "vehicle";
  name: string;
  position: Position;
  state: string;
  palette: string;
};
export type VolunteeringProject = {
  kind?: "tree_planting" | "park_cleanup" | "community_gardening" | "library_help";
  id: string;
  person_id: string;
  parcel_id: string;
  position: Position;
  status: "active" | "completed";
  worked_seconds: number;
  required_seconds: number;
  wage_cents: number;
  started_at?: string;
  completed_at?: string;
};
export type MunicipalProject = {
  id: string; person_id: string; kind: "park_cleanup" | "social_visit" | "library_help" | "tree_planting";
  site_id: string; position: Position; recipient_id?: string;
  status: "active" | "completed" | "cancelled"; worked_seconds: number; required_seconds: number;
  started_at: string; completed_at?: string;
};
export type Tree = {
  id: string;
  kind: "tree";
  name: string;
  position: Position;
  planted_at?: string | null;
  planted_by_id?: string | null;
  planted_by_name?: string | null;
  planting_reason?: "volunteering" | "town_employee" | "existing_landscape" | null;
};
export type World = {
  scenery_trees?: Tree[];
  municipal_projects?: MunicipalProject[];
  volunteering_projects?: VolunteeringProject[];
  community_gardens?: { id: string; position: Position }[];
  planted_trees?: Tree[];
  loans?: Loan[];
  construction_projects?: ConstructionProject[];
  map_size?: { width: number; height: number };
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
  economy?: { community_work_cents?: number; regional_grant_today_cents?: number; regional_grant_total_cents?: number; public_budget_date?: string; support_today_cents?: number; support_total_cents?: number; household_contribution_percent: number; treasury_cents: number; bank_cents?: number; construction_cents?: number; ledger: { id: number; at: string; from: string; to: string; amount_cents: number; reason: string }[] };
  roads: { id: string; points: number[][] }[];
  paths: { id: string; points: number[][] }[];
  people: Entity[];
  pets: Entity[];
  vehicles: Entity[];
  trains?: Train[];
  station_queues?: { station_id: string; entries: { person_id: string; arrived_at_seconds: number; destination_station_id: string }[] }[];
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
  money_cents?: number;
  carrying_groceries?: boolean;
  role?: string;
  employment_status?: string;
  support_paid_date?: string;
  support_total_cents?: number;
  work_days?: number[];
  shift_start_minute?: number;
  shift_end_minute?: number;
  workplace_id?: string;
  direct_walk?: Record<string, unknown>;
  credit_score?: number;
  aspiration?: string;
  route?: Position[];
  train_departure_id?: string;
  train_arrival_id?: string;
  on_train?: boolean;
  train_car_index?: number;
  train_seat_index?: number;
  train_trip?: { departure_id: string; arrival_id: string; destination_id: string; phase: string };
  car_trip?: { vehicle_id: string; destination_id: string; phase: "access" | "driving" | "egress" };
  in_vehicle_id?: string;
  owner_id?: string;
  reserved_by?: string;
  driver_id?: string;
  parking_place_id?: string;
  heading?: number;
  model?: "standard" | "sports";
  speed_units_per_minute?: number;
  investment_goal?: "home" | "car" | "sports_car" | "shop" | "mansion" | "savings";
  investment_target_cents?: number;
  vehicle_purchase?: { model: "standard" | "sports" };
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

export function setHouseholdContribution(worldId: string, percent: number) {
  return request<World>(`/worlds/${worldId}/economy/household-contribution`, {
    method: "PUT",
    body: JSON.stringify({ percent }),
  });
}

export function takeOverBusiness(worldId: string, placeId: string, buyerId: string, pricePercent: number) {
  return request<World>(`/worlds/${worldId}/businesses/${placeId}/takeover`, {
    method: "POST",
    body: JSON.stringify({ buyer_id: buyerId, price_percent: pricePercent }),
  });
}

export function setBusinessPrice(worldId: string, placeId: string, pricePercent: number) {
  return request<World>(`/worlds/${worldId}/businesses/${placeId}/price`, {
    method: "PUT",
    body: JSON.stringify({ price_percent: pricePercent }),
  });
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
