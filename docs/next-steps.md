# Smallfolk: evaluation and implementation plan

Evaluated 2026-09-29 against [smallfolk-spec.md](smallfolk-spec.md), especially sections 2, 5–8, 11–14 and the first vertical slice in section 16.

This is a source-level evaluation with isolated, in-memory simulation probes. It is not a browser visual acceptance pass or a production assessment. The train-capacity implementation was interrupted by this planning request: the checkout contains partial backend changes and the older frontend train behaviour. Treat those changes as unfinished. This evaluation adds documentation only; implementation resumes in a following phase.

## Assessment

The app is a useful visual and API scaffold, but it does not yet complete the specified first slice of a believable, observable day. Its most important next milestone is consistency: every visible movement, arrival, seat, activity and explanation must describe the same underlying world.

Repeated visual fixes have exposed the same architectural problem: simulation, routing and rendering each maintain parts of the truth. Adding more residents or richer sprites before resolving that will multiply contradictions. Keep the current stack and SVG prototype, but replace the time-of-day script incrementally with explicit activities, journeys and vehicle state.

Preserve the user's current direction: strict top-down, detailed cartoon art, buildings facing roads, automatic running on open, continuous movement, articulated trains, visible passengers and four seats per passenger coach. Full photorealism and detailed interiors remain beyond the spec's MVP; use selective roof cutaways and a consistent modular style first.

## Current coverage

| Spec area | Current evidence | Assessment |
| --- | --- | --- |
| App foundation | FastAPI, React/Vite, SQLModel snapshot, Alembic migrations, IDE launchers, backend 5340/frontend 5341, production HTML serving | Useful foundation; retain it |
| Tiny fixture | Ten named people, homes/services, dog, two parked vehicles, roads and SVG town | Present, largely hand-authored |
| Clock and controls | Browser issues minute advances; local pause; time-step buttons | Partial; multiple clock owners and mutation races |
| Movement | Six-node pedestrian graph; route points; sprite tweening | Partial; paths and visible roads are not one geometry source |
| Rail | Backend timetable/capacity draft; frontend independent train clock | Incomplete and inconsistent across layers |
| Individual life | Fixed 08:00–17:00 work script and a few need values | Placeholder, not the specified decision model |
| Inspection | Live selected-person card, activity and explanation strings | Good starting point; places/vehicles/train need real details |
| Persistence | Whole-world JSON snapshot in a relational table | Saves state; no durable event history/checkpoints or world migration policy |
| Generation | Seed recorded; fixed coordinates and population | Not procedural yet |
| Economy/social life | No functioning accounts, transactions, relationships or memories | Missing |
| Observation tools | Static map extent; no camera, day/night, population panel or setup UI | Missing or partial |
| Quality | Four backend smoke/scenario tests and frontend build tooling | Does not establish behavioural correctness |

## Findings that should drive the order

### P0 — correctness problems visible to the player

1. **Train position has two owners.** `backend/simulation/tick.py::_service_state` emits scheduled distance and station state, but `frontend/src/world/TownMap.tsx::TrainLoop` ignores it. The latter uses its own elapsed clock and resets/overrides position based on passengers. This is the source of station jumps and boarding without the visible train. Backend queue wording now starts with “Queued”; the frontend still searches for “Waiting”.
2. **Capacity is only a partial count check.** There is an eight-person backend limit but no seat registry, carriage assignment, FIFO queue or actual per-car occupancy. Frontend shows a dot for all riders in one coach. Boarding is keyed to one departure minute rather than a platform arrival/boarding event.
3. **Overflow passengers teleport.** An in-memory probe with ten copies of Marco produced eight aboard and two queued at 07:34. At 07:43 the two people who never boarded became “Walking from Eastgate”. The itinerary advances by clock regardless of whether the previous leg completed. Waiting for the next service is not implemented.
4. **Needs do not progress under normal playback.** `minutes // 12` and `minutes // 20` are zero for one-minute updates. A 60-minute probe left hunger/rest unchanged; bulk advances now recurse into one-minute steps, so they also lose these increments. Social need has no progression/relief loop.
5. **Schedules can teleport people.** `_move_to` assigns destination coordinates directly for work, home and pet care. Reaching 08:00 marks people as working without checking arrival. A purchase reduces hunger immediately, then the next branch can return the person home. No coherent return journey or eating duration exists.
6. **Rendered motion can contradict the route.** Walking estimates use place centres, movement uses offset positions, and station access uses straight-line distance at a different speed despite rendering a longer graph route. SVG/CSS position interpolation can cut corners between snapshots. Pedestrian graph edges and access legs can cross buildings or rails without designated crossings.
7. **Clock mutation is tied to each browser.** `TownPage.tsx` sends advances on a local timer and can also send manual advances. More than one tab can advance the same world; snapshot read-modify-write has no revision check. A local pause does not establish an authoritative world pause. Train animation can keep advancing while an API update is delayed.

