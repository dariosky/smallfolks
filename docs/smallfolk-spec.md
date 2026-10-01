# Smallfolk — Product and Technical Specification

## 1. Product summary

Smallfolk is a calm, inspectable city-life simulation: generate a small town, populate it with people and pets, and watch a believable little society develop over time. The player can pause, accelerate, explore, and eventually influence the world through planning, ownership, and an economy. The central promise is not maximal realism or a traditional city-builder; it is a readable living world where individual lives make the town feel alive.

The first useful world might be described as:

> A European town of 400 residents, with a compact historic centre, a rail line along the east edge, homes to the west, a supermarket near a ring road, and a small mix of shops, work, gardens, pets, walkers, cars, and trains.

Worlds must be deterministic from a seed plus versioned generation and simulation rules. A saved world should be replayable and debuggable.

## 2. Product principles

- **Small, legible, and human-centred.** Start with a town, not a continent. Let a player inspect why a person is doing something.
- **Systems produce stories.** Relationships, needs, work, commitments, ownership, and chance combine into emergent narratives; hand-authored scripts are not the main engine.
- **Rules make valid worlds.** Algorithms own geometry, routing, accounting, and persistence. An LLM can suggest intent, never directly author trusted simulation state or road geometry.
- **Procedural but coherent.** Build a compact modular visual vocabulary and parameterized variants, not an unbounded library of one-off AI assets.
- **Simulation and rendering are separate.** The world is semantic state; renderers are replaceable projections of it.
- **Scale deliberately.** Fidelity is concentrated near what is visible or narratively relevant. Distant/offscreen life is summarized, not fully animated.
- **Extensible data over speculative complexity.** Stable identities, event history, versioned schemas, and explicit contracts allow later systems without building every future feature now.

## 3. Player experience and high-level views

### Primary views

1. **World view** — pan/zoom top-down, 2.5D, or isometric town view; time controls; day/night; activity and traffic in motion. Select an entity or place.
2. **Person view** — portrait/icon, current intent/activity, mood/needs, schedule/commitments, relationships, possessions, recent memories, and an explainable “why now?” trace.
3. **Place view** — residents/visitors, role/capacity/open hours, affordances, inventory/owner when relevant, activity and local history.
4. **Town view** — population, simple economy, mobility, district/place index, active events, and a story/event feed.
5. **Generation/setup view** — seed and an understandable town brief (size, theme, geography, rail, density) before creation.

### Core interaction loop

1. Generate/select a seed and town brief.
2. Observe a lively day at a useful speed.
3. Notice people, places, movements, and small stories.
4. Inspect an entity to understand its current choice and context.
5. Later: influence the town through purchases, jobs, construction, service policies, or high-level directives.

The MVP prioritizes observing and understanding over direct control.

## 4. Scope

### MVP

- Generate and persist one compact town from a seed and constrained brief.
- Road/footpath graph, blocks/plots, a compact set of building/place archetypes, basic greenery, and traffic furniture.
- 30–100 residents, several workplaces/shops/services, a few pets, and a small vehicle pool.
- Clock/calendar, day/night presentation, working/open hours, and simple weekday routines.
- Needs- and commitment-driven activity choices: home, work, shop, eat, rest, socialize, walk, pet care; route on walkable/road graphs.
- Visible pedestrians and cars; one simple train service if rail is generated.
- Inspectable people, places, and vehicles, including a compact choice explanation and recent event/memory timeline.
- Basic money/accounts, ownership of homes/vehicles/businesses, wages, and purchases sufficient to support choices.
- Event log, save/load, reproducible seed, REST API, and a Vite web client.
- Semantic renderer initially using simple shapes, tiles, or modular sprites.

### Explicit non-goals for MVP

- A full-scale city, freeform terrain editing, multiplayer, disaster simulation, or a real-world geographic importer.
- Full physical traffic simulation, detailed interiors, collision physics, exhaustive life stages, crime/politics, or a production economy.
- Generating all possible art assets, photorealism, or AI-generated geometry at runtime.
- An LLM deciding every action, owning game truth, or silently mutating saved worlds.

## 5. World model

