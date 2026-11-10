import { authReturnTarget, rememberAuthTarget, clearAuthTarget } from "./return-target";
import { OrganizationAdministration } from "./administration";
import { DemoRoster } from "./demo-roster";
import { InvitationManager } from "./invitations";
import type {
  OrganizationResponse,
  MembershipResponse,
  WorkspaceResponse,
} from "@orqentra/contracts";
import {
  AuthenticateWithRedirectCallback,
  SignIn,
  SignUp,
  UserButton,
  useAuth,
} from "@clerk/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useContext, useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";
import { Button } from "../components/ui/button";
import { ArrowRight, Layers3 } from "lucide-react";
import { ApiError } from "../lib/api";
import { useEndSession, useSessionClosing } from "./session-actions";
import { useSessionApi } from "./client";
import {
  OrganizationDirectoryView,
  OrganizationWorkspaceView,
  WorkspaceFrame,
} from "./workspace-views";
import { AuthenticationTheme } from "./layout";
import { useAuthConfigured } from "./provider";

type Organization = OrganizationResponse;
type Membership = MembershipResponse;
type Workspace = WorkspaceResponse;
const panel = "rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6";
const field =
  "mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2";

export function AuthConfigurationMissing() {
  return (
    <section className={panel}>
      <h1 className="text-2xl font-semibold">Sign-in is not configured</h1>
      <p className="mt-4 text-[var(--muted)]">
        An administrator needs to configure this deployment’s Clerk application before accounts can
        sign in. Access remains restricted.
      </p>
      <Link className="mt-6 inline-block underline" to="/">
        Return home
      </Link>
    </section>
  );
}