### P1 — foundations needed for the specified MVP

8. **Generation is a fixed fixture.** Seeds 1 and 2 produced identical places and people in an isolated probe. Adding buildings alone does not create blocks, plots or coherent districts. The new centre avenue at x=700 also intersects building/park footprints around that coordinate. The validator checks only place-place overlap, not roads, rails, water, entrances or reachability.
9. **Rail geometry is duplicated and slightly different.** The displayed loop uses quadratic SVG corners; vehicle positions use circular arcs. Timetable, travel estimates and route coordinates are separately hard-coded. Midnight resets the service offset from time-of-day rather than a persisted service epoch.
10. **State is implicit in prose and mutable dictionaries.** The renderer detects riding/walking from English activity strings. There are no typed activities, commitments, journey legs, graph revisions or occupancy contracts. Stale `on_train` flags can survive branches that clear other train metadata.
11. **The “why” trace is authored text.** It does not record rejected modes, calculated arrival, missed departures, travel costs or binding constraints. Work is the same daily schedule, with no weekday/open-hours model or actual opportunity selection.
12. **Save identity and versions are overloaded.** World ID is derived from fixture version plus seed. Increasing `poc-N` sidesteps old snapshots rather than migrating them. Simulation version remains `poc-1` despite behavioural changes. Creating a world also means reloading an existing one; no separate new/load/reset/archive workflow exists.
13. **History is transient.** Events mostly say “town advanced” and are trimmed to twelve entries. There is no durable per-entity history, checkpoint/replay mechanism, relationships or memories.
14. **The semantic projection is not driving the map.** A render-state endpoint exists but the UI consumes the full world and contains hard-coded infrastructure. Train inspection is absent from entity lookup. API responses are largely arbitrary dictionaries and manually mirrored TypeScript types.
15. **Validation can miss regressions.** The existing commute test accepts either walking text or any text containing “Folk Loop”, including a queued passenger. It does not prove boarding, capacity, arrival or continuity. Test setup uses the configured DB engine with `create_all`; isolate scenario tests from developer saves and separately check migrations.

### P2 — missing product depth

16. Cars are stationary props, pet care teleports, and shops have no hours, capacity, stock or transactions. Household responsibilities, possessions, traits, mood, relationships and memories are absent.
17. There is no pan/zoom/follow camera, day/night, meaningful speed selector, setup brief, save browser, town overview, station inspector or accessible entity list. Focusable map groups need keyboard activation as well as click handling.
18. Art is repetitive and scale/perspective vary across people, vehicles and buildings. Identity colour relies partly on DOM ordering instead of stable visual traits. Building fronts, entrances and labels need stronger hierarchy. The map needs a browser review at street and town scales before asset expansion.
19. Starter auth/screens and README descriptions do not consistently describe the active town flow. Review and remove unused scaffolding only after checking references. Do not migrate frameworks or introduce a new renderer just to clean this up.

## Execution rules