The authoritative simulation world is a versioned graph plus entity registry. Rendering-specific coordinates/assets may be derived and cached but must not be the only record of game truth.

```text
World
 ├─ metadata: id, seed, generation_version, simulation_version, clock
 ├─ geography/districts
 ├─ transport graphs: pedestrian, road, rail
 ├─ parcels, buildings, places, infrastructure
 ├─ entities: people, pets, vehicles, businesses/items
 ├─ ownership/economy
 ├─ active commitments and activities
 ├─ event stream and compacted memories
 └─ snapshots/checkpoints
```

### Spatial and transport graphs

Keep distinct but connected graph types:

- **Pedestrian graph:** sidewalk/path nodes, crossings, entrances, parks, and platforms. Default travel graph for people and pets.
- **Road graph:** lanes or simplified directed road segments, junctions, parking/driveway access, speed/traffic rules. Cars traverse this graph.
- **Rail graph:** track segments, switches, stations/platforms, timetable edges. Trains use this graph.
- **Access links:** building entrances, parking, stations, crossings, and transfer points connect the graphs.

Do not infer walkability from pixels or a renderer tile. A route is a first-class simulation result with a graph version and expected duration.

```python
class TransportNode:
    id: str
    kind: Literal['sidewalk', 'crossing', 'road_junction', 'parking', 'station', 'platform']
    position: tuple[float, float]

class TransportEdge:
    id: str
    graph: Literal['pedestrian', 'road', 'rail']
    start_id: str
    end_id: str
    length_m: float
    allowed_modes: set[str]  # walk, car, train
    travel_seconds: float
    capacity: int | None
```

### Places, infrastructure, and affordances

A building is physical structure; a place is a usable social/economic location. One building can contain one or more places.

```json
{
  "id": "place:bakery-01",
  "kind": "bakery",
  "building_id": "building:market-12",
  "entrance_node_id": "walk:341",
  "hours": {"mon-fri": [["07:00", "18:00"]]},
  "capacity": 12,
  "roles": ["employer", "shop", "social_place"],
  "affordances": ["work_bake", "buy_food", "eat", "meet"],
  "owner_id": "person:elena",
  "inventory": {"food": 80}
}
```

An **affordance** expresses what can happen at a place or asset, subject to opening hours, capacity, money, permissions, inventories, and context. It avoids hard-coding every activity against every building type.

### People and pets

People should be individuals before they are generic agents. Use small bounded trait/need sets whose meanings are explainable. Initial traits can be generated deterministically from seed data, then evolve only through defined events.

```python
class Person:
    id: str
    name: str
    home_place_id: str
    workplace_id: str | None
    roles: set[str]                 # resident, baker, parent, student, owner
    personality: dict[str, float]   # sociability, conscientiousness, thrift, curiosity
    mood: dict[str, float]          # valence, energy, stress; derived/short-lived
    needs: dict[str, float]         # hunger, rest, social, safety, fun, hygiene
    interests: set[str]             # gardening, rail, sport, music...
    household_id: str | None
    dependents: set[str]            # people/pets requiring care
    money_account_id: str
    owned_asset_ids: set[str]
    commitment_ids: set[str]
    current_activity_id: str | None
    memory_ids: list[str]

class Pet:
    id: str
    species: Literal['dog', 'cat']
    guardian_id: str
    home_place_id: str
    needs: dict[str, float]
    temperament: dict[str, float]
    current_activity_id: str | None
```

Mood is not a duplicate permanent-personality system: personality biases decisions, needs create pressure, and mood is a readable short-term result of recent state/events.

### Relationships and memories

Relationships are directed and multi-dimensional; “friend” is a derived label, not the only stored fact.

```json
{
  "from_id": "person:marco",
  "to_id": "person:elena",
  "dimensions": {"affinity": 0.72, "trust": 0.81, "familiarity": 0.91, "tension": 0.08},
  "labels": ["partner", "coworker"],
  "updated_at": "world-time"
}
```

Memories are compact, consequential, and decaying/aggregatable rather than a transcript of every movement. Store source events, subject/object/place, salience, emotional valence, and a summary key. A timeline is derived from this event history.

