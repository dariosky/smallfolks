import { replaceEqualDeep } from "@tanstack/react-query";
import { useWorldStream } from "../hooks/useWorldStream";
import { TownHallWork } from "../world/TownHallWork";
import { BuildingStatus } from "../world/BuildingStatus";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  advanceWorld,
  createWorld,
  getWorld,
  setBusinessPrice,
  setHouseholdContribution,
  setWorldRunning,
  takeOverBusiness,
  type Entity,
  type Place,
  type World,
} from "../api/world";
import {
  BankDetails,
  DealershipDetails,
  HomeDevelopment,
  ResidentProsperity,
} from "../world/ProsperityDetails";
import { TownMap } from "../world/TownMap";
import { readMapCamera, saveMapCamera } from "../world/mapCamera";
import { ShopPeople } from "../world/ShopPeople";
import { PersonName } from "../world/PersonName";

type Selection = Entity | Place;

function isEntity(selection: Selection): selection is Entity {
  return "activity" in selection || "state" in selection || "role" in selection;
}

function displayTime(clock: string) {
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
    weekday: "long",
  }).format(new Date(clock));
}

function money(cents: number) {
  return new Intl.NumberFormat("en", { style: "currency", currency: "EUR" }).format(cents / 100);
}

const eventTimeFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function scheduledTime(clock: string, scheduledAt: string) {
  return `${scheduledAt.slice(11, 16)}${scheduledAt.slice(0, 10) > clock.slice(0, 10) ? " tomorrow" : ""}`;
}

const PRICE_PERCENTS = [70, 80, 90, 100, 110, 120, 130];

