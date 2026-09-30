# SmallFolks: evaluation and implementation plan

Evaluated 2026-09-29 and updated through 2026-09-30 against [smallfolk-spec.md](smallfolk-spec.md), especially sections 2, 5–8, 11–14 and the first vertical slice in section 16.

This is a source-level evaluation with isolated simulation scenarios and frontend type/lint/build checks. It is not a browser visual acceptance pass or a production assessment. Status markers distinguish complete prerequisites from the current prototype's implemented slices; they do not turn a passing state assertion into a visual continuity guarantee.

## Assessment

The app is a useful visual and API scaffold, but it does not yet complete the specified first slice of a believable, observable day. Its most important next milestone is consistency: every visible movement, arrival, seat, activity and explanation must describe the same underlying world.

Repeated visual fixes have exposed the same architectural problem: simulation, routing and rendering each maintain parts of the truth. Adding more residents or richer sprites before resolving that will multiply contradictions. Keep the current stack and SVG prototype, but replace the time-of-day script incrementally with explicit activities, journeys and vehicle state.

Preserve the user's current direction: strict top-down, detailed cartoon art, buildings facing roads, automatic running on open, continuous movement, articulated trains, visible passengers and four seats per passenger coach. Full photorealism and detailed interiors remain beyond the spec's MVP; use selective roof cutaways and a consistent modular style first.

## Current coverage

| Spec area | Current evidence | Assessment |
| --- | --- | --- |
| App foundation | FastAPI, React/Vite, SQLModel snapshot, Alembic migrations, IDE launchers, backend 5340/frontend 5341, production HTML serving | Useful foundation; retain it |
| Tiny fixture | Fifteen named people, shared households, homes/services, Pippin, two parked vehicles, roads and SVG town | Present, still hand-authored |
| Clock and controls | Server-owned fixed-second tick, run/pause, speed, revision-safe manual advance and 250 ms observation | Implemented prototype; no event/delta stream |
| Movement | Pedestrian route points, persisted direct-care routes and sprite tweening | Improved; schedule phases still need a universal journey executor |
| Rail | Backend timetable/state, eight stable seats across two coaches, visible/selectable riders, local-speed access/egress | Prototype complete enough to observe; queues/doors/one geometry source remain |
| Individual life | Work shifts, household food shopping, eating, sleeping, low-key home activities, bar/cinema choices and shared dog care | Useful vertical slice; still a conditional schedule rather than the specified planner |
| Inspection | Live people/pet/household card, clickable household members, activity/need explanations | Good starting point; places/vehicles/train need real details |
| Persistence | Whole-world JSON snapshot in a relational table | Saves state; no durable event history/checkpoints or world migration policy |
| Generation | Seed recorded; fixed coordinates and population | Not procedural yet |
| Economy/social life | Saved personal/household/business balances, wages, paid visits, operating costs and a transfer ledger; no ownership, stock or relationships yet | First prototype slice |
| Observation tools | Static map extent; no camera, day/night, population panel or setup UI | Missing or partial |
| Quality | Twenty backend scenarios plus frontend type/lint/build tooling | Does not establish browser continuity or product acceptance |

## Findings that should drive the order

### P0 — correctness problems visible to the player

1. **Journey execution is still mixed.** The server now owns the clock/train position, and recent social, pet-care and final-home routes persist from a person's actual position. The broader work/home/shop/cinema schedule still contains time-window branches that can assume a person is at an expected prior location. Replace them with one persisted-leg executor before adding more venues.
2. **Train operations are not yet station operations.** Seats and carriage placement are stable and visible, but boarding is still clock-keyed. There are no doors, finite boarding time, FIFO queue state or honest missed-service recovery.
3. **Train geometry is still duplicated.** The backend's rail-distance arcs and frontend SVG loop are aligned by convention rather than derived from one path. Station access/egress now uses normal walking speed and a local rendered path, but platform geometry and entrances remain approximate.
4. **Needs now progress and have relief loops, but their policy is narrow.** Hunger triggers meals, rest triggers sleep, social need triggers bar visits and boredom can favour cinema. Their thresholds, opening hours, household availability and activity durations still need a shared tunable activity model.
5. **Manual snapshot loading can still expose a schedule discontinuity.** Current-position routes prevent the observed bar and pet teleports, but all schedule transitions need the same arrival check. A browser route-continuity review is mandatory before calling step 1 or 4 complete.
6. **The API is authoritative but polling-only.** Per-world revisions prevent stale mutation writes, while manual advance serializes server-side to coexist with running ticks. Keep polling until measured payload/latency evidence justifies a delta/WebSocket channel.

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

