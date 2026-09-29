import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";

export function MagicLoginPage() {
  const { consumeMagicLogin, error, isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();
  const hasRequiredParams = Boolean(
    searchParams.get("email") &&
    searchParams.get("code") &&
    Number(searchParams.get("expires") ?? 0),
  );
  const [isSubmitting, setIsSubmitting] = useState(hasRequiredParams);

  useEffect(() => {
    const email = searchParams.get("email") ?? "";
    const code = searchParams.get("code") ?? "";
    const expires = Number(searchParams.get("expires") ?? 0);
    if (!hasRequiredParams) {
      return;
    }
    void consumeMagicLogin({ email, code, expires }).finally(() => {
      setIsSubmitting(false);
    });
  }, [consumeMagicLogin, hasRequiredParams, searchParams]);

  if (isAuthenticated) {
    return <Navigate replace to="/app" />;
  }

  if (!hasRequiredParams) {
    return (
      <main className="auth-status-page">
        <section className="auth-card">
          <p className="eyebrow">Sign in</p>
          <h1>Unable to sign in</h1>
          <p className="form-error">That sign-in link is incomplete.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="auth-status-page">
      <section className="auth-card">
        <p className="eyebrow">Sign in</p>
        <h1>{isSubmitting ? "Checking your link..." : "Unable to sign in"}</h1>
        {error ? <p className="form-error">{error}</p> : null}
      </section>
    </main>
  );
}