```json
{
  "id": "memory:...",
  "owner_id": "person:marco",
  "event_id": "event:...",
  "kind": "missed_commitment",
  "subjects": ["person:marco", "person:elena"],
  "place_id": "place:bakery-01",
  "salience": 0.8,
  "valence": -0.4,
  "created_at": "2031-05-12T09:15:00"
}
```

### Activities, commitments, routines, and roles

- **Role:** durable responsibility/capability (resident, parent, employee, owner, student).
- **Commitment:** bounded obligation with time/place/participants and priority (shift, school, appointment, pet feeding, meeting).
- **Routine:** a learned or authored preference template (morning coffee, work commute), never an unbreakable script.
- **Activity:** current executable plan: intent, target affordance/place, route, mode, start/end, participants, status.

An activity begins from an intent; its route and render movement are implementation details of that activity. Important commitments pre-empt lower-value desires, but needs and emergencies can interrupt routines.

### Economy, assets, and ownership

Model assets and ownership early, but keep the MVP economy simple.

```python
class Asset:
    id: str
    kind: Literal['home', 'vehicle', 'business', 'item']
    owner_id: str | None
    location_id: str | None
    condition: float
    value: int
    capabilities: set[str]  # provides_shelter, enables_car_trip, sells_food

class LedgerEntry:
    id: str
    at: datetime
    debit_account_id: str
    credit_account_id: str
    amount: int
    reason: str
    event_id: str
```

Cars are owned/shared assets that unlock car travel only when available, parked/reachable, and appropriate. Shops transfer simple inventory and money; jobs pay wages. Avoid market equilibrium or complex production chains until behavior needs them.

## 6. Procedural world generation

Generation turns a compact **town specification** into valid geometry and seeded social state. The high-level brief can be player-selected, template-driven, or LLM-assisted; the generator is deterministic.

### Pipeline

```text
seed + town brief + generator version
  → terrain/boundary and districts
  → arterial/main road and rail constraints
  → secondary streets, blocks, parcels and pedestrian network
  → zoning and place/building allocation
  → entrances, crossings, parking, signals, platforms and graph validation
  → modular visual variants and decoration
  → households, people, pets, jobs, businesses and assets
  → relationships, routines, timetables and initial economy
  → simulation warm-up / validation
  → saved world snapshot
```

### Urban rules

- Generate main routes first, then secondary streets, blocks, plots, buildings, and finally sidewalks/crossings/parking.
- Apply district/zoning constraints rather than scattering building types: station areas favour shops/apartments/offices; a centre favours dense mixed use; suburbs favour houses/gardens; an industrial edge favours warehouses.
- Validate every inhabited building has pedestrian access; every assigned job/shop can be reached; car-dependent assets have road/parking access; rail stations connect to the walk graph.
- Generate reusable archetypes with parameterized variation (shape, materials, colour, condition, signage, garden/furniture), not bespoke art per building.
- Persist the brief, seed, all version identifiers, and generated decisions necessary for reproduction/migration.

### Starter asset vocabulary

- Roads: straight/curve/junction/roundabout, crosswalk, bicycle/parking variants, signals/signs.
- Ground/public realm: sidewalks, grass/dirt, plazas, paths, rails/platforms.
- Buildings: home, apartment, shop, office, school/service, station, warehouse.
- Props: trees, lamps, benches, bins, traffic lights, fences, garden items.
- Entities: modular human silhouettes/avatars, dog/cat, car/van/bike/train components.

Visual variety should arise from composable base components: a car, for example, varies by body, colour, wheels, size, and condition.

## 7. Simulation design

### Time and day/night

World time is authoritative, with configurable pause and speed steps. Calendar/day-of-week, opening hours, commitments, and light/weather presentation consume the same clock. Day/night is a renderer output from time (and later weather), not a separate simulation.

### Event-driven decisions

Use a hybrid loop:

- a coarse fixed tick advances clock, needs, travel/progress, and scheduled jobs;
- an event queue handles arrivals, commitment starts/ends, timers, inventory changes, and significant social/economic events;
- an agent reevaluates when a relevant event occurs, a need crosses a threshold, a plan becomes invalid, or a scheduled decision time arrives.

