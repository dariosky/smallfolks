import { AuthCard } from "../components/AuthCard";

export function LandingPage() {
  return (
    <main className="page-shell">
      <section className="hero-copy">
        <p className="eyebrow">Starter app</p>
        <h1>SmallFolks</h1>
        <p className="hero-description">A calm, inspectable city-life simulation.</p>
        <ul className="hero-points">
          <li>FastAPI app factory with SQLModel and Alembic</li>
          <li>React 19, Vite, React Router, and TanStack Query</li>
          <li>Backend-served frontend build and a generic SSH deploy script</li>
        </ul>
      </section>
      <AuthCard />
    </main>
  );
}
