import { useAuth } from "../auth";

export function AuthUnavailablePage() {
  const { authLoadError, isAuthRetrying, retryAuthCheck } = useAuth();

  function handleRetry() {
    void retryAuthCheck();
  }

  return (
    <main className="auth-status-page">
      <section className="auth-card">
        <p className="eyebrow">Session error</p>
        <h1>Unable to load your account</h1>
        <p>{authLoadError ?? "The backend is not reachable right now."}</p>
        <button
          className="primary-button"
          disabled={isAuthRetrying}
          onClick={handleRetry}
          type="button"
        >
          {isAuthRetrying ? "Retrying..." : "Try again"}
        </button>
      </section>
    </main>
  );
}