- Work one numbered step at a time. Each step should produce something observable in the app and end with a short demonstration and relevant checks.
- Preserve user saves and existing work. Establish a version policy before changing saved semantics; do not keep forcing fresh fixture IDs as an upgrade strategy.
- Keep simulation independent of React, HTTP and database sessions. Keep rendering a projection of state.
- Use a small set of high-value behavioural scenarios, not exhaustive unit tests or brittle whole-world screenshots. Build/type/lint checks are necessary but cannot prove movement correctness.
- Keep a known ten-resident fixture for debugging even after procedural generation arrives. Add a crowded-platform scenario specifically for capacity.
- Dependency order: 0 → 1 → 2 → 3 → 4 → 5. Then 6 → 7 → 8 → 9 → 10, with persistence discipline beginning in step 0. Do not wait until step 9 to version new state or retain important events.

## Step 0 — establish an honest, reproducible baseline

**Scope:** small prerequisite; no new gameplay.

- [x] Record the partial `poc-9` train changes as unfinished, including the frontend/backend contract mismatch; preserve them for completion in step 2.
- [x] Isolate checks from developer saves. Keep a reproducible fixture and capture its current visible behaviour.
- [x] Define world-format, generation and simulation versions separately; specify how old snapshots are loaded, migrated, archived or explicitly rejected with an explanation.
- [x] Define the minimum typed contracts for clock/revision, location, activity, journey, train, carriage, seat and station queue. A person's location is at a place, on a route, on a platform or inside a vehicle—not independent conflicting flags.
- [x] Correct README claims and record the first acceptance scenario. Preserve SQLModel/Alembic and the current local/production serving setup.

**Done when:** a developer can load a known world, identify its versions and unfinished behaviour, and run checks without altering their saved town.

### Step 0 implementation record (2026-09-29)

- The known fixture remains `world:poc-9-{seed}` and its partial train work is deliberately preserved: `simulation/tick.py` publishes clock-driven service state, while `TownMap.tsx` still drives a separate animation and reads incompatible queue wording. Step 2 owns the behavioural completion; no gameplay was changed here.
- Current snapshots use `world_format_version: 1`, `generation_version: "poc-9"`, `simulation_version: "poc-1"`, and a command `revision`. Format 0 (no format/revision marker) is read through an additive in-memory migration and is persisted as format 1 only after a command changes state. Unknown future and retired formats return an explained compatibility error; unsupported-save archival/export is intentionally left for step 9.
- `simulation/contracts.py` now defines the planned JSON vocabulary. It is a type boundary, not a parallel runtime state machine: step 1 will make clock/revision authoritative and step 2 will populate train/carriage/seat/queue state.
- Backend tests now use a per-run temporary SQLite database and apply Alembic migrations before each scenario. The known fixture is the reproducible baseline. The captured behaviour is still intentionally incomplete: scripted schedules can teleport, needs do not accumulate per normal one-minute update, and the frontend train does not follow backend train state.
- First acceptance scenario: create fixture seed `90111`; verify format, generation and simulation versions; advance 30 minutes; reload and verify the same clock and a revision increment. This proves snapshot identity and isolated checks only—not route or train correctness.

## Step 1 — one simulation clock and route-faithful movement

**Depends on:** 0. **Primary files:** simulation, world service/API, `TownPage.tsx`, `TownMap.tsx`.

- [x] Store elapsed simulation time in seconds and use a fixed logical update cadence, independent of render FPS and request grouping. The initial cadence is 15 logical seconds every 250 ms; it is covered by grouped-versus-stepped equivalence tests and should be revisited with a browser walking/boarding observation.
- [x] Add authoritative run/pause/speed state. Opening the town starts/resumes through an explicit server-owned command; tabs observe the same saved world by polling. Per-world locks and revisions reject stale/conflicting mutations.
- [x] Make manual advancement and automatic running use the same engine. There is no offline catch-up: only the running server tick advances state.
- [ ] Represent a journey as persisted legs with start/end, edge IDs, mode, distance and progress. Complete one leg before starting another.
- [x] Fix fractional need accumulation and batch-versus-small-step equivalence.
- [ ] Render all motion against one presentation timestamp using route progress, not direct point-to-point chords. The train now follows the server’s position at the 250 ms observation cadence, but pedestrian route execution, pause-consistent animation and delayed-response presentation still need completion.

