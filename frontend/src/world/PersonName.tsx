import type { Entity } from "../api/world";

export function PersonName({ people, personId, onSelect, fallback = "Unknown" }: {
  people: Entity[];
  personId?: string;
  onSelect?: (person: Entity) => void;
  fallback?: string;
}) {
  const person = people.find((item) => item.id === personId);
  return person && onSelect ? (
    <button className="person-name" type="button" onClick={() => onSelect(person)}>{person.name}</button>
  ) : <>{person?.name ?? fallback}</>;
}