function SignedInGuard({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  const closing = useSessionClosing();
  const location = useLocation();
  useEffect(() => {
    if (isLoaded && !isSignedIn && !closing)
      rememberAuthTarget(location.pathname + location.search + location.hash);
    if (isLoaded && isSignedIn && !closing) clearAuthTarget();
  }, [isLoaded, isSignedIn, closing, location.pathname, location.search, location.hash]);
  if (closing) return <SessionExit />;
  if (!isLoaded) return <p role="status">Loading your session…</p>;
  if (!isSignedIn) return <Navigate to="/sign-in" replace />;
  return children;
}

export function Protected({ children }: { children: ReactNode }) {
  return useAuthConfigured() ? (
    <SignedInGuard>{children}</SignedInGuard>
  ) : (
    <AuthConfigurationMissing />
  );
}

export function AuthenticationPage({ mode }: { mode: "sign-in" | "sign-up" | "callback" }) {
  if (!useAuthConfigured()) return <AuthConfigurationMissing />;
  return <ConfiguredAuthenticationPage mode={mode} />;
}

function ConfiguredAuthenticationPage({ mode }: { mode: "sign-in" | "sign-up" | "callback" }) {
  const { isLoaded, isSignedIn } = useAuth();
  const closing = useSessionClosing();
  const dark = useContext(AuthenticationTheme);
  const destination = authReturnTarget();
  const appearance = {
    variables: {
      colorPrimary: dark ? "#a2e3cc" : "#22694f",
      colorPrimaryForeground: dark ? "#102c23" : "#ffffff",
      colorBackground: dark ? "#171d20" : "#ffffff",
      colorForeground: dark ? "#f0f4f2" : "#16251f",
      colorMutedForeground: dark ? "#a7b3b5" : "#52645b",
      colorNeutral: dark ? "#ffffff" : "#16251f",
      colorInput: dark ? "#101719" : "#f7f9f8",
      colorInputForeground: dark ? "#f0f4f2" : "#16251f",
      colorBorder: dark ? "#354044" : "#d6dfda",
      borderRadius: "0.65rem",
      fontFamily: "Inter, Segoe UI, system-ui, sans-serif",
      fontSize: "0.875rem",
    },
    elements: {
      rootBox: "auth-clerk-root",
      cardBox: "auth-clerk-box",
      card: "auth-clerk-card",
      headerTitle: "auth-clerk-title",
      headerSubtitle: "auth-clerk-subtitle",
      formButtonPrimary: "auth-clerk-primary",
      socialButtonsBlockButton: "auth-clerk-social",
      formFieldInput: "auth-clerk-input",
      footer: "auth-clerk-footer",
    },
  };
  if (closing) return <SessionExit />;
  if (!isLoaded)
    return (
      <p role="status" className="p-8">
        Loading your session…
      </p>
    );
  if (isSignedIn && mode !== "callback") return <Navigate to={destination} replace />;
  return (
    <div className="auth-widget">
      {mode === "sign-in" ? (
        <SignIn
          appearance={appearance}
          routing="path"
          path="/sign-in"
          signUpUrl="/sign-up"
          forceRedirectUrl={destination}
        />
      ) : mode === "sign-up" ? (
        <SignUp
          appearance={appearance}
          routing="path"
          path="/sign-up"
          signInUrl="/sign-in"
          forceRedirectUrl={destination}
        />
      ) : (
        <AuthenticateWithRedirectCallback
          signInForceRedirectUrl={destination}
          signUpForceRedirectUrl={destination}
        />
      )}
    </div>
  );
}

function SessionNavigation({ compact = false }: { compact?: boolean }) {
  const { isLoaded, isSignedIn } = useAuth();
  const { endSession, pending, failed } = useEndSession();
  const closing = useSessionClosing();
  if (closing) return <span className="text-sm text-[var(--muted)]">Session locked</span>;
  if (!isLoaded) return <span role="status">Loading…</span>;
  return isSignedIn ? (
    <div className="flex items-center gap-3">
      {!compact && (
        <Link to="/app" className="hidden text-sm sm:block">
          Organizations
        </Link>
      )}
      <UserButton />
      <Button variant="outline" disabled={pending} onClick={() => void endSession("/")}>
        {pending ? "Signing out…" : "Sign out"}
      </Button>
      {failed && (
        <span role="alert" className="max-w-48 text-xs">
          Sign-out failed. Please try again.
        </span>
      )}
    </div>
  ) : (
    <Button asChild>
      <Link to="/sign-in">Sign in</Link>
    </Button>
  );
}

export function AccountNavigation({ compact = false }: { compact?: boolean }) {
  return useAuthConfigured() ? (
    <SessionNavigation compact={compact} />
  ) : (
    <Link to="/sign-in" className="text-sm underline">
      Sign in
    </Link>
  );
}

export function AccessDenied() {
  return (
    <section className={panel}>
      <h1 className="text-2xl font-semibold">Access denied</h1>
      <p className="mt-4 text-[var(--muted)]">
        Your account does not have access to this organization or action.
      </p>
      <Link className="mt-6 inline-block underline" to="/app">
        Choose an organization
      </Link>
    </section>
  );
}

export function SessionExpired() {
  return (
    <section className={panel}>
      <h1 className="text-2xl font-semibold">Session expired</h1>
      <p className="mt-4 text-[var(--muted)]">Sign in again to continue securely.</p>
      {useAuthConfigured() ? (
        <RestartSession />
      ) : (
        <Button asChild className="mt-6">
          <Link to="/sign-in">Sign in</Link>
        </Button>
      )}
    </section>
  );
}

function SessionExit() {
  const { endSession, pending, failed } = useEndSession();
  return (
    <section className={`${panel} mx-auto my-10 max-w-xl`}>
      <h1 className="text-2xl font-semibold">
        {pending ? "Signing out securely…" : "Workspace locked"}
      </h1>
      <p role="status" className="mt-3 text-[var(--muted)]">
        {pending
          ? "Signing out securely…"
          : "Sign-out has not yet been confirmed. Your workspace stays locked until the session ends."}
      </p>
      {failed && (
        <p role="alert" className="mt-3">
          Sign-out failed. Your workspace remains locked. Please try again.
        </p>
      )}
      <Button className="mt-6" disabled={pending} onClick={() => void endSession("/sign-in")}>
        {pending ? "Signing out…" : "Try sign out again"}
      </Button>
    </section>
  );
}

function RestartSession() {
  const { endSession, pending, failed } = useEndSession();
  return (
    <>
      <Button className="mt-6" disabled={pending} onClick={() => void endSession("/sign-in")}>
        {pending ? "Ending expired session…" : "Sign in again"}
      </Button>
      {failed && (
        <p role="alert" className="mt-3">
          Could not end the session. Please try again.
        </p>
      )}
    </>
  );
}

function Failure({ error, retry }: { error: unknown; retry?: () => void }) {
  if (error instanceof ApiError && error.status === 403) return <AccessDenied />;
  return (
    <div role="alert" className={panel}>
      <h2 className="text-lg font-semibold">Unable to load this page</h2>
      <p className="mt-2 text-sm text-[var(--muted)]">
        Check your connection and try again. Your saved data has not been changed.
      </p>
      {retry && (
        <Button variant="outline" className="mt-4" onClick={retry}>
          Try again
        </Button>
      )}
      {error instanceof ApiError && error.correlationId && (
        <p className="mt-2 text-xs">Request ID: {error.correlationId}</p>
      )}
    </div>
  );
}

export function OrganizationSelection() {
  const { api, userId } = useSessionApi();
  const query = useQuery({
    queryKey: ["organizations", userId],
    queryFn: ({ signal }) => api<Organization[]>("/organizations", { signal }),
    staleTime: 0,
  });
  if (query.isPending) return <p role="status">Loading organizations…</p>;
  if (query.isError) return <Failure error={query.error} retry={() => void query.refetch()} />;
  return <OrganizationDirectoryView organizations={query.data} />;
}

export function CreateOrganization() {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [validation, setValidation] = useState("");
  const create = useMutation({
    mutationFn: (body: { name: string; slug: string }) =>
      api<Organization>("/organizations", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (org) => {
      void cache.invalidateQueries({ queryKey: ["organizations", userId] });
      navigate(`/app/organizations/${org.id}`);
    },
  });
  return (
    <section className={`${panel} workspace-create mx-auto max-w-2xl`}>
      <Link to="/app" className="mb-6 inline-block text-sm text-[var(--muted)]">
        ← All organizations
      </Link>
      <h1 className="text-2xl font-semibold">Create organization</h1>
      <p className="mt-3 text-[var(--muted)]">
        You’ll become the owner, with one default workspace.
      </p>
      <form
        aria-busy={create.isPending}
        className="mt-8 space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          if (create.isPending) return;
          const result = z
            .object({
              name: z.string().trim().min(1).max(200),
              slug: z
                .string()
                .min(1)
                .max(100)
                .regex(/^[a-z0-9]+(-[a-z0-9]+)*$/),
            })
            .safeParse({ name, slug });
          if (!result.success) {
            setValidation("Enter a name and a lowercase slug with hyphens.");
            return;
          }
          setValidation("");
          create.mutate(result.data);
        }}
      >
        <label className="block" htmlFor="org-name">
          Organization name
          <input
            id="org-name"
            required
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={field}
            disabled={create.isPending}
          />
        </label>
        <label className="block" htmlFor="org-slug">
          Organization slug
          <input
            id="org-slug"
            required
            maxLength={100}
            pattern="[a-z0-9]+(-[a-z0-9]+)*"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className={field}
            disabled={create.isPending}
          />
          <span className="mt-2 block text-xs text-[var(--muted)]">For example, acme-team</span>
        </label>
        {validation && <p role="alert">{validation}</p>}
        {create.isError && (
          <p role="alert">
            {create.error instanceof ApiError && create.error.status === 409
              ? "That slug is already in use."
              : "Organization creation failed. Please try again."}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create organization"}
          </Button>
          <Button asChild variant="outline">
            <Link to="/app">Cancel</Link>
          </Button>
        </div>
      </form>
    </section>
  );
}

export function OrganizationHome({ settings = false }: { settings?: boolean }) {
  const { organizationId } = useParams();
  const { api, userId } = useSessionApi();
  const base = `/organizations/${organizationId}`;
  const organization = useQuery({
    queryKey: ["organization", userId, organizationId],
    queryFn: ({ signal }) => api<Organization>(base, { signal }),
    staleTime: 0,
  });
  const workspaces = useQuery({
    queryKey: ["workspaces", userId, organizationId],
    queryFn: ({ signal }) => api<Workspace[]>(`${base}/workspaces`, { signal }),
    enabled: organization.isSuccess,
    staleTime: 0,
  });
  if (organization.isPending) return <p role="status">Loading organization…</p>;
  if (organization.isError)
    return <Failure error={organization.error} retry={() => void organization.refetch()} />;
  if (settings && organizationId && ["OWNER", "ADMIN"].includes(organization.data.role))
    return <OrganizationAdministration key={organizationId} organizationId={organizationId} />;
  return (
    <OrganizationWorkspaceView
      organization={organization.data}
      workspaces={workspaces.data}
      loading={workspaces.isPending}
      settings={settings}
      workspaceError={
        workspaces.isError ? (
          <Failure error={workspaces.error} retry={() => void workspaces.refetch()} />
        ) : undefined
      }
    />
  );
}

export function MembershipManagement() {
  const { organizationId } = useParams();
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const base = `/organizations/${organizationId}`;
  const [failure, setFailure] = useState("");
  const [removeTarget, setRemoveTarget] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["members", userId, organizationId],
    queryFn: ({ signal }) => api<Membership[]>(`${base}/memberships`, { signal }),
    staleTime: 0,
  });
  const own = useQuery({
    queryKey: ["membership", userId, organizationId],
    queryFn: ({ signal }) => api<Membership>(`${base}/memberships/me`, { signal }),
    staleTime: 0,
  });
  const mutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string | null }) =>
      api(`${base}/memberships/${id}`, {
        method: role ? "PATCH" : "DELETE",
        ...(role ? { body: JSON.stringify({ role }) } : {}),
      }),
    onSuccess: () => {
      void cache.invalidateQueries({
        queryKey: ["members", userId, organizationId],
      });
      void cache.invalidateQueries({
        queryKey: ["membership", userId, organizationId],
      });
      setFailure("");
      setRemoveTarget(null);
    },
    onError: (error) =>
      setFailure(
        error instanceof ApiError && error.status === 409
          ? "The final active owner cannot be removed or demoted."
          : "You are not allowed to change this membership, or access has changed.",
      ),
  });
  if (query.isPending || own.isPending) return <p role="status">Loading members…</p>;
  if (query.isError || own.isError) return <Failure error={query.error ?? own.error} />;
  const role = own.data.role;
  const manages = role === "OWNER" || role === "ADMIN";
  return (
    <section>
      <Link className="text-sm underline" to={`/app/organizations/${organizationId}`}>
        Back to Command Center
      </Link>
      <h1 className="mb-3 mt-6 text-3xl font-semibold">Members & access</h1>
      <p className="mb-6 text-sm text-[var(--muted)]">
        Manage organization access and share private invitations according to your role.
      </p>
      {manages && organizationId && (
        <InvitationManager key={organizationId} organizationId={organizationId} />
      )}
      {failure && (
        <p role="alert" className="mb-4">
          {failure}
        </p>
      )}
      {removeTarget && (
        <section aria-label="Confirm member removal" className={`${panel} mb-5`}>
          <h2 className="font-semibold">Remove this member?</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            They will lose access to this organization. Existing records will be preserved.
          </p>
          <div className="mt-4 flex gap-3">
            <Button
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ id: removeTarget, role: null })}
            >
              {mutation.isPending ? "Removing…" : "Confirm removal"}
            </Button>
            <Button
              variant="outline"
              disabled={mutation.isPending}
              onClick={() => setRemoveTarget(null)}
            >
              Cancel
            </Button>
          </div>
        </section>
      )}
      <h2 className="mb-4 text-xl font-semibold">Real members · {query.data.length}</h2>
      <p className="mb-4 text-sm text-[var(--muted)]">
        Only real accounts with active memberships can access this organization. Demo profiles below
        cannot sign in. Invite a real person using a private link.
      </p>
      <div className="space-y-4">
        {query.data.map((member) => {
          const editable =
            manages && (role === "OWNER" || !["OWNER", "ADMIN"].includes(member.role));
          return (
            <div
              key={member.id}
              className={`${panel} member-row flex flex-wrap items-center justify-between gap-4`}
            >
              <div>
                <p className="break-all text-sm">
                  {member.id === own.data.id ? "You" : `Member ${member.user_id.slice(0, 8)}`}
                  <span className="mt-1 block text-xs text-[var(--muted)]">{member.user_id}</span>
                </p>
                <p className="mt-2 text-xs text-[var(--muted)]">{member.status}</p>
              </div>
              <div className="flex gap-3">
                <label className="sr-only" htmlFor={`role-${member.id}`}>
                  Role for {member.user_id}
                </label>
                <select
                  id={`role-${member.id}`}
                  className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-2"
                  value={member.role}
                  disabled={!editable || mutation.isPending}
                  onChange={(e) => mutation.mutate({ id: member.id, role: e.target.value })}
                >
                  {(role === "OWNER"
                    ? ["OWNER", "ADMIN", "MEMBER", "VIEWER"]
                    : [...new Set([member.role, "MEMBER", "VIEWER"])]
                  ).map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
                {editable && (
                  <Button
                    variant="outline"
                    disabled={mutation.isPending}
                    onClick={() => {
                      setFailure("");
                      setRemoveTarget(member.id);
                    }}
                  >
                    Remove
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {organizationId && (
        <DemoRoster key={`demo-${organizationId}`} organizationId={organizationId} />
      )}
    </section>
  );
}

export function HomeEntry() {
  if (!useAuthConfigured()) return <Welcome />;
  return <SessionEntry />;
}
function SessionEntry() {
  const { isLoaded, isSignedIn } = useAuth();
  const closing = useSessionClosing();
  if (closing) return <SessionExit />;
  if (!isLoaded)
    return (
      <p role="status" className="p-8">
        Loading your session…
      </p>
    );
  return isSignedIn ? <Navigate to="/app" replace /> : <Welcome />;
}
function Welcome() {
  return (
    <section className="mx-auto grid min-h-[75vh] max-w-7xl items-center gap-12 px-6 py-16 lg:grid-cols-[1.2fr_1fr]">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--accent)]">
          Enterprise AI workforce
        </p>
        <h1 className="mt-6 max-w-2xl text-5xl font-semibold leading-tight tracking-tight sm:text-6xl">
          Your workforce,
          <br />
          <span className="text-[var(--accent)]">intelligently orchestrated.</span>
        </h1>
        <p className="mt-6 max-w-lg text-lg leading-8 text-[var(--muted)]">
          Bring your organization together. Set up your workspace, manage your team, and build the
          foundation for what comes next.
        </p>
        <div className="mt-8 flex gap-4">
          <Button asChild>
            <Link to="/sign-up">
              Get started
              <ArrowRight className="size-4" />
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/sign-in">Sign in</Link>
          </Button>
        </div>
      </div>
      <div className="rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-8">
        <div className="mb-8 flex items-center gap-3">
          <Layers3 className="size-6 text-[var(--accent)]" />
          <span className="font-semibold">Built around your organization</span>
        </div>
        {[
          "A dedicated home for your team",
          "Clear roles and member permissions",
          "Securely isolated organization data",
        ].map((label, index) => (
          <div key={label} className="flex items-center gap-4 border-t border-[var(--border)] py-5">
            <span className="w-5 shrink-0 whitespace-nowrap text-sm tabular-nums text-[var(--accent)]">
              0{index + 1}
            </span>
            <p className="text-sm">{label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ApplicationLayout() {
  const { api, userId } = useSessionApi();
  const organizations = useQuery({
    queryKey: ["organizations", userId],
    queryFn: ({ signal }) => api<OrganizationResponse[]>("/organizations", { signal }),
  });
  const { pathname } = useLocation();
  const [dark, setDark] = useState(() => {
    try {
      return localStorage.getItem("orqentra.workspace-theme") === "dark";
    } catch {
      return false;
    }
  });
  const match = pathname.match(/^\/app\/organizations\/([^/]+)/);
  const root = match ? `/app/organizations/${match[1]}` : null;
  const title = pathname.endsWith("/chat")
    ? "Workspace chat"
    : pathname.endsWith("/knowledge")
      ? "Knowledge library"
      : pathname.endsWith("/runs")
        ? "Tasks & reviews"
        : pathname.endsWith("/audit")
          ? "Audit trail"
          : pathname.endsWith("/teammates")
            ? "Teammate Forge"
            : pathname.endsWith("/members")
              ? "Members & access"
              : pathname.endsWith("/settings")
                ? "Organization settings"
                : pathname.endsWith("/create-organization")
                  ? "Create organization"
                  : root
                    ? "Command Center"
                    : "Organization directory";
  function toggle() {
    const next = !dark;
    setDark(next);
    try {
      localStorage.setItem("orqentra.workspace-theme", next ? "dark" : "light");
    } catch {}
  }
  return (
    <WorkspaceFrame
      title={title}
      organizations={organizations.data ?? []}
      root={root}
      dark={dark}
      toggle={toggle}
      account={<AccountNavigation compact />}
    >
      <Outlet />
    </WorkspaceFrame>
  );
}
