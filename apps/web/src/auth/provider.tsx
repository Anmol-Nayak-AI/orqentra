import { ClerkProvider } from "@clerk/react";
import { createContext, useContext, type ReactNode } from "react";

import { SessionCacheBoundary } from "./cache-boundary";
import { SessionActions } from "./session-actions";

const Configured = createContext(false);
export const useAuthConfigured = () => useContext(Configured);

export function AuthenticationProvider({ children }: { children: ReactNode }) {
  const key = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;
  if (!key) return children;
  return (
    <Configured.Provider value={true}>
      <ClerkProvider
        publishableKey={key}
        signInUrl="/sign-in"
        signUpUrl="/sign-up"
        afterSignOutUrl="/"
      >
        <SessionActions>
          <SessionCacheBoundary>{children}</SessionCacheBoundary>
        </SessionActions>
      </ClerkProvider>
    </Configured.Provider>
  );
}
