import { ChatPage } from "./chat/page";
import { AcceptInvitation } from "./auth/invitations";
import { WorkbenchPage } from "./execution/page";
import { TeammatesPage } from "./agents/page";
import {
  AccountNavigation,
  Protected,
  AuthenticationPage,
  OrganizationSelection,
  CreateOrganization,
  OrganizationHome,
  MembershipManagement,
  AccessDenied,
  SessionExpired,
  HomeEntry,
  ApplicationLayout,
} from "./auth/pages";
import { AuthenticationLayout } from "./auth/layout";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, Route, Routes, Outlet } from "react-router-dom";
import { ArrowRight, Check, Layers3, RefreshCw } from "lucide-react";
import { Brand, ThemeToggle } from "./components/chrome";
import { Button } from "./components/ui/button";
import { ApiError, getHealth } from "./lib/api";

function Foundation() {
  const health = useQuery({
    queryKey: ["system", "health"],
    queryFn: ({ signal }) => getHealth(signal),
    retry: false,
  });
  return (
    <section className="mx-auto max-w-5xl px-6 py-14 sm:py-20">
      <div className="mb-8 flex items-center gap-3 text-xs font-medium uppercase tracking-[0.18em] text-[var(--muted)]">
        <span className="h-px w-8 bg-[var(--accent)]" /> Enterprise AI workforce
      </div>
      <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
        A strong foundation.
        <br />
        <span className="text-[var(--muted)]">For the work ahead.</span>
      </h1>
      <p className="mt-6 max-w-xl text-base leading-7 text-[var(--muted)]">
        The platform starts here. A connected workspace for building, configuring, and governing
        your AI teammates.
      </p>
      <section
        aria-labelledby="foundation-title"
        className="mt-12 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]"
      >
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] px-6 py-5">
          <div className="flex items-center gap-3">
            <Layers3 className="size-5 text-[var(--accent)]" />
            <h2 id="foundation-title" className="font-medium">
              Platform foundation
            </h2>
          </div>
          <span className="rounded-full border border-[var(--border)] px-3 py-1 text-xs text-[var(--muted)]">
            System status
          </span>
        </div>
        <div className="grid sm:grid-cols-[1fr_1.2fr]">
          <div className="p-6 sm:border-r sm:border-[var(--border)]">
            <p className="text-xs uppercase tracking-widest text-[var(--muted)]">API connection</p>
            <div
              role="status"
              aria-live="polite"
              className="mt-5 flex items-center gap-3 text-lg font-medium"
            >
              <span
                className={`size-2 rounded-full ${health.isSuccess ? "bg-[var(--accent)]" : health.isError ? "bg-amber-400" : "bg-[var(--muted)] animate-pulse"}`}
              />
              {health.isPending
                ? "Checking connection…"
                : health.isError
                  ? "API unavailable"
                  : "API connected"}
            </div>
            <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
              {health.isError
                ? "Check that the Python API is running, then try again."
                : "This checks the API process. Database and identity readiness are checked separately."}
            </p>
            {health.error instanceof ApiError && health.error.correlationId && (
              <p className="mt-3 break-all text-xs text-[var(--muted)]">
                Request ID: {health.error.correlationId}
              </p>
            )}
            <Button
              variant="outline"
              className="mt-6"
              disabled={health.isFetching}
              onClick={() => void health.refetch()}
            >
              <RefreshCw className={`size-4 ${health.isFetching ? "animate-spin" : ""}`} />
              Check again
            </Button>
          </div>
          <div className="p-6">
            <p className="text-xs uppercase tracking-widest text-[var(--muted)]">
              What’s available
            </p>
            <ul className="mt-5 space-y-4 text-sm">
              <li className="flex items-center gap-3">
                <Check className="size-4 text-[var(--accent)]" />
                Web and API foundation
              </li>
              <li className="flex items-center gap-3">
                <Check className="size-4 text-[var(--accent)]" />
                Live process health check
              </li>
            </ul>
            <div className="mt-7 rounded-xl border border-[var(--border)] p-4 text-sm leading-6 text-[var(--muted)]">
              <span className="mb-1 flex items-center gap-2 font-medium text-[var(--text)]">
                Your workspace <ArrowRight className="size-4" />
              </span>
              Secure sign-in and organization management are available. Open your workspace to get
              started.
            </div>
          </div>
        </div>
      </section>
      <p className="mt-6 text-xs leading-6 text-[var(--muted)]">
        Development environment · External delivery is simulated.
      </p>
    </section>
  );
}

