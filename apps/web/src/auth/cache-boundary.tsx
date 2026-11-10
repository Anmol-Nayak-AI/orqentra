import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/react";
import { useEffect, useState, type ReactNode } from "react";

type Identity = { userId: string; sessionId: string | null } | null;

export function SessionCacheBoundary({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, userId, sessionId } = useAuth();
  const current: Identity =
    isLoaded && isSignedIn && userId ? { userId, sessionId: sessionId ?? null } : null;
  const [installed, setInstalled] = useState<Identity>(current);
  const cache = useQueryClient();
  const user = current?.userId ?? null;
  const session = current?.sessionId ?? null;
  const previousUser = installed?.userId ?? null;
  const previousSession = installed?.sessionId ?? null;
  const changed = user !== previousUser || session !== previousSession;

  useEffect(() => {
    if (!isLoaded || !changed) return;
    if (previousUser) {
      const filter = {
        predicate: (query: { queryKey: readonly unknown[] }) =>
          query.queryKey.includes(previousUser),
      };
      void cache.cancelQueries(filter);
      cache.removeQueries(filter);
    }
    setInstalled(user ? { userId: user, sessionId: session } : null);
  }, [cache, isLoaded, changed, previousUser, user, session]);

  // Prevent the next session from painting the previous session's cached results.
  if (isLoaded && current && installed && changed) {
    return (
      <p role="status" className="p-8">
        Updating your session…
      </p>
    );
  }
  return children;
}