- The known fixture remains `world:poc-9-{seed}`. It has since grown into the current fifteen-resident prototype; the server clock and train state now drive the map, while step 2 retains the station-operation work.
- Current snapshots use `world_format_version: 1`, `generation_version: "poc-9"`, `simulation_version: "poc-1"`, and a command `revision`. Format 0 (no format/revision marker) is read through an additive in-memory migration and is persisted as format 1 only after a command changes state. Unknown future and retired formats return an explained compatibility error; unsupported-save archival/export is intentionally left for step 9.
- `simulation/contracts.py` now defines the planned JSON vocabulary. It is a type boundary, not a parallel runtime state machine: step 1 will make clock/revision authoritative and step 2 will populate train/carriage/seat/queue state.
- Backend tests now use a per-run temporary SQLite database and apply Alembic migrations before each scenario. The known fixture is the reproducible baseline. The captured behaviour remains intentionally incomplete: some scripted phase transitions still need universal persisted-leg execution, and train queues are not yet modelled.
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
- Journey objects now accompany the existing walk/train route data as an interim persisted contract. Direct routes are persisted for pet care, return-home and social/cinema recovery from an unexpected current position; the current route graph and schedule still need the step’s full leg-completion/replanning rewrite, so this step is not yet complete.
- 2026-09-30 movement pass: work and lunch wait for actual arrival; evening grocery, cinema and bar visits now persist travel/activity/return phases, and their durations start on arrival. Walking and pet-care routes retain a leg with distance and progress through save/reload. An interrupted route is replanned from the person's current position. New fixtures declare simulation version `poc-2`; existing `poc-1` snapshots keep their identity and gain the additive fields as they advance.
- The fixture starts at 07:30, too late for several people to walk from home to the 07:33 Market Square train. They now miss it instead of appearing at the platform. The clock-keyed train branch still needs step 2's later-service queue and boarding recovery; train access/egress and pedestrian movement do not yet share one full journey executor. Browser continuity remains unverified.

## Step 2 — finish the train, queues and visible passengers

**Depends on:** 1. This completes the outstanding train request before expanding the town.

- [ ] Store one rail path and use it for track drawing, arc-length traversal, coach headings and timetable distances. Remove demand-driven train positioning and the independent frontend train clock.
- [x] Model service states: travelling → approaching → stopped/doors open → boarding complete → departing. Progress around the loop continuously, including wraparound and day boundaries, with or without passengers. The train now parks at Market Square from 00:00 to 06:00 with doors closed.
- [x] Give the existing two passenger coaches four explicit seats each (eight total; locomotive excluded). Persist `train_id`, `car_id`, `seat_id` and passenger ID; do not repack seats when another person leaves.
- [x] Maintain station queues ordered by actual arrival time with deterministic tie-breaking. Alight first, then board eligible waiting people into free seats while the train is stopped at that platform. Include finite boarding time.
- [ ] Keep overflow passengers visibly queued for the next actual service. Missing a train must not complete a ride or teleport someone to the destination. Allow replanning and truthful lateness.
- [x] Show individual seated people through open/cutaway coach roofs. Keep identity colours and selection; click a rider to inspect the same person. Show coach occupancy, queue length and next train in station/train inspectors.
- [ ] Align platform geometry with coach doors, queue slots and safe pedestrian access. Render boarding/alighting at the same presentation time as train arrival/departure so network interpolation cannot make people vanish early.

**Done when:** a ten-person crowd fills eight seats, leaves two visible on the platform, and boards those two on a later service. The train takes the same path/timing in an empty-world run. Each rider is visible in a stable seat, alights only at their stop, and survives save/reload while aboard. Verify this in the browser, not only by inspecting state.

### Step 2 progress record (2026-09-30)

