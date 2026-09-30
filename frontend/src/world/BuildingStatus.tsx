import type { BuildingOperatingState } from "../api/world";

function dateTime(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function BuildingStatus({ state }: { state: BuildingOperatingState }) {
  return (
    <section className="building-status">
      <p><strong>Status:</strong> {state.status}</p>
      <p>{state.reason}</p>
      {!state.is_open ? (
        <p><strong>Closed since:</strong> {state.closed_since ? dateTime(state.closed_since) : "Closure time was not recorded."}</p>
      ) : null}
      {state.next_open_at ? (
        <p><strong>Next scheduled opening:</strong> {dateTime(state.next_open_at)}</p>
      ) : null}
    </section>
  );
}
