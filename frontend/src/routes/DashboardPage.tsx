import { useAuth } from "../auth";
import { getInitials } from "../logic/getInitials";

export function DashboardPage() {
  const { logout, user } = useAuth();

  if (!user) {
    return null;
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div className="avatar-chip">{getInitials(user.full_name)}</div>
        <div>
          <p className="eyebrow">Signed in</p>
          <h1>{user.full_name}</h1>
          <p className="subtle-text">{user.email}</p>
        </div>
        <button className="secondary-button" onClick={() => void logout()} type="button">
          Log out
        </button>
      </header>

      <section className="dashboard-grid">
        <article className="panel">
          <p className="eyebrow">Backend contract</p>
          <h2>Frontend is served by FastAPI</h2>
          <p>
            The backend mounts compiled assets from <code>frontend/dist</code> and serves the SPA
            fallback when <code>ENABLE_HTML_SERVING</code> is enabled.
          </p>
        </article>
        <article className="panel">
          <p className="eyebrow">Next steps</p>
          <h2>Replace the starter domain</h2>
          <p>
            Add your models and routes under <code>backend/</code>, then extend
            <code>frontend/src/api.ts</code> and <code>frontend/src/queries.ts</code>.
          </p>
        </article>
      </section>
    </main>
  );
}
