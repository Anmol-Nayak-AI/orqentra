import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, Link } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  HomeEntry,
  AuthenticationPage,
  SessionExpired,
  CreateOrganization,
  MembershipManagement,
  Protected,
  AccountNavigation,
  OrganizationSelection,
} from "./pages";

import { useSessionApi } from "./client";
import { SessionActions } from "./session-actions";

const state = vi.hoisted(() => ({
  configured: true,
  loaded: true,
  signedIn: true,
  sessionId: "sess_fixture",
  getToken: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock("@clerk/react", () => ({
  useAuth: () => ({
    isLoaded: state.loaded,
    isSignedIn: state.signedIn,
    sessionId: state.sessionId,
    userId: "user_fixture",
    getToken: state.getToken,
  }),
  useClerk: () => ({ signOut: state.signOut }),
  UserButton: () => null,
  SignIn: () => null,
  SignUp: () => null,
  AuthenticateWithRedirectCallback: () => null,
}));
vi.mock("./provider", () => ({ useAuthConfigured: () => state.configured }));

function setup(element: React.ReactNode, path = "/app") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SessionActions>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/app" element={element} />
            <Route path="/app/organizations/:organizationId/members" element={element} />
            <Route path="/" element={<p>Public home</p>} />
            <Route path="/sign-in" element={<p>Sign-in route</p>} />
            <Route path="/session-expired" element={<p>Expired route</p>} />
          </Routes>
        </MemoryRouter>
      </SessionActions>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  state.sessionId = "sess_fixture";
  state.configured = true;
  state.loaded = true;
  state.signedIn = true;
  state.signOut.mockReset().mockResolvedValue(undefined);
  state.getToken.mockReset().mockResolvedValue("unit-test-token");
});
afterEach(() => vi.unstubAllGlobals());

it("does not render protected content while loading", () => {
  state.loaded = false;
  setup(
    <Protected>
      <p>Private data</p>
    </Protected>,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Loading your session");
  expect(screen.queryByText("Private data")).not.toBeInTheDocument();
});
it("redirects a signed-out session", () => {
  state.signedIn = false;
  setup(
    <Protected>
      <p>Private data</p>
    </Protected>,
  );
  expect(screen.getByText("Sign-in route")).toBeInTheDocument();
});
it("fails closed when provider configuration is absent", () => {
  state.configured = false;
  setup(
    <Protected>
      <p>Private data</p>
    </Protected>,
  );
  expect(screen.getByRole("heading", { name: "Sign-in is not configured" })).toBeInTheDocument();
  expect(screen.queryByText("Private data")).not.toBeInTheDocument();
});
it("validates organization fields before a request", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  setup(<CreateOrganization />);
  await userEvent.type(screen.getByLabelText("Organization name"), "Acme");
  await userEvent.type(screen.getByLabelText(/Organization slug/), "INVALID SLUG");
  fireEvent.submit(screen.getByRole("button", { name: "Create organization" }).closest("form")!);
  expect(screen.getByRole("alert")).toHaveTextContent("lowercase slug");
  expect(fetch).not.toHaveBeenCalled();
});
it("uses Clerk token per request and handles slug conflicts without losing inputs", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 409 }));
  vi.stubGlobal("fetch", fetch);
  setup(<CreateOrganization />);
  await userEvent.type(screen.getByLabelText("Organization name"), "Acme");
  await userEvent.type(screen.getByLabelText(/Organization slug/), "acme");
  await userEvent.click(screen.getByRole("button", { name: "Create organization" }));
  expect(await screen.findByText("That slug is already in use.")).toBeInTheDocument();
  expect(state.getToken).toHaveBeenCalled();
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe("Bearer unit-test-token");
  expect(fetch.mock.calls[0][1].credentials).toBe("omit");
  expect(screen.getByLabelText("Organization name")).toHaveValue("Acme");
});
it("shows session expired and sends no request when token retrieval fails closed", async () => {
  state.getToken.mockResolvedValue(null);
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  setup(<CreateOrganization />);
  await userEvent.type(screen.getByLabelText("Organization name"), "Acme");
  await userEvent.type(screen.getByLabelText(/Organization slug/), "acme");
  await userEvent.click(screen.getByRole("button", { name: "Create organization" }));
  expect(await screen.findByText("Expired route")).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});
