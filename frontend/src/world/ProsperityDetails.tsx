import type { Entity, Loan, Place, World } from "../api/world";
import { PersonName } from "./PersonName";

const money = (cents: number) =>
  new Intl.NumberFormat("en", { style: "currency", currency: "EUR" }).format(cents / 100);

function LoanDetails({ loan }: { loan: Loan }) {
  return (
    <p>
      <strong>{loan.purpose.replace(/_/g, " ")} loan:</strong> {loan.status} ·{" "}
      {money(loan.remaining_cents)} remaining
      <br />
      {money(loan.installment_cents)} per game day · {loan.interest_percent}% fixed interest over{" "}
      {loan.term_days} days
      {loan.status !== "repaid" && (
        <>
          <br />
          Next installment: {loan.next_payment_date}
        </>
      )}
      {loan.arrears_cents > 0 && (
        <>
          <br />
          Overdue: {money(loan.arrears_cents)} · {loan.missed_payments} missed installments
        </>
      )}
    </p>
  );
}

export function ResidentProsperity({ world, person }: { world: World; person: Entity }) {
  const shops = world.places.filter((place) => place.business?.owner_id === person.id);
  const loans = world.loans?.filter((loan) => loan.borrower_id === person.id) ?? [];
  return (
    <section className="prosperity-details">
      {person.aspiration && (
        <p>
          <strong>Next investment:</strong> {person.aspiration}
        </p>
      )}
      {person.investment_goal === "mansion" && person.investment_target_cents && (
        <p><strong>Villa price:</strong> {money(person.investment_target_cents)}</p>
      )}
      {person.credit_score !== undefined && (
        <p>
          <strong>Credit score:</strong> {person.credit_score} / 850
        </p>
      )}
      {shops.length > 0 && (
        <p>
          <strong>Owned shops:</strong> {shops.map((shop) => shop.name).join(", ")}
        </p>
      )}
      {loans.map((loan) => (
        <LoanDetails key={loan.id} loan={loan} />
      ))}
    </section>
  );
}

export function HomeDevelopment({ world, home, onSelect }: { world: World; home: Place; onSelect?: (person: Entity) => void }) {
  const project = world.construction_projects?.find(
    (item) => item.id === home.construction_project_id,
  );
  const worker = world.people.find((person) => person.id === project?.worker_id);
  const owner = world.households.find((household) => household.id === home.owner_household_id);
  return (
    <section className="home-development">
      <p>
        <strong>Home:</strong> {home.house_style === "mansion" ? "Upper-class villa" : home.house_style === "large" ? "Large house" : "Small house"}
        {home.house_style === "mansion" ? " · Vast walled garden · Two parking spaces" : home.driveway ? " · Side driveway" : ""}
      </p>
      {home.sale_price_cents && (
        <p>
          <strong>For sale:</strong> {money(home.sale_price_cents)}
        </p>
      )}
      {owner && (
        <p>
          <strong>Owners:</strong>{" "}
          {owner.member_ids.map((id, index) => <span key={id}>
            {index > 0 ? ", " : ""}<PersonName people={world.people} personId={id} onSelect={onSelect} fallback={id} />
          </span>)}
        </p>
      )}
      {project && (
        <>
          <p>
            <strong>Building work:</strong> {project.status} ·{" "}
            {Math.round((project.worked_seconds / project.required_seconds) * 100)}% complete
          </p>
          <p>
            <strong>Builder:</strong> <PersonName people={world.people} personId={worker?.id} onSelect={onSelect} fallback="Waiting for an available carpenter" />
          </p>
          <p>
            {money(project.cost_cents)} paid ·{" "}
            {Math.round((project.required_seconds - project.worked_seconds) / 60)} minutes of work
            remaining{project.includes_driveway ? " · Includes a driveway" : ""}
          </p>
        </>
      )}
    </section>
  );
}

export function BankDetails({ world, onSelect }: { world: World; onSelect?: (person: Entity) => void }) {
  const loans = world.loans ?? [];
  return (
    <section className="bank-details">
      <p>
        Loans fund everyday and luxury sports cars, larger homes, villas and home improvements. Applicants need credit of at least 650,
        a job at an open workplace, and three completed earning days in the past week.
      </p>
      <p>
        Residents keep €200 in reserve and pay at least 40% up front. Repayments must fit within a
        quarter of their observed personal income. Loans charge 8% fixed interest over 60 game days;
        missed installments lower credit and stay due.
      </p>
      <p>
        <strong>Available funds:</strong> {money(world.economy?.bank_cents ?? 0)}
      </p>
      {loans.length ? (
        loans.map((loan) => (
          <div key={loan.id}>
            <strong><PersonName people={world.people} personId={loan.borrower_id} onSelect={onSelect} fallback={loan.borrower_id} /></strong>
            <LoanDetails loan={loan} />
          </div>
        ))
      ) : (
        <p>No loans issued yet.</p>
      )}
    </section>
  );
}


export function DealershipDetails({ workshop }: { workshop: Place }) {
  if (!workshop.dealership) return null;
  return (
    <section className="dealership-details">
      <p><strong>Cars for sale at the workshop</strong></p>
      <p>Everyday car · {money(workshop.dealership.standard_price_cents)}</p>
      <p>Luxury sports car · {money(workshop.dealership.sports_price_cents)} · 60% faster cruising</p>
      <p>Exclusive paints: ruby red, sapphire blue, emerald green, amethyst purple, and champagne gold.</p>
      <p>Residents visit the workshop to collect their car. Eligible buyers can finance either model with Willow Bank.</p>
      <p><strong>Cars sold:</strong> {workshop.dealership.cars_sold}</p>
    </section>
  );
}
