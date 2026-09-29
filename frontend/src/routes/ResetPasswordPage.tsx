import { type FormEvent, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { PasswordInput } from "../components/PasswordInput";

export function ResetPasswordPage() {
  const { consumePasswordReset, error, isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const email = searchParams.get("email") ?? "";
  const code = searchParams.get("code") ?? "";
  const expires = Number(searchParams.get("expires") ?? 0);

  if (isAuthenticated) {
    return <Navigate replace to="/app" />;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await consumePasswordReset({ email, code, expires, password });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-status-page">
      <section className="auth-card">
        <p className="eyebrow">Reset password</p>
        <h1>Choose a new password</h1>
        <form className="auth-form" onSubmit={onSubmit}>
          <PasswordInput
            autoComplete="new-password"
            label="New password"
            minLength={8}
            onChange={setPassword}
            required
            value={password}
          />
          {error ? <p className="form-error">{error}</p> : null}
          <button className="primary-button" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Saving..." : "Set new password"}
          </button>
        </form>
      </section>
    </main>
  );
}
