import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { SessionCacheBoundary } from "./cache-boundary";
const identity = vi.hoisted(() => ({
  isLoaded: true,
  isSignedIn: true,
  userId: "user_a" as string | null,
  sessionId: "sess_a" as string | null,
}));
vi.mock("@clerk/react", () => ({ useAuth: () => identity }));
beforeEach(() => {
  identity.isLoaded = true;
  identity.isSignedIn = true;
  identity.userId = "user_a";
  identity.sessionId = "sess_a";
});
function fixture() {
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity, retry: false } },
  });
  client.setQueryData(["organizations", "user_a"], [{ name: "Private A" }]);
  client.setQueryData(["system", "health"], { status: "ok" });
  const tree = () => (
    <QueryClientProvider client={client}>
      <SessionCacheBoundary>
        <p>Child view</p>
      </SessionCacheBoundary>
    </QueryClientProvider>
  );
  const view = render(tree());
  return { client, update: () => view.rerender(tree()) };
}
it("clears private results when the provider reports session invalidation", () => {
  const { client, update } = fixture();
  identity.isSignedIn = false;
  identity.userId = null;
  identity.sessionId = null;
  update();
  expect(client.getQueryData(["organizations", "user_a"])).toBeUndefined();
  expect(client.getQueryData(["system", "health"])).toEqual({ status: "ok" });
});
it("clears the old session cache on reauthentication with the same user", () => {
  const { client, update } = fixture();
  identity.sessionId = "sess_reauthenticated";
  update();
  expect(client.getQueryData(["organizations", "user_a"])).toBeUndefined();
  expect(client.getQueryData(["system", "health"])).toEqual({ status: "ok" });
});
it("does not treat temporary provider loading as a confirmed identity transition", () => {
  const { client, update } = fixture();
  identity.isLoaded = false;
  identity.userId = null;
  identity.sessionId = null;
  update();
  expect(client.getQueryData(["organizations", "user_a"])).toEqual([{ name: "Private A" }]);
  identity.isLoaded = true;
  identity.isSignedIn = false;
  update();
  expect(client.getQueryData(["organizations", "user_a"])).toBeUndefined();
});
