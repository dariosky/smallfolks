import type { Entity, Place } from "../api/world";

export function ShopPeople({ place, people, onSelect }: {
  place: Place;
  people: Entity[];
  onSelect: (person: Entity) => void;
}) {
  const employees = people.filter((person) => place.business?.status !== "bankrupt" && person.workplace_id === place.id && person.employment_status !== "out of work");
  const present = people.filter((person) =>
    person.target_place_id === place.id &&
    !person.route?.length && !person.direct_walk && !person.on_train && !person.in_vehicle_id && !person.car_trip &&
    Math.hypot(person.position.x - place.position.x, person.position.y - place.position.y) < 55,
  );
  const employeeIds = new Set(employees.map((person) => person.id));
  const visitors = present.filter((person) => !employeeIds.has(person.id));
  const list = (members: Entity[], attendance: boolean) => (
    <ul>
      {members.map((person) => (
        <li key={person.id}>
          <button onClick={() => onSelect(person)} type="button">
            <span>{person.name}</span>
            <small>{attendance ? person.activity : `${person.role ?? "Employee"} · ${present.some((member) => member.id === person.id) ? "Here now" : "Away"}`}</small>
          </button>
        </li>
      ))}
    </ul>
  );
  return (
    <section className="household-members shop-people">
      <p className="eyebrow">Employees</p>
      {employees.length ? list(employees, false) : <p>No current employees.</p>}
      <p className="eyebrow">Here now</p>
      {visitors.length ? list(visitors, true) : <p>No visitors are here right now.</p>}
    </section>
  );
}
