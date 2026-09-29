import { useEffect, useState } from "react";
import { advanceWorld, createWorld, type Entity, type Place, type World } from "../api/world";
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
  const [running, setRunning] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    void createWorld()
      .then((next) => {
        setWorld(next);
        setSelected(next.people[0]);
      })
      .catch((reason: unknown) => {
        const detail = reason instanceof Error ? reason.message : "Request failed.";
        setError(`Cannot reach the town backend at http://127.0.0.1:5340. ${detail}`);
      });
  }, []);
  useEffect(() => {
    if (!running || !world) return undefined;
    const timer = window.setInterval(() => {
      void advanceWorld(world.id, 1)
        .then(setWorld)
        .catch(() => setRunning(false));
    }, 1300);
    return () => window.clearInterval(timer);
  }, [running, world]);

  async function advance(minutes: number) {
    if (!world) return;
    setWorld(await advanceWorld(world.id, minutes));
  }

  const currentSelection =
    selected && world
      ? ([...world.people, ...world.pets, ...world.vehicles, ...world.places].find(
          (item) => item.id === selected.id,
        ) ?? selected)
      : selected;
  const selectedEntity = currentSelection && isEntity(currentSelection) ? currentSelection : null;
  return (
    <main className="town-shell">
      <header className="town-header">
        <div>
          <p className="eyebrow">Fixed-seed proof of concept</p>
          <h1>Smallfolk</h1>
          <p>A connected town with lives in motion.</p>
        </div>
        <div className="clock">
          <span>{world ? displayTime(world.clock) : "Loading town…"}</span>
          <small>
            seed {world?.seed ?? "—"} · {world?.generation_version ?? "—"}
          </small>
        </div>
      </header>
      {error ? <p className="error-state">{error}</p> : null}
      <section className="town-layout">
        <div className="map-card">
          {world ? (
            <TownMap
              onSelect={setSelected}
              running={running}
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
              className={running ? "secondary-button is-running" : "secondary-button"}
              disabled={!world}
              onClick={() => setRunning(!running)}
              type="button"
            >
              {running ? "Pause" : "Resume"}
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
                          <span>{name}</span>
                          <i>
                            <b style={{ width: `${value}%` }} />
                          </i>
                          <em>{value}</em>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="why">
                  A semantic place: {labelsFor(currentSelection.kind)}. Click a resident to inspect
                  their activity and decision trace.
                </p>
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
      workplace: "Workplace",
      park: "Public park",
      vehicle: "Vehicle",
      pet: "Pet",
    }[kind] ?? kind
  );
}