**Done when:** a pedestrian follows a corner at every speed; pausing freezes all motion; two tabs do not double world speed; advancing ten minutes at once matches equivalent smaller steps.

### Step 1 progress record (2026-09-29)

- The server tick is deliberately polling-based for this small POC: a WebSocket is not needed to make the authoritative clock smooth. The app sends no browser advance timer; it observes a running world every 250 ms. A later event/delta channel can replace polling without changing the clock contract.
- `simulation.elapsed_seconds`, `presentation_time_seconds`, `running` and `speed` are persisted in the snapshot. The server advances 15 logical seconds per 250 ms at speed 1, scales that step by speed, and persists a new revision. Existing format-0 saves receive a stopped simulation state on load.
- Journey objects now accompany the existing walk/train route data as an interim persisted contract. The current route graph and schedule still need the step’s full leg-completion/replanning rewrite, so this step is not yet complete.

## Step 2 — finish the train, queues and visible passengers

**Depends on:** 1. This completes the outstanding train request before expanding the town.

- [ ] Store one rail path and use it for track drawing, arc-length traversal, coach headings and timetable distances. Remove demand-driven train positioning and the independent frontend train clock.
- [ ] Model service states: travelling → approaching → stopped/doors open → boarding complete → departing. Progress around the loop continuously, including wraparound and day boundaries, with or without passengers.
- [ ] Give the existing two passenger coaches four explicit seats each (eight total; locomotive excluded). Persist `train_id`, `car_id`, `seat_id` and passenger ID; do not repack seats when another person leaves.
- [ ] Maintain station queues ordered by actual arrival time with deterministic tie-breaking. Alight first, then board eligible waiting people into free seats while the train is stopped at that platform. Include finite boarding time.
- [ ] Keep overflow passengers visibly queued for the next actual service. Missing a train must not complete a ride or teleport someone to the destination. Allow replanning and truthful lateness.
- [ ] Show individual seated people through open/cutaway coach roofs. Keep identity colours and selection; click a rider to inspect the same person. Show coach occupancy, queue length and next train in station/train inspectors.
- [ ] Align platform geometry with coach doors, queue slots and safe pedestrian access. Render boarding/alighting at the same presentation time as train arrival/departure so network interpolation cannot make people vanish early.

**Done when:** a ten-person crowd fills eight seats, leaves two visible on the platform, and boards those two on a later service. The train takes the same path/timing in an empty-world run. Each rider is visible in a stable seat, alights only at their stop, and survives save/reload while aboard. Verify this in the browser, not only by inspecting state.

## Step 3 — connected town geometry and trustworthy journey estimates

**Depends on:** 2; begin with the fixture, then reuse the same contracts in generation.

- [ ] Establish world distance units and coherent walk/train/car speeds. Estimate every leg using the same geometry and rules that execute it, including station access and boarding time.
- [ ] Build explicit sidewalk, crossing, entrance, platform and parking links. Keep walk/road/rail graphs separate with permitted transfer links. Replace the six-node graph and arbitrary access elbows.
- [ ] Make routing return graph revision, mode, edge sequence, distance, duration and a reason when unreachable. Handle same-place journeys as zero travel; use nearest valid access, not simply nearest node.
- [ ] Fix road/building/rail/water conflicts. Attach buildings to parcels and an oriented street frontage; place entrances and front paths accordingly.
- [ ] Plan from current logical location toward a commitment's deadline. Compare complete walk/train itineraries with timetable wait, transfer, capacity uncertainty and a modest arrival buffer.
- [ ] Persist the chosen plan and replan on a relevant event: missed train, closed destination, route invalidation or delay. Never teleport to satisfy a clock deadline; report late arrival.

**Done when:** an 08:00 worker leaves at a defensible time, walks only on connected public paths, catches a feasible service and actually reaches work. Missing that service produces an honest new ETA or alternative route.

## Step 4 — a complete day of believable activity

