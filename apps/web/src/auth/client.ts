import { useAuth } from "@clerk/react";
import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useInvalidateSession, useSessionClosing } from "./session-actions";
import { ApiError } from "../lib/api";

export function useSessionApi() {
  const { getToken, userId } = useAuth();
  const navigate = useNavigate();
  const closing = useSessionClosing();
  const invalidate = useInvalidateSession();
  const cache = useQueryClient();
  const api = useCallback(
    async <T>(path: string, options: RequestInit = {}): Promise<T> => {
      function expireSession() {
        invalidate();
        const filter = {
          predicate: (query: { queryKey: readonly unknown[] }) =>
            !!userId && query.queryKey.includes(userId),
        };
        void cache.cancelQueries(filter);
        cache.removeQueries(filter);
        navigate("/session-expired", { replace: true });
      }
      if (closing) throw new ApiError(401, null);
      options.signal?.throwIfAborted();
      let token: string | null;
      try {
        token = await getToken();
      } catch {
        expireSession();
        throw new ApiError(401, null);
      }
      options.signal?.throwIfAborted();
      if (!token) {
        expireSession();
        throw new ApiError(401, null);
      }
      const request = (value: string) =>
        fetch(`/api/v1${path}`, {
          ...options,
          credentials: "omit",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            Authorization: `Bearer ${value}`,
          },
        });
      let response = await request(token);
      // A cached short-lived token may expire in transit. Refresh once through Clerk;
      // a missing/rejected fresh token still closes the session and clears private data.
      if (response.status === 401) {
        try {
          token = await getToken({ skipCache: true });
        } catch {
          token = null;
        }
        options.signal?.throwIfAborted();
        if (!token) {
          expireSession();
          throw new ApiError(401, response.headers.get("x-request-id"));
        }
        response = await request(token);
      }
      if (!response.ok) {
        if (response.status === 401) expireSession();
        throw new ApiError(response.status, response.headers.get("x-request-id"));
      }
      return (response.status === 204 ? undefined : await response.json()) as T;
    },
    [getToken, navigate, closing, invalidate, cache, userId],
  );
  return { api, userId };
}