Do not score every possible action for every entity every frame. Decisions should be event-driven, deterministic under a seeded RNG, and include a compact explanation.

```python
def choose_intent(person: Person, world: World) -> Intent:
    candidates = available_intents(person, world)
    scored = [score(intent, person, world) for intent in candidates]
    return choose_seeded(scored)  # includes reasons, not only a number

# An illustrative score combines, rather than replaces, hard constraints.
score = commitment_priority + need_relief + relationship_value + interest_fit \
        - travel_cost - money_cost - stress_cost + controlled_variation
```

Hard constraints (closed venue, lack of funds, no reachable route, occupied asset, dependency care) filter candidates before scoring. The stored explanation should mention the strongest factors: “late for bakery shift,” “hungry,” “Elena invited Marco,” or “car unavailable.”

### Movement and traffic

- Pedestrians/pets follow pedestrian routes and crossings; use occupancy/personal-space simplification rather than physics.
- Cars reserve/use road segments with a simple queue/right-of-way model at junctions. MVP traffic should look plausible and avoid impossible routing, not model every lane-change rule.
- Trains run a timetable/path between stations, with platform arrival/departure events. Start with a single service line.
- Vehicles, pedestrians, and trains change state only through simulation events; interpolation belongs to the client renderer.
- Traffic infrastructure (junctions, crosswalks, lights, parking, rail crossings) is semantic infrastructure that exposes traversal rules and rendering hints.

### Simulation LOD

Use levels of detail to keep a town alive without spending equal compute everywhere:

| Level | When used | Behavior |
| --- | --- | --- |
| Full | visible, selected, in an active story/interaction | route/activity progression, position updates, important social details |
| Local summary | nearby but not visible | activity and travel progress in coarser steps; important events retained |
| Background | distant/offscreen ordinary agents | jump between commitments/routine outcomes; aggregate needs and emit only meaningful events |

LOD changes must not produce impossible outcomes. Promote an entity before a visible/important encounter and preserve its logical location/activity throughout.

## 8. Renderer abstraction

The backend exposes semantic render state, not UI-specific sprite selection. The frontend maps semantic kinds, states, and variants to current assets/meshes/tiles. This makes a simple 2D renderer viable now and leaves 3D/isometric or alternate art styles possible later.

```ts
type RenderEntity = {
  id: string;
  kind: 'person' | 'pet' | 'vehicle' | 'building' | 'infrastructure' | 'prop';
  position: { x: number; y: number; z?: number };
  heading?: number;
  state: string; // walking, driving, parked, working, open, closed
  visual: {
    archetype: string;
    variantSeed: number;
    palette?: string;
    parts?: Record<string, string>;
  };
  selection?: { label: string; inspectable: boolean };
};
```

Renderer responsibilities: camera, culling, interpolation, tile/mesh/sprite selection, animation, lighting/day-night, input hit testing, and accessibility alternatives. Simulation responsibilities: semantic position, state, route/activity progress, graph validity, and decisions.

Begin with an intentionally modest 2D top-down or 2.5D/isometric style. Choose the final camera style through a small prototype before locking asset production.

## 9. AI/LLM role

AI is an optional creative/interface layer, not the simulation engine.

Good roles:

- Turn natural-language town prompts into a validated `TownBrief` with explicit constraints.
- Suggest names, bios, descriptive event summaries, and optional player-facing story recaps.
- Help author modular asset concepts during development, subject to human review and coherent art direction.
- Offer high-level scenario seeds (“quiet rail town”, “market day”, “young families”) that the deterministic generator realizes.

Not allowed without an explicit, validated tool/action boundary:

- Directly mutate authoritative state, emit geometry, decide an agent’s every frame, or invent unaccounted money/assets/relationships.
- Replace generation validation, routing, policy checks, persistence/migrations, or test oracles.

Store LLM input/output provenance only if its result materially affects a saved brief or player-visible content. The world itself must remain playable/reproducible without the service.

## 10. Application architecture

### Implementation constraints

