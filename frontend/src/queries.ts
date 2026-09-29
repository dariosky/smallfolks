import { queryOptions, useQuery } from "@tanstack/react-query";
import { getCurrentUser } from "./api";

export const currentUserQueryKey = ["auth", "me"] as const;

export const currentUserQueryOptions = queryOptions({
  queryKey: currentUserQueryKey,
  queryFn: getCurrentUser,
});

export function useCurrentUserQuery(enabled = true) {
  return useQuery({
    ...currentUserQueryOptions,
    enabled,
  });
}
