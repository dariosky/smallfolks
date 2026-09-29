/* eslint-disable react-refresh/only-export-components */
import { useQueryClient } from "@tanstack/react-query";
import { createContext, type PropsWithChildren, useContext, useState } from "react";
import {
  consumeMagicLogin,
  consumePasswordReset,
  login,
  loginWithGoogleCredential,
  logout,
  register,
  updateCurrentUser,
} from "./api";
import { currentUserQueryKey, useCurrentUserQuery } from "./queries";
import type {
  GoogleCredentialLoginInput,
  LoginInput,
  MagicLoginConsumeInput,
  PasswordResetConsumeInput,
  RegisterInput,
  UpdateUserInput,
  User,
} from "./schema";

type AuthContextValue = {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  authLoadError: string | null;
  isAuthRetrying: boolean;
  error: string | null;
  consumeMagicLogin: (payload: MagicLoginConsumeInput) => Promise<void>;
  consumePasswordReset: (payload: PasswordResetConsumeInput) => Promise<void>;
  login: (payload: LoginInput) => Promise<void>;
  loginWithGoogleCredential: (payload: GoogleCredentialLoginInput) => Promise<void>;
  register: (payload: RegisterInput) => Promise<string>;
  updateUser: (payload: UpdateUserInput) => Promise<User>;
  logout: () => Promise<void>;
  retryAuthCheck: () => Promise<void>;
  clearError: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const currentUserQuery = useCurrentUserQuery();

  async function refreshCurrentUser() {
    await queryClient.invalidateQueries({ queryKey: currentUserQueryKey });
    await queryClient.refetchQueries({ queryKey: currentUserQueryKey });
  }

  const value: AuthContextValue = {
    user: currentUserQuery.data ?? null,
    isAuthenticated: Boolean(currentUserQuery.data),
    isLoading: currentUserQuery.isLoading,
    authLoadError: currentUserQuery.isError
      ? errorMessage(currentUserQuery.error, "Unable to reach SmallFolks right now.")
      : null,
    isAuthRetrying: currentUserQuery.isFetching,
    error,
    consumeMagicLogin: async (payload) => {
      setError(null);
      try {
        await consumeMagicLogin(payload);
        await refreshCurrentUser();
      } catch (requestError) {
        setError(errorMessage(requestError, "Unable to use that sign-in link."));
        throw requestError;
      }
    },
    consumePasswordReset: async (payload) => {
      setError(null);
      try {
        await consumePasswordReset(payload);
        await refreshCurrentUser();
      } catch (requestError) {
        setError(errorMessage(requestError, "Unable to reset your password."));
        throw requestError;
      }
    },
    login: async (payload) => {
      setError(null);
      try {
        await login(payload);
        await refreshCurrentUser();
      } catch (requestError) {
        setError(errorMessage(requestError, "Unable to log in."));
        throw requestError;
      }
    },
    loginWithGoogleCredential: async (payload) => {
      setError(null);
      try {
        await loginWithGoogleCredential(payload);
        await refreshCurrentUser();
      } catch (requestError) {
        setError(errorMessage(requestError, "Unable to log in with Google."));
        throw requestError;
      }
    },
    register: async (payload) => {
      setError(null);
      try {
        const result = await register(payload);
        await refreshCurrentUser();
        return result.detail;
      } catch (requestError) {
        setError(errorMessage(requestError, "Unable to register."));
        throw requestError;
      }
    },
    updateUser: async (payload) => {
      setError(null);
      try {
        const user = await updateCurrentUser(payload);
        queryClient.setQueryData(currentUserQueryKey, user);
        return user;
      } catch (requestError) {
        setError(errorMessage(requestError, "Unable to update your profile."));
        throw requestError;
      }
    },
    logout: async () => {
      setError(null);
      await logout();
      queryClient.setQueryData(currentUserQueryKey, null);
    },
    retryAuthCheck: async () => {
      await currentUserQuery.refetch();
    },
    clearError: () => setError(null),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