**Depends on:** 3. This closes the first slice in spec section 16.

- [ ] Replace the hour-based conditional chain with commitments and executable activities: breakfast, travel, work, buy food, eat, rest, socialize and pet care.
- [ ] Distinguish being at a place from doing an activity there. Require arrival, opening hours, capacity and basic affordances before an activity starts; give it a duration and effect.
- [ ] Separate hunger from food possession: shopping acquires food, eating relieves hunger. Recover rest through rest/sleep; make need rates and effects tunable and elapsed-time based.
- [ ] Implement real trips home and pet walks, with guardian/pet location consistency. Respect weekday/weekend schedules and overnight transitions.
- [ ] Add a bounded candidate scorer after hard constraints, with stable seeded tie-breaking. Store the decisive reasons and rejected alternatives for inspection.
- [ ] Replace routine tick messages with meaningful departure, arrival, activity, missed-service and missed-commitment events; keep per-person history.

**Done when:** watch breakfast → commute → work → shop → home → dinner/sleep over a full day, with a pet walk, no unexplained relocations, changing needs and intelligible decisions. Replaying the same saved starting state yields the same results.

## Step 5 — make the world readable and visually convincing

**Depends on:** 4; preserve small visual improvements made for train acceptance earlier.

- [ ] Add pan/zoom, follow selection, fit-town and readable label levels; supply keyboard selection and an accessible searchable entity/place list.
- [ ] Drive day/night lighting from world time. Add distinct stopped/walking/working/eating/resting/boarding animation states and reduced-motion handling.
- [ ] Define a coherent top-down art guide: scale, roof shapes, materials, shadows, outlines, palette and person/vehicle proportions. Build parameterized homes, apartments, shops, workplaces and stations.
- [ ] Improve frontage, sidewalks, rail ties/rails, platforms, benches, trees and street furniture. Prioritize streets people actually use. Add simple occupied-building roof cutaways where they clarify activity; full furnished interiors remain optional later.
- [ ] Expand inspectors: itinerary/ETA and next commitment, place hours/occupancy, train seats/service state, vehicle owner/location, and recent meaningful events.
- [ ] Show pause/speed, loading/reconnect/errors and current world selection clearly. Make failed time advances visible and recoverable.

**Done when:** the user can follow a person from home into a visibly occupied coach and into work without losing identity or context, at both street and town zoom. Review screenshots and a full browser journey, including pause and resize.

## Step 6 — generate a coherent 30–100-person town

**Depends on:** 3–5. Start at 30 residents; target 100 before considering the illustrative 400-resident town.

- [ ] Add a validated TownBrief and setup UI: seed, population, density/theme, geography and optional rail.
- [ ] Generate boundary/districts → major roads/rail → streets/blocks → parcels → buildings/entrances → paths/crossings/platforms → decoration → households/jobs/pets/assets.
- [ ] Use district constraints and access rules: mixed centre, residential streets, service/industrial edge, connected stations. Vary architecture from seeded parameters.
- [ ] Validate footprints against infrastructure, graph connectivity, job/shop reachability, job capacity, home capacity and rail availability. Explain invalid briefs and generation failures.
- [ ] Seed diverse but feasible households/jobs and warm up the world by running actual activities before the displayed start time. Do not place commuters at platforms solely because their deadline implies they should be there.
- [ ] Persist the brief and seeded generation decisions; expose create-new versus load-existing explicitly.

**Done when:** different seeds create visibly different valid towns; the same brief/seed/versions reproduce one; each inhabited building faces and connects to a street. A small representative seed sample runs a complete day successfully.

## Step 7 — assets, money and practical car travel

**Depends on:** 4 and 6.

- [ ] Add explicit home/business/vehicle ownership, integer-valued money accounts and balanced ledger transactions. Seed initial ownership, balances and stock.
- [ ] Pay wages once per defined earning event; purchases transfer money and inventory atomically and idempotently. No funds/stock means a different valid decision, not a fabricated purchase.
- [ ] Treat a car as an available, reachable asset: walk to parking, acquire exclusive use, drive on the road graph, park and walk to the destination.
- [ ] Add simple junction/crossing queues and parking capacity, without full driving physics. Compare car travel honestly against walking and transit.