- The frontend no longer owns a train clock: it renders the server's scheduled rail distance and shows individual, selectable riders in stable carriage/seat slots. The two passenger coaches hold four people each.
- Train access and egress use the normal walking speed. A commuter remains on the final local station leg after the nominal shift time instead of being snapped to work.
- The 2026-09-30 station pass adds persisted FIFO queues, 15-second boarding slots, alight-before-board, eight explicit stable seats, later-service overflow recovery, selectable station/train inspectors, and open-door cues. A ten-person isolated scenario fills eight seats, leaves two queued, then boards those two on the next Market Square service; save/reload preserves the queue and occupied seats. Empty and loaded trains share the same timetable position.
- Folk Loop now completes its last loop at Market Square at midnight, remains parked with doors closed until 06:00, and advertises the next valid departure. Trip choice includes access, timetable wait, ride and egress; a queued resident sees the earliest work ETA and lateness. New fixtures use simulation version `poc-3`; old snapshots gain additive track/station metadata without replacing their identity.
- Queue order now appears as numbered markers beside each platform. After a missed boarding window, residents compare the next train's earliest arrival with walking from their current position; they leave the queue and walk if that saves more than four minutes. Residents for whom the next train remains useful stay in FIFO order for the later service. The inspector labels the next scheduled departure as seat-dependent. Browser continuity and physical platform access still need acceptance work.
- Step 2 remains open for browser continuity and queue/platform visual acceptance. The backend rail geometry now supplies the rendered track and coach position, while timetable segment durations are still explicit values rather than derived from graph edges.

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

### Step 4 prototype progress (2026-09-30)

- Implemented slices: shared household food servings and alternating grocery shoppers; shopping duration proportional to servings; moving shoppers; meal-driven hunger relief; sleep-driven rest relief; at-home reading/gardening/calls/chores/hobbies; boredom/social-driven bar or cinema choices; evening bar/cinema staffing; shared household dog care with a 12-hour walk autonomy, proactive walk, accident cleanup and rotating owners.
- These slices are deliberately not marked complete. They still run through a conditional schedule instead of commitments and general activities, and household food is not yet an inventory/transaction model. The next implementation should extract the existing decisions into persisted activities and make every transition arrival-gated.

## Step 5 — make the world readable and visually convincing

**Depends on:** 4; preserve small visual improvements made for train acceptance earlier.

- [ ] Add pan/zoom, follow selection, fit-town and readable label levels; supply keyboard selection and an accessible searchable entity/place list.
- [ ] Drive day/night lighting from world time. Add distinct stopped/walking/working/eating/resting/boarding animation states and reduced-motion handling.
- [ ] Define a coherent top-down art guide: scale, roof shapes, materials, shadows, outlines, palette and person/vehicle proportions. Build parameterized homes, apartments, shops, workplaces and stations.
- [ ] Improve frontage, sidewalks, rail ties/rails, platforms, benches, trees and street furniture. Prioritize streets people actually use. Add simple occupied-building roof cutaways where they clarify activity; full furnished interiors remain optional later.
- [ ] Expand inspectors: itinerary/ETA and next commitment, place hours/occupancy, train seats/service state, vehicle owner/location, and recent meaningful events.
- [ ] Show pause/speed, loading/reconnect/errors and current world selection clearly. Make failed time advances visible and recoverable.

**Done when:** the user can follow a person from home into a visibly occupied coach and into work without losing identity or context, at both street and town zoom. Review screenshots and a full browser journey, including pause and resize.

### Step 5 prototype progress (2026-09-30)

- Implemented visual slices: interpolated map updates, visible groceries, beer/social animation, role-specific work marks, eating and sleep indicators, reduced-motion handling, clickable household members and selectable train riders.
- The next visual acceptance work remains pan/zoom/follow, place/train inspectors, day/night, a browser continuity pass, and correcting any route that still appears to snap under real running playback.

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
- [x] Treat a car as an available, reachable asset: walk to parking, acquire exclusive use, drive on the road graph, park and walk to the destination.
- [ ] Add simple junction/crossing queues and parking capacity, without full driving physics. Compare car travel honestly against walking and transit.

**Done when:** a resident earns and spends money, food stock changes consistently, and two people cannot simultaneously drive one vehicle. A complete visible car trip starts and ends at valid parking.

### Economy prototype progress (2026-09-30)

