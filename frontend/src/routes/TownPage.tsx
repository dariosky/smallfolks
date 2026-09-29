import { useEffect, useState } from "react";
import {
  advanceWorld,
  createWorld,
  getWorld,
  setWorldRunning,
  type Entity,
  type Place,
  type World,
} from "../api/world";
import { TownMap } from "../world/TownMap";

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

export function TownPage() {
  const [world, setWorld] = useState<World | null>(null);
  const [selected, setSelected] = useState<Selection | null>(null);
  const [worldId, setWorldId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void createWorld()
      .then((next) => {
        setWorld(next);
        setWorldId(next.id);
        setSelected(next.people[0]);
        return resumeWorld(next);
      })
      .then(setWorld)
      .catch((reason: unknown) => {
        const detail = reason instanceof Error ? reason.message : "Request failed.";
        setError(`Cannot reach the town backend at http://127.0.0.1:5340. ${detail}`);
      });
  }, []);
  useEffect(() => {
    if (!worldId) return undefined;
    const timer = window.setInterval(() => {
      void getWorld(worldId)
        .then(setWorld)
        .catch(() => setError("Lost connection to the town backend."));
    }, 250);
    return () => window.clearInterval(timer);
  }, [worldId]);

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
      return setWorldRunning(
        current.id,
        true,
        current.simulation.speed,
        current.revision,
      );
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
  const selectedHousehold =
    selectedEntity?.household_id && world
      ? world.households.find((household) => household.id === selectedEntity.household_id)
      : undefined;
  const selectedHomeHousehold =
    selectedPlace?.kind === "home" && world
      ? world.households.find((household) => household.home_place_id === selectedPlace.id)
      : undefined;
  const selectedHomeMembers = selectedHomeHousehold
    ? world?.people.filter((person) => selectedHomeHousehold.member_ids.includes(person.id)) ?? []
    : [];
  return (
    <main className="town-shell">
      <header className="town-header">
        <div>
          <h1>SmallFolks</h1>
          <p>A connected town with lives in motion.</p>
        </div>
        <div className="clock">
          <span>{world ? displayTime(world.clock) : "Loading town…"}</span>
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
            />
          ) : (
            <div className="map-loading">Building the town…</div>
          )}
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
              className={world?.simulation.running ? "secondary-button is-running" : "secondary-button"}
              disabled={!world}
              onClick={() => void toggleRunning()}
              type="button"
            >
              {world?.simulation.running ? "Pause" : "Resume"}
            </button>
          </div>
        </div>
        <aside className="inspector">
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
                    <p>
                      <strong>Household food:</strong>{" "}
                      {selectedHousehold.food_servings} servings for {selectedHousehold.member_ids.length}{" "}
                      people ({selectedHousehold.food_servings / selectedHousehold.member_ids.length} days)
                    </p>
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
                  <p className="why">
                    A semantic place: {labelsFor(currentSelection.kind)}.
                  </p>
                  {selectedPlace?.kind === "home" ? (
                    selectedHomeHousehold ? (
                      <section className="household-members">
                        <p className="eyebrow">Household</p>
                        <p>{selectedHomeMembers.length} residents live here</p>
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
                <p key={`${event.at}-${event.summary}`}>
                  <time>{event.at}</time>
                  {event.summary}
                </p>
              ))}
          </section>
        </aside>
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
      workplace: "Workplace",
      park: "Public park",
      vehicle: "Vehicle",
      pet: "Pet",
    }[kind] ?? kind
  );
}