- **Backend:** Python. Prefer a typed HTTP API and clear domain/application/infrastructure boundaries. Select the exact framework and persistence library from starter-project conventions rather than duplicating framework decisions in this spec.
- **Frontend:** TypeScript + Vite. Use the **Oxc toolchain** (`oxc.rs`) for linting/formatting where it covers required work, following the same general tooling preference as Otto, LYKD, My Listening Shelf, and Dindi.
- **Shared contract:** generated or manually versioned TypeScript API types from a stable backend schema; do not let renderer-internal types leak into persistence.

### Suggested repository shape

```text
smallfolks/
├─ backend/
│  ├─ app/
│  │  ├─ api/                 # HTTP routes, schemas, websocket/SSE if added
│  │  ├─ domain/              # models, invariants, value objects
│  │  ├─ simulation/          # clock, events, decisions, routing, LOD
│  │  ├─ generation/          # briefs, pipeline, validators, seeded RNG
│  │  ├─ services/            # use cases: create world, advance, inspect
│  │  ├─ persistence/         # repositories, ORM/storage, migrations
│  │  └─ rendering/           # semantic render-state projection
│  └─ tests/
├─ frontend/
│  ├─ src/
│  │  ├─ api/
│  │  ├─ world/               # camera/map renderer/entity render mapping
│  │  ├─ features/            # inspector, town panel, generation, time controls
│  │  ├─ state/
│  │  └─ styles/
│  └─ public/
├─ docs/                      # decisions, API/event-format notes
└─ scripts/                   # development and reproducibility helpers
```

Keep domain simulation code independent of request handlers, database sessions, browser APIs, and concrete render assets.

## 11. API boundaries

Start with conventional HTTP endpoints and polling/refetch on meaningful simulation updates. Add a streaming channel only once live animation/update requirements demonstrate the need.

```text
POST   /api/worlds                         create from TownBrief/seed
GET    /api/worlds/{worldId}               metadata and clock
POST   /api/worlds/{worldId}/advance       controlled time advance (dev/MVP)
GET    /api/worlds/{worldId}/render-state  viewport/LOD-filtered semantic projection
GET    /api/worlds/{worldId}/entities/{id} inspector detail and explanation
GET    /api/worlds/{worldId}/events        filtered event/history feed
GET    /api/worlds/{worldId}/places/{id}   place details
POST   /api/worlds/{worldId}/commands      future player actions; explicit command schema
```

Commands must be validated domain actions (for example, `buy_asset`, `set_time_speed`, later `build_place`), not generic patch endpoints. The server owns clock advancement and simulation mutations.

## 12. Persistence and reproducibility

- Use a relational database for stable entity, graph, ownership, relationship, and queryable event data; use JSON fields only for bounded flexible attributes/visual variants where querying is not central.
- Treat the event stream as an audit/history source, with periodic authoritative snapshots/checkpoints for load performance. Do not require pure event sourcing from day one.
- Version database schema, world format, generation algorithm, and simulation rules independently. Provide migration policy before changing generated-world semantics.
- Persist seeded RNG state or derivation strategy at deterministic boundaries. Never depend on system randomness for simulation decisions.
- Store derived render caches separately or regenerate them; they are disposable.
- Use soft archival/versioned saves instead of destructive overwrites of a player world.

## 13. Testing and quality strategy

- **Unit tests:** trait/need calculations, candidate filtering/scoring, commitments, affordability/ownership, graph routing, transfer constraints, time/calendar, and LOD promotion.
- **Property/generative tests:** many seeds produce connected, reachable, bounded worlds; no occupied building is isolated; routes obey modes; generation is deterministic for seed+version.
- **Scenario tests:** a worker reaches a shift, a hungry resident buys/eats when able, a pet-care commitment is respected, a car is unavailable to two simultaneous drivers, a train follows timetable, an invalid route triggers replanning.
- **Persistence tests:** save/reload equivalence, snapshot+event replay equivalence within defined tolerances, schema migrations.
- **API contract tests:** creation, advance, renderer projection, inspector explanation, invalid command rejection.
- **Frontend tests:** map/selection/inspector/time-control flows and semantic-render mapping. Use screenshot/visual checks for camera, day/night, density, and selection readability once a renderer exists.
- **Tooling:** run backend tests and frontend type/lint/build checks, including Oxc tooling, in CI. Add fixed-seed golden fixtures only for intentionally stable projections; avoid brittle pixel-perfect whole-world tests.