export function TownPage() {
  const [world, updateWorld] = useState<World | null>(null);
  const setWorld = useCallback((next: World) => {
    updateWorld((previous) =>
      previous?.id === next.id && previous.revision > next.revision
        ? previous
        : replaceEqualDeep(previous, next),
    );
    setError("");
  }, []);
  const [selected, setSelected] = useState<Selection | null>(null);
  const [worldId, setWorldId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [camera, setCamera] = useState(readMapCamera);
  const zoom = camera.zoom;
  const setZoom = (update: (value: number) => number) =>
    setCamera((current) => ({ ...current, zoom: update(current.zoom) }));

  useEffect(() => {
    saveMapCamera(camera);
  }, [camera]);

  useEffect(() => {
    void createWorld()
      .then((next) => {
        setWorld(next);
        setWorldId(next.id);
        return resumeWorld(next);
      })
      .then(setWorld)
      .catch((reason: unknown) => {
        const detail = reason instanceof Error ? reason.message : "Request failed.";
        setError(`Cannot reach the town backend at http://127.0.0.1:5340. ${detail}`);
      });
  }, []);
  const reportStreamError = useCallback(() => {
    setError("Lost connection to the town backend.");
  }, []);
  useWorldStream(worldId, setWorld, reportStreamError);

  async function advance(minutes: number) {
    if (!world) return;
    try {
      // The server's live clock can advance between polling and a click. Manual
      // time travel is deliberately serialized server-side rather than rejected
      // for a harmless stale display revision.
      setWorld(await advanceWorld(world.id, minutes));
      setError("");
    } catch (reason: unknown) {
      const detail = reason instanceof Error ? reason.message : "Request failed.";
      setError(`Cannot advance the town clock. ${detail}`);
    }
  }

  async function toggleRunning() {
    if (!world) return;
    try {
      setWorld(
        await setWorldRunning(
          world.id,
          !world.simulation.running,
          world.simulation.speed,
          world.revision,
        ),
      );
    } catch {
      setWorld(await getWorld(world.id));
    }
  }

  async function changeContribution(percent: number) {
    if (!world) return;
    try {
      setWorld(await setHouseholdContribution(world.id, percent));
      setError("");
    } catch {
      setError("Could not update the household contribution.");
    }
  }

  async function submitTakeover(event: FormEvent<HTMLFormElement>, placeId: string) {
    event.preventDefault();
    if (!world) return;
    const form = new FormData(event.currentTarget);
    try {
      setWorld(
        await takeOverBusiness(
          world.id,
          placeId,
          String(form.get("buyer_id")),
          Number(form.get("price_percent")),
        ),
      );
      setError("");
    } catch {
      setError("That resident cannot take over the business at the current balance.");
    }
  }

  async function submitBusinessPrice(event: FormEvent<HTMLFormElement>, placeId: string) {
    event.preventDefault();
    if (!world) return;
    const form = new FormData(event.currentTarget);
    try {
      setWorld(await setBusinessPrice(world.id, placeId, Number(form.get("price_percent"))));
      setError("");
    } catch {
      setError("Could not change the business price.");
    }
  }

  async function resumeWorld(worldToResume: World): Promise<World> {
    try {
      return await setWorldRunning(
        worldToResume.id,
        true,
        worldToResume.simulation.speed,
        worldToResume.revision,
      );
    } catch {
      const current = await getWorld(worldToResume.id);
      if (current.simulation.running) return current;
      return setWorldRunning(current.id, true, current.simulation.speed, current.revision);
    }
  }

  const currentSelection =
    selected && world
      ? ([...world.people, ...world.pets, ...world.vehicles, ...world.places].find(
          (item) => item.id === selected.id,
        ) ?? selected)
      : selected;
  const selectedEntity = currentSelection && isEntity(currentSelection) ? currentSelection : null;
  const selectedPlace = currentSelection && !isEntity(currentSelection) ? currentSelection : null;
  const trainState = world?.trains?.[0]?.state;
  const selectedStation =
    selectedPlace?.kind === "station"
      ? trainState?.stations.find((station) => station.station_id === selectedPlace.id)
      : undefined;
  const selectedHousehold =
    selectedEntity?.household_id && world
      ? world.households.find((household) => household.id === selectedEntity.household_id)
      : undefined;
  const selectedHomeHousehold =
    selectedPlace?.kind === "home" && world
      ? world.households.find((household) => household.home_place_id === selectedPlace.id)
      : undefined;
  const selectedHomeMembers = selectedHomeHousehold
    ? (world?.people.filter((person) => selectedHomeHousehold.member_ids.includes(person.id)) ?? [])
    : [];
  return (
    <main className="town-shell">
      <header className="town-header">
        <div className="town-brand">
          <img src="/smallfolks.png" alt="" width="1447" height="1087" />
          <div>
            <h1>SmallFolks</h1>
          </div>
        </div>
      </header>
      {error ? <p className="error-state">{error}</p> : null}
      <section className="town-layout">
        <div className="map-card">
          {world ? (
            <TownMap
              onSelect={setSelected}
              selectedId={currentSelection?.id ?? null}
              world={world}
              zoom={zoom}
              onCameraChange={setCamera}
              position={camera.position}
              onPositionChange={(position) => setCamera((current) => ({ ...current, position }))}
            />
          ) : (
            <div className="map-loading">Building the town…</div>
          )}
          <div className="map-toolbar">
            <div className="clock">
              <span>{world ? displayTime(world.clock) : "Loading town…"}</span>
            </div>
            <div className="time-controls">
              <button
                className="primary-button"
                disabled={!world}
                onClick={() => void advance(15)}
                type="button"
              >
                +15 min
              </button>
              <button
                className="secondary-button"
                disabled={!world}
                onClick={() => void advance(60)}
                type="button"
              >
                +1 hour
              </button>
              <button
                className={
                  world?.simulation.running ? "secondary-button is-running" : "secondary-button"
                }
                disabled={!world}
                onClick={() => void toggleRunning()}
                type="button"
              >
                {world?.simulation.running ? "Pause" : "Resume"}
              </button>
            </div>
            <div className="zoom-controls" aria-label="Map zoom">
              <button
                className="secondary-button"
                type="button"
                aria-label="Zoom out"
                disabled={zoom <= 1}
                onClick={() => setZoom((value) => Math.max(1, value - 0.25))}
              >
                −
              </button>
              <output aria-label="Zoom level">{Math.round(zoom * 100)}%</output>
              <button
                className="secondary-button"
                type="button"
                aria-label="Zoom in"
                disabled={zoom >= 4}
                onClick={() => setZoom((value) => Math.min(4, value + 0.25))}
              >
                +
              </button>
            </div>
          </div>
        </div>
        {currentSelection && (
          <aside
            className="inspector"
            aria-label="Selection details"
            onKeyDown={(event) => {
              if (event.key === "Escape") setSelected(null);
            }}
          >
            <button
              className="inspector-close"
              type="button"
              aria-label="Close details"
              onClick={() => setSelected(null)}
            >
              ×
            </button>
          {currentSelection ? (
            <>
              <p className="eyebrow">
                {selectedEntity?.role ??
                  ("kind" in currentSelection ? labelsFor(currentSelection.kind) : "Place")}
              </p>
              <h2>{currentSelection.name}</h2>
              {selectedEntity ? (
                <>
                  <p className="activity">{selectedEntity.activity ?? selectedEntity.state}</p>
                  {selectedEntity.employment_status === "out of work" ? (
                    <p><strong>Employment:</strong> Out of work while the workplace is closed.</p>
                  ) : null}
                  {selectedEntity.support_paid_date ? (
                    <p><strong>Unemployment support:</strong> €24 received on {selectedEntity.support_paid_date} · {money(selectedEntity.support_total_cents ?? 0)} total, shared with the household.</p>
                  ) : null}
                  {selectedEntity.work_days ? (
                    <p><strong>Work days:</strong> {selectedEntity.work_days.map((day) => ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day]).join(", ")}</p>
                  ) : null}
                  <p className="why">
                    <strong>Why now?</strong>
                    {selectedEntity.explanation ??
                      "This vehicle is available at its current location."}
                  </p>
                  {selectedEntity.next_commitment ? (
                    <p>
                      <strong>Next:</strong> {selectedEntity.next_commitment}
                    </p>
                  ) : null}
                  {selectedEntity.train_trip ? (
                    <p>
                      <strong>Train trip:</strong> {selectedEntity.train_trip.phase} · {selectedEntity.train_trip.departure_id.replace("station:", "")} to {selectedEntity.train_trip.arrival_id.replace("station:", "")}
                    </p>
                  ) : null}
                  {selectedEntity.car_trip ? (
                    <p>
                      <strong>Car trip:</strong> {selectedEntity.car_trip.phase} · {world?.vehicles.find((vehicle) => vehicle.id === selectedEntity.car_trip?.vehicle_id)?.name ?? selectedEntity.car_trip.vehicle_id} to {world?.places.find((place) => place.id === selectedEntity.car_trip?.destination_id)?.name ?? selectedEntity.car_trip.destination_id}
                    </p>
                  ) : null}
                  {selectedEntity.kind === "vehicle" && selectedEntity.model === "sports" ? <p><strong>Model:</strong> Luxury sports car · 60% faster cruising</p> : null}
                  {selectedEntity.kind === "vehicle" ? (
                    <p>
                      <strong>Owner:</strong> <PersonName people={world?.people ?? []} personId={selectedEntity.owner_id} onSelect={setSelected} fallback="unknown" />
                      {selectedEntity.driver_id ? <> · Driven by <PersonName people={world?.people ?? []} personId={selectedEntity.driver_id} onSelect={setSelected} fallback={selectedEntity.driver_id} /></> : selectedEntity.reserved_by ? <> · Reserved by <PersonName people={world?.people ?? []} personId={selectedEntity.reserved_by} onSelect={setSelected} fallback={selectedEntity.reserved_by} /></> : " · Available"}
                    </p>
                  ) : null}
                  {selectedEntity.needs ? (
                    <div className="needs">
                      {Object.entries(selectedEntity.needs).map(([name, value]) => (
                        <div key={name}>
                          <span>{name === "walk_out" ? "needs walk" : name}</span>
                          <i>
                            <b style={{ width: `${value}%` }} />
                          </i>
                          <em>{value}</em>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {selectedEntity.walk_status ? (
                    <p>
                      <strong>Walk:</strong> {selectedEntity.walk_status}
                      {selectedEntity.accident_at_home ? " — cleanup needed" : ""}
                    </p>
                  ) : null}
                  {selectedHousehold ? (
                    <>
                      <ResidentProsperity world={world!} person={selectedEntity} />
                      <p><strong>Personal money:</strong> {money(selectedEntity.money_cents ?? 0)}</p>
                      <p><strong>Shared household money:</strong> {money(selectedHousehold.money_cents ?? 0)} ({world?.economy?.household_contribution_percent ?? 50}% of wages)</p>
                      <label>
                        Share of future wages for every household{" "}
                        <select
                          value={world?.economy?.household_contribution_percent ?? 50}
                          onChange={(event) => void changeContribution(Number(event.target.value))}
                        >
                          {[0, 25, 50, 75, 100].map((percent) => <option key={percent} value={percent}>{percent}%</option>)}
                        </select>
                      </label>
                      <p>
                        <strong>Household food:</strong>{" "}
                        {selectedHousehold.food_servings} servings for {selectedHousehold.member_ids.length}{" "}
                        people ({selectedHousehold.food_servings / selectedHousehold.member_ids.length} days)
                      </p>
                    </>
                  ) : null}
                  {selectedEntity.social_inclination !== undefined ? (
                    <p>
                      <strong>Social inclination:</strong>{" "}
                      {Math.round(selectedEntity.social_inclination * 100)}%
                    </p>
                  ) : null}
                  {selectedEntity.cinema_inclination !== undefined ? (
                    <p>
                      <strong>Cinema inclination:</strong>{" "}
                      {Math.round(selectedEntity.cinema_inclination * 100)}%
                    </p>
                  ) : null}
                </>
              ) : (
                <>
                  {selectedPlace?.operating_state ? (
                    <BuildingStatus state={selectedPlace.operating_state} />
                  ) : null}
                  {selectedPlace?.kind === "train" && trainState ? (
                    <section className="train-details">
                      <p><strong>Service:</strong> {trainState.service_state} · 06:00–00:00</p>
                      <p><strong>Doors:</strong> {trainState.doors_open ? "open" : "closed"} · {trainState.passenger_ids.length}/{trainState.capacity} seats occupied</p>
                      {trainState.carriages.map((carriage, index) => (
                        <p key={carriage.id}>
                          <strong>Coach {index + 1}:</strong> {carriage.seats.map((seat, seatIndex) => <span key={seat.id}>{seatIndex > 0 ? " · " : ""}{seat.passenger_id ? <PersonName people={world?.people ?? []} personId={seat.passenger_id} onSelect={setSelected} fallback={seat.passenger_id} /> : "empty"}</span>)}
                        </p>
                      ))}
                    </section>
                  ) : selectedStation ? (
                    <section className="station-details">
                      <p><strong>Next train:</strong> {scheduledTime(world!.clock, selectedStation.next_arrival_at)} arrival · {scheduledTime(world!.clock, selectedStation.next_departure_at)} departure</p>
                      <p><strong>Queue:</strong> {selectedStation.queue_length} waiting in arrival order</p>
                      <p><strong>Service hours:</strong> 06:00–00:00; train parks overnight.</p>
                      <ul>
                        {world?.station_queues?.find((queue) => queue.station_id === selectedStation.station_id)?.entries.map((entry) => {
                          const person = world.people.find((item) => item.id === entry.person_id);
                          return person ? <li key={entry.person_id}><button onClick={() => setSelected(person)} type="button">{person.name}</button></li> : null;
                        })}
                      </ul>
                    </section>
                  ) : null}
                  {selectedPlace?.kind === "home" ? (
                    selectedHomeHousehold ? (
                      <section className="household-members">
                        <p className="eyebrow">Household</p>
                        <p>{selectedHomeMembers.length} residents live here · {money(selectedHomeHousehold.money_cents ?? 0)} shared</p>
                        <ul>
                          {selectedHomeMembers.map((member) => (
                            <li key={member.id}>
                              <button onClick={() => setSelected(member)} type="button">
                                <span>{member.name}</span>
                                <small>{member.role}</small>
                              </button>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : (
                      <p className="why">This home is currently unoccupied.</p>
                    )
                  ) : null}
                  {selectedPlace?.kind === "home" && world ? <HomeDevelopment world={world} home={selectedPlace} onSelect={setSelected} /> : null}
                  {selectedPlace?.id === "place:townhall" && world ? <TownHallWork world={world} onSelect={setSelected} /> : null}
                  {selectedPlace?.kind === "park" && selectedPlace.cleanliness !== undefined ? <p><strong>Cleanliness:</strong> {selectedPlace.cleanliness}% · {selectedPlace.cleanup_sessions ?? 0} community cleanups</p> : null}
                  {selectedPlace?.id === "place:library" ? <p><strong>Community library help:</strong> {selectedPlace.library_help_sessions ?? 0} completed sessions</p> : null}
                  {selectedPlace?.id === "place:bank" && world ? <BankDetails world={world} onSelect={setSelected} /> : null}
                  {selectedPlace?.dealership ? <DealershipDetails workshop={selectedPlace} /> : null}
                  {selectedPlace && (selectedPlace.business || selectedPlace.kind === "workplace") ? (
                    <ShopPeople place={selectedPlace} people={world?.people ?? []} onSelect={setSelected} />
                  ) : null}
                  {selectedPlace?.business ? (
                    <section className="business-details">
                      <p><strong>Business:</strong> {selectedPlace.business.status} · {money(selectedPlace.business.balance_cents)}</p>
                      <p><strong>Owner:</strong> <PersonName people={world?.people ?? []} personId={selectedPlace.business.owner_id ?? undefined} onSelect={setSelected} fallback="None" /></p>
                      <p><strong>Price:</strong> {money(selectedPlace.business.unit_price_cents)} {selectedPlace.id === "place:supermarket" ? "per serving" : "per sale"}</p>
                      <p><strong>Wider town customers today:</strong> {selectedPlace.business.regional_visits_today} · {money(selectedPlace.business.regional_sales_cents_today)} sales</p>
                      {selectedPlace.business.status === "bankrupt" ? (
                        <>
                          <p><strong>Unpaid debt:</strong> {money(selectedPlace.business.debt_cents)}</p>
                          {world?.people.some((person) => (person.money_cents ?? 0) >= selectedPlace.business!.debt_cents + 8000) ? (
                          <form key={`takeover-${selectedPlace.id}`} onSubmit={(event) => void submitTakeover(event, selectedPlace.id)}>
                            <label>Resident
                              <select name="buyer_id" required>
                                {world?.people.filter((person) => (person.money_cents ?? 0) >= selectedPlace.business!.debt_cents + 8000).map((person) => (
                                  <option key={person.id} value={person.id}>{person.name} · {money(person.money_cents ?? 0)}</option>
                                ))}
                              </select>
                            </label>
                            <label>New price
                              <select name="price_percent" defaultValue={100}>
                                {PRICE_PERCENTS.map((percent) => <option key={percent} value={percent}>{percent}% · {money(selectedPlace.business!.base_unit_price_cents * percent / 100)}</option>)}
                              </select>
                            </label>
                            <p>Resident pays the debt and invests {money(8000)} in the business.</p>
                            <button className="primary-button" type="submit">Take over and reopen</button>
                          </form>
                          ) : <p>No resident can yet cover the debt and {money(8000)} working capital.</p>}
                        </>
                      ) : selectedPlace.business.owner_id ? (
                        <form key={`price-${selectedPlace.id}`} onSubmit={(event) => void submitBusinessPrice(event, selectedPlace.id)}>
                          <label>Price
                            <select name="price_percent" defaultValue={selectedPlace.business.price_percent}>
                              {PRICE_PERCENTS.map((percent) => <option key={percent} value={percent}>{percent}% · {money(selectedPlace.business!.base_unit_price_cents * percent / 100)}</option>)}
                            </select>
                          </label>
                          <button className="secondary-button" type="submit">Set price</button>
                        </form>
                      ) : null}
                    </section>
                  ) : null}
                </>
              )}
            </>
          ) : (
            <p>Select someone in town.</p>
          )}
          <section className="event-feed">
            <p className="eyebrow">Recent town events</p>
            {world?.events
              .slice()
              .reverse()
              .slice(0, 4)
              .map((event) => (
                <p className="event-feed-entry" key={`${event.at}-${event.summary}`}>
                  <time dateTime={event.at}>
                    {eventTimeFormatter.format(new Date(event.at))}
                  </time>
                  <span>{event.summary}</span>
                </p>
              ))}
          </section>
          </aside>
        )}
      </section>
    </main>
  );
}

function labelsFor(kind: string) {
  return (
    {
      home: "Home",
      bakery: "Bakery",
      shop: "Market",
      bar: "Bar",
      restaurant: "Restaurant",
      workplace: "Workplace",
      park: "Public park",
      vehicle: "Vehicle",
      pet: "Pet",
      station: "Station",
      train: "Train",
    }[kind] ?? kind
  );
}