it("renders denied state for forbidden memberships", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async () => new Response("{}", { status: 403 })),
  );
  setup(<MembershipManagement />, "/app/organizations/foreign/members");
  expect(await screen.findByRole("heading", { name: "Access denied" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
});

it("redirects signed-in entry and sign-in routes to the application", () => {
  for (const entry of [
    <HomeEntry key="home" />,
    <AuthenticationPage key="sign-in" mode="sign-in" />,
  ]) {
    const view = render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={entry} />
          <Route path="/app" element={<p>Authenticated application destination</p>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Authenticated application destination")).toBeInTheDocument();
    view.unmount();
  }
});

it("ends the expired provider session before retrying authentication", async () => {
  state.signOut.mockResolvedValue(undefined);
  setup(<SessionExpired />);
  await userEvent.click(screen.getByRole("button", { name: "Sign in again" }));
  expect(state.signOut).toHaveBeenCalledWith({ redirectUrl: "/sign-in" });
});

it("hides protected content while sign-out is pending", async () => {
  let finish: () => void = () => {};
  state.signOut.mockImplementation(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );
  setup(
    <Protected>
      <AccountNavigation />
      <p>Private organization content</p>
    </Protected>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(screen.queryByText("Private organization content")).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Signing out securely");
  finish();
  expect(await screen.findByText("Public home")).toBeInTheDocument();
});
it("shows a recoverable failure when provider sign-out fails", async () => {
  state.signOut.mockRejectedValue(new Error("provider unavailable"));
  setup(
    <Protected>
      <AccountNavigation />
      <p>Private organization content</p>
    </Protected>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Sign-out failed");
  expect(screen.getByRole("button", { name: "Try sign out again" })).toBeEnabled();
});
it("routes thrown token-retrieval errors to recovery without an API request", async () => {
  state.getToken.mockRejectedValue(new Error("session unavailable"));
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  setup(<OrganizationSelection />);
  expect(await screen.findByText("Expired route")).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});
it("retries a failed organization read without reloading or losing the session", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 503 }))
      .mockImplementation(async () => new Response("[]")),
  );
  setup(<OrganizationSelection />);
  await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("heading", { name: "Your organizations" })).toBeInTheDocument();
});
it("requires confirmation before removing a member", async () => {
  const member = {
    id: "membership-fixture",
    user_id: "user_fixture",
    organization_id: "org-fixture",
    role: "OWNER",
    status: "ACTIVE",
  };
  const fetch = vi
    .fn()
    .mockImplementation(
      async (path: string) =>
        new Response(
          JSON.stringify(
            path.endsWith("/me") ? member : path.endsWith("/memberships") ? [member] : [],
          ),
        ),
    );
  vi.stubGlobal("fetch", fetch);
  setup(<MembershipManagement />, "/app/organizations/org-fixture/members");
  await userEvent.click(await screen.findByRole("button", { name: "Remove" }));
  expect(screen.getByRole("region", { name: "Confirm member removal" })).toBeInTheDocument();
  expect(fetch.mock.calls.every((call) => !call[1]?.method)).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("region", { name: "Confirm member removal" })).not.toBeInTheDocument();
});

it("clears only the departing user's private cache during sign-out", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  client.setQueryData(["organizations", "user_fixture"], [{ name: "Private" }]);
  client.setQueryData(["system", "health"], { status: "ok" });
  render(
    <QueryClientProvider client={client}>
      <SessionActions>
        <MemoryRouter>
          <Routes>
            <Route path="/" element={<AccountNavigation />} />
          </Routes>
        </MemoryRouter>
      </SessionActions>
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(client.getQueryData(["organizations", "user_fixture"])).toBeUndefined();
  expect(client.getQueryData(["system", "health"])).toEqual({ status: "ok" });
});