## 14. Development phases

1. **Foundation:** repository/tooling, typed API shell, world clock, seed/version metadata, persistence baseline, fixed tiny fixture world.
2. **Readable prototype:** top-down/2.5D renderer prototype, camera/selection, semantic render projection, person/place inspector, pause/speed/day-night.
3. **Generation and navigation:** town brief, deterministic blocks/places/transport graphs, validators, pedestrians routing to home/work.
4. **Life simulation:** needs, commitments, routines, activity planner/explanations, relationships, memories, basic pets.
5. **Town movement and economy:** simple cars/parking/traffic, optional rail line, ownership, wages, purchases/inventory.
6. **Depth and polish:** simulation LOD, event feed/story recaps, more archetypes/variation, player commands, balancing and migration discipline.

At the end of each phase, keep one shareable seeded world and a small scenario suite as a regression baseline.

## 15. Open design decisions

- Camera/style: strict top-down, 2.5D, or isometric; choose after a visual interaction prototype.
- Simulation cadence: real-time with pause/speed versus primarily turn/step-based; MVP can support both a live clock and controlled advance endpoint.
- Town size/default density and target-device performance budget.
- Whether weather appears in MVP and whether it affects choices or is presentation-only.
- Person presentation: abstract icons, sprite characters, or modular portraits; maintain semantic renderer contract either way.
- Player role: observer only at launch, benevolent planner, household manager, or town owner; add influence only after observer experience is compelling.
- Initial database/framework selection and transport format should follow the chosen starter conventions.
- LLM availability/privacy/cost boundaries; all essential creation flows need deterministic non-LLM alternatives.

## 16. First implementation slice

Build the narrowest vertical slice that proves the premise:

1. Create a fixed-seed town with a few buildings, connected sidewalk/road graph, ten residents, one workplace, one shop, a dog, and two cars.
2. Run a single day: residents leave home, walk/drive to work, buy food, return home; the dog is walked; time and lighting advance.
3. Click a resident and show current activity, route target, needs, next commitment, and an explanation.
4. Save/reload without changing the observable world state.

Only then generalize it into the procedural pipeline and broader town model described above.

### Implemented weekly commitments and dining

Resident `work_days` uses Monday=0 through Sunday=6. Default office, school, workshop, and library jobs run weekdays; shops/bakeries include Saturday; clinic, bar, cinema, and restaurant shifts can run daily. No commuting, wages, or construction shifts begin on days off. Inspectors expose weekly work days.

The Olive Table offers lunch and dinner, with separate 11:00–15:00 and 18:00–22:00 staff. Off-duty residents choose dining during 12:00–13:00 or 19:00–20:00 when hunger, personal inclination, staff availability, and funds allow. Travel persists; payment occurs on arrival, once per meal, and 30 minutes of dining eases hunger and social need. Existing saves receive these fields, restaurant access, and staff additively.

### Building operating status

Workplaces expose persisted operating status, closure reason/time, and the next scheduled opening. Closed buildings show a map sign and omit chimney smoke; occupied, awake households retain smoke. Weekly schedules, hours, and staff activity drive status. Bankruptcy records exact closure time separately from the bounded event feed; legacy saves recover known timestamps from events and display unknown time otherwise. Scheduled closures infer the last shift end and next shift start. Unstaffed automated services (the bank) do not acquire a staff-based closure.

### Town Hall community work and unemployment support

Adults may choose sponsored community work between 08:00 and 18:00: tree planting (four hours, €24), park cleanup (one hour, €6), community gardening (two hours, €12), and library help (one hour, €6 during scheduled library opening hours). Existing student visuals identify students because saves have no ages. Unemployed adults seek suitable tasks; employed adults consider them when bored (at least 20) or strongly interested in nature/community/library work (at least 0.5), with one saved deterministic 40% daily participation choice. Nature, community, and library interests rank the tasks. Existing nature preferences are preserved; missing interests derive deterministically from resident IDs.