export function App() {
  const [dark, setDark] = useState(true);
  return (
    <div
      data-theme={dark ? "dark" : "light"}
      className="min-h-screen bg-[var(--background)] text-[var(--text)] transition-colors"
    >
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-10 focus:bg-[var(--surface)] focus:p-3"
      >
        Skip to content
      </a>
      <Routes>
        <Route element={<PublicLayout dark={dark} toggle={() => setDark(!dark)} />}>
          <Route path="/" element={<HomeEntry />} />
          <Route path="/status" element={<Foundation />} />
          <Route path="/access-denied" element={<AccessDenied />} />
          <Route path="/session-expired" element={<SessionExpired />} />
          <Route
            path="*"
            element={
              <section className="mx-auto max-w-xl px-6 py-20">
                <h1 className="text-3xl font-semibold">Page not found</h1>
                <p className="mt-3 text-[var(--muted)]">This page is not available.</p>
                <Button asChild className="mt-6">
                  <Link to="/">Return home</Link>
                </Button>
              </section>
            }
          />
        </Route>
        <Route element={<AuthenticationLayout dark={dark} toggle={() => setDark(!dark)} />}>
          <Route path="/sign-in/*" element={<AuthenticationPage mode="sign-in" />} />
          <Route path="/sign-up/*" element={<AuthenticationPage mode="sign-up" />} />
          <Route path="/auth/callback" element={<AuthenticationPage mode="callback" />} />
        </Route>
        <Route
          path="/app"
          element={
            <Protected>
              <ApplicationLayout />
            </Protected>
          }
        >
          <Route index element={<OrganizationSelection />} />
          <Route path="join" element={<AcceptInvitation />} />
          <Route path="create-organization" element={<CreateOrganization />} />
          <Route path="organizations/:organizationId" element={<OrganizationHome />} />
          <Route
            path="organizations/:organizationId/settings"
            element={<OrganizationHome settings />}
          />
          <Route
            path="organizations/:organizationId/knowledge"
            element={<WorkbenchPage section="knowledge" />}
          />
          <Route
            path="organizations/:organizationId/runs"
            element={<WorkbenchPage section="runs" />}
          />
          <Route
            path="organizations/:organizationId/audit"
            element={<WorkbenchPage section="audit" />}
          />
          <Route path="organizations/:organizationId/chat" element={<ChatPage />} />
          <Route path="organizations/:organizationId/teammates" element={<TeammatesPage />} />
          <Route path="organizations/:organizationId/members" element={<MembershipManagement />} />
          <Route
            path="*"
            element={
              <section>
                <h1 className="text-3xl font-semibold">Page not found</h1>
                <Link to="/app" className="mt-4 inline-block underline">
                  Back to organizations
                </Link>
              </section>
            }
          />
        </Route>
      </Routes>
    </div>
  );
}

function PublicLayout({ dark, toggle }: { dark: boolean; toggle: () => void }) {
  return (
    <>
      <header className="border-b border-[var(--border)] bg-[var(--surface)]">
        <div className="mx-auto flex min-h-18 max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-3">
          <Brand />
          <div className="flex items-center gap-4">
            <Link to="/status" className="hidden text-sm text-[var(--muted)] sm:block">
              System status
            </Link>
            <ThemeToggle dark={dark} toggle={toggle} />
            <AccountNavigation />
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="public-content">
        <Outlet />
      </main>
    </>
  );
}
