import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useClerk, useAuth } from "@clerk/react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { clearAuthTarget } from "./return-target";

const STORAGE_KEY = "orqentra.logout-barrier";
function savedBarrier(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}
function storeBarrier(session: string | null) {
  try {
    if (session) sessionStorage.setItem(STORAGE_KEY, session);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* In-memory denial still applies if browser storage is unavailable. */
  }
}
const Closing = createContext({
  closing: false,
  pending: false,
  failed: false,
  begin: () => {},
  invalidate: () => {},
  setPending: (_value: boolean) => {},
  setFailed: (_value: boolean) => {},
});
export const useSessionClosing = () => useContext(Closing).closing;
export const useInvalidateSession = () => useContext(Closing).invalidate;
export function SessionActions({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, sessionId } = useAuth();
  const [barrier, setBarrier] = useState(savedBarrier);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const closing = !!barrier && (!sessionId || barrier === "unknown" || barrier === sessionId);
  useEffect(() => {
    const restoreBarrier = () => setBarrier(savedBarrier());
    window.addEventListener("pageshow", restoreBarrier);
    return () => window.removeEventListener("pageshow", restoreBarrier);
  }, []);
  useEffect(() => {
    // A completed promise is not proof that React has observed a signed-out session.
    // Only a provider-confirmed sign-out or a genuinely different session clears denial.
    if (
      isLoaded &&
      (!isSignedIn || (sessionId && barrier && barrier !== "unknown" && sessionId !== barrier))
    ) {
      storeBarrier(null);
      setBarrier(null);
      setPending(false);
      setFailed(false);
    }
  }, [isLoaded, isSignedIn, sessionId, barrier]);
  function blockSession(pending: boolean) {
    const session = sessionId ?? "unknown";
    storeBarrier(session);
    setBarrier(session);
    setPending(pending);
    setFailed(false);
  }
  return (
    <Closing.Provider
      value={{
        closing,
        pending,
        failed,
        begin: () => blockSession(true),
        invalidate: () => blockSession(false),
        setPending,
        setFailed,
      }}
    >
      {children}
    </Closing.Provider>
  );
}
export function useEndSession() {
  const { begin, pending, failed, setPending, setFailed } = useContext(Closing);
  const { signOut } = useClerk();
  const { userId } = useAuth();
  const cache = useQueryClient();
  const navigate = useNavigate();
  async function endSession(redirectUrl: string) {
    if (pending) return;
    clearAuthTarget();
    begin();
    try {
      const filter = {
        predicate: (query: { queryKey: readonly unknown[] }) =>
          !!userId && query.queryKey.includes(userId),
      };
      await cache.cancelQueries(filter);
      cache.removeQueries(filter);
      await signOut({ redirectUrl });
      navigate(redirectUrl, { replace: true });
    } catch {
      setFailed(true);
    } finally {
      // Keep the local access barrier until Clerk actually confirms the transition.
      setPending(false);
    }
  }
  return { endSession, pending, failed };
}
