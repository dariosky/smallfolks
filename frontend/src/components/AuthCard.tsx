import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { API_PREFIX, getGoogleAuthConfig, requestMagicLogin, requestPasswordReset } from "../api";
import { useAuth } from "../auth";
import { PasswordInput } from "./PasswordInput";

type AuthMode = "login" | "register";

type GoogleCredentialResponse = {
  credential?: string;
};

type GoogleAccounts = {
  id: {
    cancel: () => void;
    initialize: (options: {
      callback: (response: GoogleCredentialResponse) => void;
      client_id: string;
      context: "signin" | "signup" | "use";
      itp_support: boolean;
    }) => void;
    prompt: () => void;
  };
};

declare global {
  interface Window {
    google?: {
      accounts: GoogleAccounts;
    };
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const GOOGLE_SCRIPT_SRC = "https://accounts.google.com/gsi/client";
let googleConfigRequest: Promise<string | null> | null = null;

function loadGoogleClientId() {
  if (!googleConfigRequest) {
    googleConfigRequest = getGoogleAuthConfig()
      .then((config) => config.client_id ?? null)
      .finally(() => {
        googleConfigRequest = null;
      });
  }
  return googleConfigRequest;
}

export function AuthCard() {
  const { clearError, error, login, loginWithGoogleCredential, register } = useAuth();
  const [mode, setMode] = useState<AuthMode>("register");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [magicMessage, setMagicMessage] = useState<string | null>(null);
  const [resetMessage, setResetMessage] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [googleClientId, setGoogleClientId] = useState(GOOGLE_CLIENT_ID ?? "");
  const oneTapInitialized = useRef(false);
  const authActions = useRef({ clearError, loginWithGoogleCredential });

  useEffect(() => {
    authActions.current = { clearError, loginWithGoogleCredential };
  }, [clearError, loginWithGoogleCredential]);

  const handleGoogleCredential = useCallback(async (response: GoogleCredentialResponse) => {
    if (!response.credential) {
      setGoogleError("Google sign-in did not return a credential.");
      return;
    }
    const { clearError, loginWithGoogleCredential } = authActions.current;
    clearError();
    setGoogleError(null);
    try {
      await loginWithGoogleCredential({ credential: response.credential });
    } catch {
      // The auth provider exposes the server message through `error`.
    }
  }, []);

  useEffect(() => {
    if (googleClientId) {
      return;
    }
    let cancelled = false;
    void loadGoogleClientId()
      .then((clientId) => {
        if (!cancelled) {
          setGoogleClientId(clientId ?? "");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setGoogleClientId("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [googleClientId]);

  useEffect(() => {
    const clientId = googleClientId;
    if (!clientId || oneTapInitialized.current) {
      return;
    }
    let cancelled = false;
    function initializeOneTap() {
      if (cancelled || !window.google?.accounts) {
        return;
      }
      oneTapInitialized.current = true;
      window.google.accounts.id.initialize({
        callback: (response) => {
          void handleGoogleCredential(response);
        },
        client_id: clientId,
        context: mode === "register" ? "signup" : "signin",
        itp_support: true,
      });
      window.google.accounts.id.prompt();
    }

    const existingScript = document.querySelector<HTMLScriptElement>(
      `script[src="${GOOGLE_SCRIPT_SRC}"]`,
    );
    if (existingScript) {
      if (window.google?.accounts) {
        initializeOneTap();
      } else {
        existingScript.addEventListener("load", initializeOneTap, { once: true });
      }
      return () => {
        cancelled = true;
        oneTapInitialized.current = false;
        existingScript.removeEventListener("load", initializeOneTap);
        window.google?.accounts.id.cancel();
      };
    }

    const script = document.createElement("script");
    script.async = true;
    script.defer = true;
    script.src = GOOGLE_SCRIPT_SRC;
    script.addEventListener("load", initializeOneTap, { once: true });
    document.head.append(script);
    return () => {
      cancelled = true;
      oneTapInitialized.current = false;
      script.removeEventListener("load", initializeOneTap);
      window.google?.accounts.id.cancel();
    };
  }, [googleClientId, handleGoogleCredential, mode]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage(null);
    setGoogleError(null);
    try {
      if (mode === "register") {
        setMessage(await register({ email, full_name: fullName, password }));
      } else {
        await login({ email, password });
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function continueWithGoogle() {
    clearError();
    setGoogleError(null);
    window.location.assign(`${API_PREFIX}/auth/google/start?mode=${encodeURIComponent(mode)}`);
  }

  async function sendMagicLink() {
    clearError();
    setMagicMessage(null);
    const response = await requestMagicLogin({ email });
    setMagicMessage(response.detail);
  }

  async function sendResetLink() {
    clearError();
    setResetMessage(null);
    const response = await requestPasswordReset({ email });
    setResetMessage(response.detail);
  }

  return (
    <section className="auth-card">
      <div className="auth-switcher">
        <button
          className={mode === "register" ? "is-active" : ""}
          onClick={() => {
            clearError();
            setMessage(null);
            setMode("register");
          }}
          type="button"
        >
          Create account
        </button>
        <button
          className={mode === "login" ? "is-active" : ""}
          onClick={() => {
            clearError();
            setMessage(null);
            setMode("login");
          }}
          type="button"
        >
          Log in
        </button>
      </div>

      {googleClientId ? (
        <button className="google-auth-button" onClick={continueWithGoogle} type="button">
          <span aria-hidden="true" className="google-auth-button__mark">
            G
          </span>
          Continue with Google
        </button>
      ) : null}

      <form className="auth-form" onSubmit={onSubmit}>
        {mode === "register" ? (
          <label>
            Full name
            <input
              autoComplete="name"
              onChange={(event) => setFullName(event.target.value)}
              required
              value={fullName}
            />
          </label>
        ) : null}

        <label>
          Email
          <input
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
        </label>

        <PasswordInput
          autoComplete={mode === "register" ? "new-password" : "current-password"}
          label="Password"
          minLength={8}
          onChange={setPassword}
          required
          value={password}
        />

        {error ? <p className="form-error">{error}</p> : null}
        {googleError ? <p className="form-error">{googleError}</p> : null}
        {message ? (
          <p className="form-success" role="status">
            {message}
          </p>
        ) : null}
        {magicMessage ? (
          <p className="form-success" role="status">
            {magicMessage}
          </p>
        ) : null}
        {resetMessage ? (
          <p className="form-success" role="status">
            {resetMessage}
          </p>
        ) : null}

        {mode === "login" ? (
          <div className="auth-inline-actions">
            <button onClick={() => void sendMagicLink()} type="button">
              Send magic link
            </button>
            <button onClick={() => void sendResetLink()} type="button">
              Forgot password?
            </button>
          </div>
        ) : null}

        <button className="primary-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Working..." : mode === "register" ? "Create account" : "Log in"}
        </button>
      </form>
    </section>
  );
}