- The fixed town now seeds integer-cent personal, shared-household, business and treasury balances. Wages are paid for actual 15-minute work blocks. A saved town-wide contribution percentage (default 50%, adjustable in the inspector) splits each wage between the worker and the household.
- Grocery trips spend shared household money; bar and cinema visits spend personal money. Each arrival transfers money once to the venue and grocery servings increase only after payment. Businesses pay daily operating costs and wages; an insolvent business closes and stops accepting visits or providing work.
- Bruno's paid gardening is assigned to Fern Florist. Gardening at home remains a hobby. Existing `poc-9` saves receive the corrected workplace and additive accounts in memory, persisted on their next command.
- This first economic loop did not complete step 7: stock, detailed ownership, public finance policy, job loss/re-employment and practical car travel remain open. Rates are fixture parameters; the snapshot retains the latest 200 transfers until a durable history/checkpoint policy is added.

### Business recovery and pricing (2026-09-30)

- The fifteen rendered residents do not provide enough customer visits to cover five shops' wages. A deterministic hourly customer count now represents the rest of the town, with separate ledger receipts and supply costs. Staffed businesses receive this income only while open; visible residents' purchases remain separate, pay supply costs, and still raise income. The inspector labels the wider-town customers so they are not mistaken for people on the map.
- Each business has a saved unit price. Higher prices reduce expected customer count; the current price affects grocery, bar and cinema payments as well as wider-town sales. A resident can take over a closed business by paying its recorded unpaid bills and investing €80, then choosing a price. At 09:00, an affordable resident may also choose an economically viable takeover, preferring former employees. The business reopens with an owner, and retained profits can pay a weekly dividend after a two-day expense reserve.
- Closed workers are marked out of work and look for a next step during ordinary home time. The previous closure records lacked exact debt claims, so they receive one conservative legacy unpaid bill inferred from the closure event; new closures record the exact creditor and amount. The saved `poc-9` gardener assignment to the park also upgrades to Fern Florist without moving Bruno's current position.
- This is a compact fixture demand model, not a detailed supply chain or a guarantee that every price and staffing choice is profitable. Browser continuity, broader generation, inventory, business ownership contracts and full job mobility remain open.

### Car travel progress (2026-09-30)

- The existing cars now belong to Lea and Lucas as drivable assets. For a distant work or evening destination, an owner compares walking, train service where relevant, and a complete car trip. The car trip reserves the vehicle, walks from the resident's actual position to parking, drives through connected road segments, parks near the destination, and walks the last leg. A car at work can be used for the return home; short trips stay on foot.
- Vehicle and driver positions, route progress, reservation, and the current trip phase persist through save/reload. The map shows the moving car with its driver inside using a rotatable top-down sprite with wheels on both sides; the inspectors show the owner, reservation, driver, and trip phase. New fixtures use `poc-4`; older snapshots keep their version and gain trip fields only when a car is used.
- This completes the basic exclusive car workflow. Junction queues, shared household borrowing, explicit parking capacities, road traffic, and browser visual acceptance remain open.

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

## Recommended next implementation

1. Run step 2's browser acceptance: ten-person crowd, visible platform positions, open doors, stable coach seats, overflow's later boarding or walking replan, midnight stop and 06:00 restart. Correct any visual discontinuity.
2. Unify the remaining train and pedestrian legs into one journey executor, including route continuity for corners, pause and delayed observations.
3. Convert the step 4 prototype slices into typed commitments/activities with explicit duration, opening hours and effects. Preserve household food and dog-care behaviour while making it reproducible and inspectable.
4. Run the first browser acceptance pass from step 5: pause/resume, a full train trip, social/cinema outing, dog walk, large manual advance and two-tab observation. Record any remaining visual discontinuity before expanding generation or economy.

### Larger city layout (2026-09-30)

- New `city-10` worlds contain 30 residents across 15 occupied households, with single residents, couples, and three- and four-person shared homes. Larger households use the existing larger house artwork.
- The map extends to 1200 by 1000, with a southern residential neighborhood and street access to every building entrance. School placement avoids Grand Avenue.
- Folk Loop now follows a winding closed route through the center and western residential district. Track rendering, station distances, train positions and coach positions share that geometry. Existing world IDs remain saved separately.
