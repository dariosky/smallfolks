import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { verifyEmail } from "../api";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const code = searchParams.get("code") ?? "";
  const hasRequiredParams = Boolean(email && code);
  const [message, setMessage] = useState(
    hasRequiredParams
      ? "Checking your verification link..."
      : "That verification link is incomplete.",
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasRequiredParams) {
      return;
    }
    void verifyEmail({ email, code })
      .then((response) => {
        setMessage(response.detail);
      })
      .catch((requestError) => {
        setError(
          requestError instanceof Error ? requestError.message : "Unable to verify that email.",
        );
      });
  }, [code, email, hasRequiredParams]);

  return (
    <main className="auth-status-page">
      <section className="auth-card">
        <p className="eyebrow">Email verification</p>
        <h1>{error ? "Verification failed" : "Email verification"}</h1>
        <p className={error ? "form-error" : "form-success"}>{error ?? message}</p>
        <Link className="primary-button" to="/app">
          Continue
        </Link>
      </section>
    </main>
  );
}