Starting a task requires household food, enough time for work plus estimated outbound/return travel and a 15-minute buffer, and available funds. Scheduled work, sleep, urgent hunger/rest, pet care, and planned outings take priority. Only on-site time counts; interruptions retain progress. Each adult starts at most one project per game day. Active park/library tasks reserve a single slot per location; planting and gardening permanently occupy their parcels. Completed planting adds a persistent tree; gardening adds a visible flowerbed; park cleanup raises cleanliness by 40 (capped at 100), while cleanliness declines one point per game hour. The library records completed help sessions.

Task pay is reserved immediately in a separate community-work account and distributed on completion using the household contribution percentage. Completed task payments count as earned income. Legacy projects without a kind remain four-hour €24 tree planting and receive payment reservations on the first advancing tick, preserving progress and terms.

Unemployed adults receive €24 once per game day from 08:00 or their first eligible tick afterward, split using the same household contribution setting. A bankrupt workplace establishes unemployment; days off and students do not qualify. Community wages are additional. A reopened workplace stops future support; payments already received remain. Support is separately labelled and does not enter earned-income history or establish loan eligibility. Saved payment dates and cumulative totals remain valid after ledger truncation and reload.

A finite external regional account starts with €1 billion and transfers explicit public-services grants through the ledger. On the first advancing tick each day, a daily budget covers scheduled public wages, eligible support, up to €24 of community work per adult, and unfunded legacy commitments. Only the treasury shortfall against the unspent budget is funded; spending does not trigger repeated grants. Changed employment eligibility may increase the budget later that day. Existing depleted towns receive funding on their next advancing tick; no historical payments are backdated, and reading a snapshot or advancing zero seconds awards nothing. If external funds are exhausted, unpaid support remains eligible for retry; project escrow remains protected.

Town Hall shows treasury, reserved payments, daily/cumulative grants and support, clickable recipients, task offerings, and recent progress. Residents show their latest support date and cumulative amount; parks show cleanliness and cleanup counts, and the library shows completed help sessions.


### Town Hall staffing and municipal handymen

The small town keeps Sofia Costa and Eva Vega as planners; Maya Chen and Sara Lind are town handymen. Fresh towns use these roles, and existing snapshots convert only those two named residents when they are still planners employed by Town Hall. Migration preserves their positions, weekly schedules, balances, journeys, and existing volunteering projects; it does not add missing residents to older smaller towns.

Handymen retain their normal weekday 08:00–17:00 public shifts and €12/hour wages, funded by the existing regional public-services budget. During shifts they walk from their actual position to on-site assignments instead of remaining at a planning desk. Priority is park cleanup when cleanliness is strictly below 50%, social work, then tree planting. A one-hour cleanup improves cleanliness by 40, capped at 100; accepted cleanup sessions finish even if cleanliness crosses the starting threshold. Dirtier available parks come first. Urgent park work interrupts lower-priority projects without erasing progress.

Social work consists of one-hour companionship visits to awake residents who are actually at home and have unmet social need of at least 60; actual on-site companionship gradually reduces that need by up to 35 over an hour, and each recipient receives at most one completed municipal visit per day. A recipient leaving cancels the visit without fabricated progress. Handymen also provide one shared one-hour library-help session per day during scheduled opening hours. When these needs are served, they plant a visible tree after four accumulated on-site hours. Jobs, recipients, completion, and progress persist in `municipal_projects`; tree parcels and active work sites are reserved across municipal and voluntary work.

Travel, waiting, meals, rest, and days off do not earn task wages or progress. Hunger of at least 65 triggers a meal break; lunchtime uses the usual hunger threshold of 35; urgent rest interrupts work at Town Hall. Task progress resumes after breaks and across shifts/saves. Municipal work pays only the normal public wage in 15-minute work blocks, with household sharing and earned-income history; it does not also pay a volunteering stipend. Town Hall displays the two handymen, their current activities, and recent municipal work separately from optional sponsored work.
