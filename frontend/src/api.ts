import type {
  GoogleAuthConfig,
  GoogleCredentialLoginInput,
  LoginInput,
  MagicLoginConsumeInput,
  PasswordResetConsumeInput,
  PasswordResetRequestInput,
  RegisterInput,
  UpdateUserInput,
  User,
  VerificationResponse,
} from "./schema";

export const API_PREFIX = import.meta.env.VITE_API_PREFIX || "/api";

export type ApiFieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  errors: ApiFieldErrors | null;
  status: number;

  constructor(message: string, status: number, errors: ApiFieldErrors | null = null) {
    super(message);
    this.name = "ApiError";
    this.errors = errors;
    this.status = status;
  }
}

function parseFieldErrors(value: unknown): ApiFieldErrors | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const entries = Object.entries(value).flatMap(([field, messages]) => {
    if (!Array.isArray(messages)) {
      return [];
    }
    const normalizedMessages = messages.flatMap((message) =>
      typeof message === "string" && message.trim() ? [message.trim()] : [],
    );
    return normalizedMessages.length ? [[field, normalizedMessages] as const] : [];
  });
  return entries.length ? Object.fromEntries(entries) : null;
}

async function apiFetch<T>(path: string, init?: globalThis.RequestInit): Promise<T> {
  const body = init?.body;
  const hasFormDataBody = typeof FormData !== "undefined" && body instanceof FormData;
  const headers = new Headers(init?.headers ?? {});
  if (!hasFormDataBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_PREFIX}${path}`, {
    credentials: "include",
    headers,
    ...init,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    let detail = "Request failed";
    let errors: ApiFieldErrors | null = null;
    try {
      const payload = (await response.json()) as {
        detail?: string;
        errors?: unknown;
      };
      detail = payload.detail || detail;
      errors = parseFieldErrors(payload.errors);
    } catch {
      // Ignore JSON parsing errors and fall back to the default message.
    }
    throw new ApiError(detail, response.status, errors);
  }

  return (await response.json()) as T;
}

export function getCurrentUser() {
  return apiFetch<User>("/auth/me").catch((error: unknown) => {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  });
}

export function login(payload: LoginInput) {
  return apiFetch<User>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function register(payload: RegisterInput) {
  return apiFetch<VerificationResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCurrentUser(payload: UpdateUserInput) {
  return apiFetch<User>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getGoogleAuthConfig() {
  return apiFetch<GoogleAuthConfig>("/auth/google/config");
}

export function loginWithGoogleCredential(payload: GoogleCredentialLoginInput) {
  return apiFetch<User>("/auth/google/one-tap", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logout() {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export function requestMagicLogin(payload: PasswordResetRequestInput) {
  return apiFetch<VerificationResponse>("/auth/magic-login/request", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function consumeMagicLogin(payload: MagicLoginConsumeInput) {
  return apiFetch<User>("/auth/magic-login/consume", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function requestPasswordReset(payload: PasswordResetRequestInput) {
  return apiFetch<VerificationResponse>("/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function consumePasswordReset(payload: PasswordResetConsumeInput) {
  return apiFetch<User>("/auth/password-reset/consume", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resendVerificationEmail() {
  return apiFetch<VerificationResponse>("/auth/send-verification-email", {
    method: "POST",
  });
}

export function verifyEmail(payload: { email: string; code: string }) {
  return apiFetch<VerificationResponse>("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
