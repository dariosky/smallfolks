import type { Entity, World } from "../api/world";

const money = (cents: number) =>
  new Intl.NumberFormat("en", {
    style: "currency",
    currency: "EUR",
  }).format(cents / 100);

const taskLabels = {
  tree_planting: "Tree planting",
  park_cleanup: "Park cleanup",
  community_gardening: "Community gardening",
  library_help: "Library help",
};

export function TownHallWork({
  world,
  onSelect,
}: {
  world: World;
  onSelect: (person: Entity) => void;
}) {
  // Projects are saved in the order citizens chose them, including older saves.
  const recent = (world.volunteering_projects ?? []).slice(-8).reverse();
  const municipalLabels = {
    ...taskLabels,
    social_visit: "Companionship visit",
  };
  const municipal = (world.municipal_projects ?? []).slice(-8).reverse();
  const handymen = world.people.filter(
    (person) =>
      person.workplace_id === "place:townhall" &&
      person.role === "Town handyman",
  );
  const day = world.clock?.slice(0, 10);
  const currentBudget = world.economy?.public_budget_date === day;
  const recipients = world.people.filter(
    (person) => day && person.support_paid_date === day,
  );
  return (
    <section className="household-members townhall-work">
      <p className="eyebrow">Town services and support</p>
      <p>
        Treasury: {money(world.economy?.treasury_cents ?? 0)} · Reserved work
        payments: {money(world.economy?.community_work_cents ?? 0)}
      </p>
      <p>
        Regional grants:{" "}
        {money(
          currentBudget ? (world.economy?.regional_grant_today_cents ?? 0) : 0,
        )}{" "}
        today · {money(world.economy?.regional_grant_total_cents ?? 0)} total
      </p>
      <p>
        Unemployment support: €24 per day from 08:00, shared with the household.
        Optional work earns extra.
      </p>
      <p>
        Support paid:{" "}
        {money(currentBudget ? (world.economy?.support_today_cents ?? 0) : 0)}{" "}
        today · {money(world.economy?.support_total_cents ?? 0)} total
      </p>
      {recipients.length ? (
        <p>
          Received today:{" "}
          {recipients.map((person, index) => (
            <span key={person.id}>
              {index ? ", " : ""}
              <button type="button" onClick={() => onSelect(person)}>
                {person.name}
              </button>
            </span>
          ))}
        </p>
      ) : (
        <p>No unemployment support paid today.</p>
      )}
      <p className="eyebrow">Town handymen</p>
      <p>
        Paid public shifts · €12/hour for work on site. Parks below 50%
        cleanliness come first, then companionship visits and library help, then
        tree planting.
      </p>
      {handymen.map((person) => (
        <p key={person.id}>
          <button type="button" onClick={() => onSelect(person)}>
            {person.name}
          </button>{" "}
          · {person.activity ?? "Awaiting assignment"}
        </p>
      ))}
      {municipal.length ? (
        <ul>
          {municipal.map((project) => {
            const person = world.people.find(
              (person) => person.id === project.person_id,
            );
            return (
              <li key={project.id}>
                <button
                  type="button"
                  onClick={() => person && onSelect(person)}
                >
                  <span>{person?.name ?? "Former employee"}</span>
                  <small>
                    {municipalLabels[project.kind]} ·{" "}
                    {project.status === "completed"
                      ? "Completed"
                      : project.status === "cancelled"
                        ? "No longer needed"
                        : `${Math.floor(project.worked_seconds / 60)}/${project.required_seconds / 60} minutes worked`}
                  </small>
                  {project.recipient_id ? (
                    <small>
                      Visiting{" "}
                      {world.people.find(
                        (person) => person.id === project.recipient_id,
                      )?.name ?? "a resident"}
                    </small>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
      <p className="eyebrow">Available community activities · 08:00–18:00</p>
      <p>Tree planting · 4 hours · €24 on completion</p>
      <p>Park cleanup · 1 hour · €6 on completion</p>
      <p>Community gardening · 2 hours · €12 on completion</p>
      <p>
        Library help · 1 hour · €6 on completion · during library opening hours
      </p>
      <p>
        Work depends on available sites, free time, and funding. Urgent needs
        and scheduled commitments take priority.
      </p>
      <p className="eyebrow">Recent sponsored work</p>
      {recent.length ? (
        <ul>
          {recent.map((project) => {
            const person = world.people.find(
              (item) => item.id === project.person_id,
            );
            const date = project.started_at;
            const status =
              project.status === "completed"
                ? `Completed · ${money(project.wage_cents)} paid`
                : `${Math.floor(project.worked_seconds / 60)}/${Math.ceil(project.required_seconds / 60)} minutes worked · ${money(project.wage_cents)} on completion`;
            const details = (
              <>
                <span>{person?.name ?? "Former resident"}</span>
                <small>
                  {taskLabels[project.kind ?? "tree_planting"]} · {status}
                </small>
                {date ? (
                  <small>
                    Chosen {date.slice(0, 10)} at {date.slice(11, 16)}
                  </small>
                ) : null}
              </>
            );
            return (
              <li key={project.id}>
                {person ? (
                  <button type="button" onClick={() => onSelect(person)}>
                    {details}
                  </button>
                ) : (
                  details
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p>No one has chosen sponsored work yet.</p>
      )}
    </section>
  );
}
