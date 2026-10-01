import type { Tree, Entity } from "../api/world";
import { PersonName } from "./PersonName";

const eventTimeFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function TreeDetails({
  tree,
  clock,
  people,
  onSelect,
}: {
  tree: Tree;
  clock: string;
  people: Entity[];
  onSelect: (person: Entity) => void;
}) {
  const days = tree.planted_at
    ? Math.max(0, Math.floor((Date.parse(clock) - Date.parse(tree.planted_at)) / 86400000))
    : null;
  return (
    <>
      <p>
        <strong>Age:</strong>{" "}
        {days === null
          ? "Unknown · planting date was not recorded"
          : days === 0
            ? "Planted today"
            : `${days} ${days === 1 ? "day" : "days"} since planting`}
      </p>
      {tree.planted_at ? (
        <p>
          <strong>Planted:</strong> {eventTimeFormatter.format(new Date(tree.planted_at))}
        </p>
      ) : null}
      <p>
        <strong>Planted by:</strong>{" "}
        <PersonName
          people={people}
          personId={tree.planted_by_id ?? undefined}
          onSelect={onSelect}
          fallback={tree.planted_by_name ?? "Unknown"}
        />
      </p>
      <p>
        <strong>Reason:</strong>{" "}
        {tree.planting_reason === "volunteering"
          ? "Volunteering work for Town Hall"
          : tree.planting_reason === "town_employee"
            ? "Town employee · municipal tree planting"
            : tree.planting_reason === "existing_landscape"
              ? "Existing landscape · planting history unknown"
              : "Unknown"}
      </p>
    </>
  );
}
