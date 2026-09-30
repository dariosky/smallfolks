import type { Entity, World } from "../api/world";

const money = (cents: number) => new Intl.NumberFormat("en", {
  style: "currency", currency: "EUR",
}).format(cents / 100);

export function TownHallWork({ world, onSelect }: {
  world: World;
  onSelect: (person: Entity) => void;
}) {
  // Projects are saved in the order citizens chose them, including older saves.
  const recent = (world.volunteering_projects ?? []).slice(-8).reverse();
  return (
    <section className="household-members townhall-work">
      <p className="eyebrow">Recent sponsored work</p>
      <p>Tree planting · 4 hours · €24 on completion</p>
      {recent.length ? (
        <ul>
          {recent.map((project) => {
            const person = world.people.find((item) => item.id === project.person_id);
            const date = project.started_at;
            const status = project.status === "completed"
              ? `Completed · ${money(project.wage_cents)} paid`
              : `${Math.floor(project.worked_seconds / 60)}/${Math.ceil(project.required_seconds / 60)} minutes worked · ${money(project.wage_cents)} on completion`;
            const details = (
              <>
                <span>{person?.name ?? "Former resident"}</span>
                <small>Tree planting · {status}</small>
                {date ? <small>Chosen {date.slice(0, 10)} at {date.slice(11, 16)}</small> : null}
              </>
            );
            return (
              <li key={project.id}>
                {person ? <button type="button" onClick={() => onSelect(person)}>{details}</button> : details}
              </li>
            );
          })}
        </ul>
      ) : <p>No one has chosen sponsored work yet.</p>}
    </section>
  );
}