it("does not reopen protected content when signOut resolves before SDK auth state changes", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(
    <QueryClientProvider client={client}>
      <SessionActions>
        <MemoryRouter initialEntries={["/app"]}>
          <Routes>
            <Route path="/" element={<HomeEntry />} />
            <Route
              path="/app"
              element={
                <Protected>
                  <AccountNavigation />
                  <p>Private organization content</p>
                </Protected>
              }
            />
          </Routes>
        </MemoryRouter>
      </SessionActions>
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Workspace locked" })).toBeInTheDocument();
  expect(screen.queryByText("Private organization content")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: /Your workforce,/ })).not.toBeInTheDocument();
});
it("keeps the same session locked after remounting and permits a genuinely new session", async () => {
  const first = setup(
    <Protected>
      <AccountNavigation />
      <p>Private organization content</p>
    </Protected>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await screen.findByText("Public home");
  first.unmount();
  const second = setup(
    <Protected>
      <p>Private organization content</p>
    </Protected>,
  );
  expect(screen.getByRole("heading", { name: "Workspace locked" })).toBeInTheDocument();
  expect(screen.queryByText("Private organization content")).not.toBeInTheDocument();
  second.unmount();
  state.sessionId = "sess_new_authentication";
  setup(
    <Protected>
      <p>Private organization content</p>
    </Protected>,
  );
  expect(await screen.findByText("Private organization content")).toBeInTheDocument();
});
it("clears the logout barrier only after the SDK confirms signed out", async () => {
  const first = setup(
    <Protected>
      <AccountNavigation />
      <p>Private organization content</p>
    </Protected>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await screen.findByText("Public home");
  first.unmount();
  state.signedIn = false;
  setup(
    <Protected>
      <p>Private organization content</p>
    </Protected>,
  );
  expect(await screen.findByText("Sign-in route")).toBeInTheDocument();
  expect(sessionStorage.getItem("orqentra.logout-barrier")).toBeNull();
});

function ExpirationProbe() {
  const { api } = useSessionApi();
  return (
    <>
      <p>Private organization content</p>
      <button type="button" onClick={() => void api("/me").catch(() => {})}>
        Check protected access
      </button>
    </>
  );
}
it.each(["api-401", "missing-token", "token-error"])(
  "clears stale private cache and blocks return on %s",
  async (failure) => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    });
    client.setQueryData(["organizations", "user_fixture"], [{ name: "Private organization" }]);
    client.setQueryData(["system", "health"], { status: "ok" });
    if (failure === "missing-token") state.getToken.mockResolvedValue(null);
    if (failure === "token-error") state.getToken.mockRejectedValue(new Error("session ended"));
    const fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetch);
    render(
      <QueryClientProvider client={client}>
        <SessionActions>
          <MemoryRouter initialEntries={["/app"]}>
            <Routes>
              <Route
                path="/app"
                element={
                  <Protected>
                    <ExpirationProbe />
                  </Protected>
                }
              />
              <Route
                path="/session-expired"
                element={
                  <>
                    <SessionExpired />
                    <Link to="/app">Attempt return</Link>
                  </>
                }
              />
              <Route path="/sign-in" element={<p>Sign-in route</p>} />
            </Routes>
          </MemoryRouter>
        </SessionActions>
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Check protected access" }));
    expect(await screen.findByRole("heading", { name: "Session expired" })).toBeInTheDocument();
    expect(client.getQueryData(["organizations", "user_fixture"])).toBeUndefined();
    expect(client.getQueryData(["system", "health"])).toEqual({ status: "ok" });
    expect(screen.queryByText("Private organization content")).not.toBeInTheDocument();
    if (failure !== "api-401") expect(fetch).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("link", { name: "Attempt return" }));
    expect(screen.getByRole("heading", { name: "Workspace locked" })).toBeInTheDocument();
    expect(screen.queryByText("Private organization content")).not.toBeInTheDocument();
  },
);

it("refreshes a rejected cached token once before ending the session", async () => {
  state.getToken
    .mockResolvedValueOnce("synthetic-stale-token")
    .mockResolvedValue("synthetic-fresh-token");
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(new Response("{}", { status: 401 }))
    .mockImplementation(async () => new Response("[]"));
  vi.stubGlobal("fetch", fetch);
  setup(<OrganizationSelection />);
  expect(await screen.findByRole("heading", { name: "Your organizations" })).toBeInTheDocument();
  expect(state.getToken).toHaveBeenCalledWith({ skipCache: true });
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[1][1].headers.Authorization).toBe("Bearer synthetic-fresh-token");
  expect(screen.queryByText("Expired route")).not.toBeInTheDocument();
});

it("keeps the protected destination when redirecting a signed-out member", async () => {
  state.signedIn = false;
  setup(
    <Protected>
      <p>Private member controls</p>
    </Protected>,
    "/app/organizations/org-fixture/members",
  );
  expect(await screen.findByText("Sign-in route")).toBeVisible();
  expect(sessionStorage.getItem("orqentra.auth-return")).toBe(
    "/app/organizations/org-fixture/members",
  );
  expect(screen.queryByText("Private member controls")).not.toBeInTheDocument();
});