**Done when:** a resident earns and spends money, food stock changes consistently, and two people cannot simultaneously drive one vehicle. A complete visible car trip starts and ends at valid parking.

## Step 8 — individual lives and small stories

**Depends on:** 4 and 7.

- [ ] Add bounded personality/interests, households and care responsibilities. Derive mood from needs and recent events rather than duplicating personality.
- [ ] Add directed affinity/trust/familiarity/tension relationships updated through real shared activities.
- [ ] Derive compact salient memories from consequential events; aggregate/decay routine detail. Let social invitations and obligations influence candidate choices.
- [ ] Build the town overview and filtered story feed: population, occupations, transport use, late arrivals, purchases and relationships. Explanations reference actual event/state evidence.

**Done when:** two otherwise similar residents make understandable different choices, a shared interaction changes a relationship, and their inspectors retain the relevant memory.

## Step 9 — durable saves, typed API and reproducibility

**Depends on:** contracts/version policy from 0; important events already retained since 4. Complete the broader storage work once those models are stable.

- [ ] Move queryable entities, graph data, ownership, relationships, activities and events into deliberate SQLModel tables with Alembic migrations. Keep snapshots/checkpoints and bounded JSON attributes where useful.
- [ ] Add save slots, explicit archival, schema/rule compatibility handling and checkpoint + command/event replay with defined determinism guarantees. Persist RNG strategy/state at the required boundaries.
- [ ] Make server response schemas authoritative; generate or explicitly version TypeScript types. Include train/infrastructure details in render and inspector contracts.
- [ ] Separate semantic render projection from full simulation state. Add event filtering and place details; validate domain commands rather than exposing generic state patches.
- [ ] Complete crash/reload/concurrent-update handling and migration checks against representative old saves. Update run instructions and trim verified-unused starter code.

**Done when:** reload preserves queues, exact seats, routes, activities, accounts and clock; an older supported save upgrades intentionally; replay matches; conflicting clients cannot silently overwrite progress.

## Step 10 — scale and optional depth

**Depends on:** a coherent, measured 100-resident MVP.

- [ ] Measure simulation step time, payload sizes, browser frame time and memory on a documented target machine; set budgets from evidence. Cache routes by graph version and stop recomputing every commute each minute.
- [ ] Move decision evaluation to relevant events/thresholds, add viewport culling and compact updates. Introduce streaming only if polling demonstrably limits the experience.
- [ ] Add local/background simulation detail levels while preserving logical location, arrival timing, occupancy and consequential events on promotion.
- [ ] Consider 400 residents, additional visual archetypes, weather and limited validated player commands only after the small-town experience works.
- [ ] Optional AI: validated brief suggestions, names/bios and grounded recaps. Keep generation and simulation independently playable and deterministic without an AI service.

**Done when:** the target population runs within measured budgets and promoting an offscreen person never changes their history or invents a location/interaction.

## Lean acceptance portfolio

Keep a small number of scenarios that target actual failure modes:

1. One continuous route with a corner, pause/resume and large versus small advances.
2. Ten queued riders, eight seats, later-service recovery, alight-before-board and save/reload aboard.
3. An 08:00 commitment reached through a valid walk/train trip; missed train causes late/replanned arrival.
4. Full-day needs, shopping/eating, return home and guardian/pet consistency across midnight.
5. A representative set of generated seeds with infrastructure, reachability and reproducibility checks.
6. Balanced wages/purchases and exclusive vehicle use once those systems exist.

Run relevant backend checks and frontend type/lint/build for each affected slice; use browser observation for train occupancy, continuity, camera and animation. Do not count a passing compile or an activity label assertion as proof that the scenario works.

**Recommended next implementation:** step 0, then steps 1 and 2 as the first coherent milestone. Its demonstration is simple: the same train follows the same route whether anyone is waiting or not, people board only during a real station stop, and the user can see every occupied seat.
