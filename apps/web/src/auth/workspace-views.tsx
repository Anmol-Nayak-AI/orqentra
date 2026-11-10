import { useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import {
  ArrowRight,
  Bot,
  MessageSquare,
  Building2,
  Check,
  ChevronDown,
  FolderOpen,
  Layers3,
  LayoutDashboard,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import type { OrganizationResponse, WorkspaceResponse } from "@orqentra/contracts";
import { Brand, ThemeToggle } from "../components/chrome";
import { Button } from "../components/ui/button";

export function WorkspaceFrame({
  children,
  title,
  root,
  dark,
  toggle,
  account,
  organizations = [],
}: {
  children: ReactNode;
  title: string;
  root: string | null;
  dark: boolean;
  toggle: () => void;
  account: ReactNode;
  organizations?: OrganizationResponse[];
}) {
  const [selection, setSelection] = useState<string | null>(null);
  const selected = organizations.find((org) => root === `/app/organizations/${org.id}`);
  const navigation = [
    [root, "Command Center", LayoutDashboard],
    [root ? `${root}/teammates` : null, "Teammates", Bot],
    [root ? `${root}/chat` : null, "Chat", MessageSquare],
    [root ? `${root}/knowledge` : null, "Knowledge", FolderOpen],
    [root ? `${root}/runs` : null, "Tasks & reviews", LayoutDashboard],
    [root ? `${root}/audit` : null, "Audit trail", ShieldCheck],
    [root ? `${root}/members` : null, "Members", Users],
    [root ? `${root}/settings` : null, "Settings", Settings],
  ] as const;
  return (
    <div className="workspace-shell" data-theme={dark ? "dark" : "light"}>
      <aside className="workspace-sidebar">
        <div className="workspace-brand">
          <Brand />
          <span className="workspace-edition">WORKFORCE PLATFORM</span>
        </div>
        <button
          type="button"
          className="workspace-switch"
          aria-expanded={selection !== null}
          aria-controls="organization-switcher"
          onClick={() => setSelection(selection === null ? "" : null)}
        >
          <span className="workspace-switch-icon">
            <Building2 size={17} />
          </span>
          <span>
            <strong>{selected?.name ?? "Choose organization"}</strong>
            <small>{selected ? "Switch organization" : "Open your team's workspace"}</small>
          </span>
          <ChevronDown size={14} />
        </button>
        {selection !== null && (
          <section
            id="organization-switcher"
            className="organization-switcher"
            aria-label="Choose organization"
          >
            <p>{root ? "Switch organization" : "Choose an organization to continue"}</p>
            {organizations.map((org) => (
              <Link
                key={org.id}
                to={`/app/organizations/${org.id}`}
                onClick={() => setSelection(null)}
              >
                <Building2 size={15} />
                <span>
                  {org.name}
                  <small>{org.role}</small>
                </span>
                {selected?.id === org.id && <Check size={14} />}
              </Link>
            ))}
            {organizations.length === 0 && (
              <p>No organizations available for this section. Create one to get started.</p>
            )}
            <Link to="/app/create-organization" onClick={() => setSelection(null)}>
              <Plus size={15} />
              Create organization
            </Link>
          </section>
        )}
        <p className="workspace-nav-label">{root ? "WORKSPACE" : "ORGANIZATIONS"}</p>
        <nav aria-label="Workspace navigation">
          <NavLink
            to="/app"
            onClick={() => setSelection(null)}
            end
            className={({ isActive }) => `workspace-nav-item ${isActive ? "is-active" : ""}`}
          >
            <Building2 size={17} />
            All organizations
          </NavLink>
          {root &&
            navigation
              .filter(
                ([, label]) =>
                  label !== "Audit trail" ||
                  selected?.role === "OWNER" ||
                  selected?.role === "ADMIN",
              )
              .map(
                ([href, label, Icon]) =>
                  href && (
                    <NavLink
                      key={label}
                      to={href}
                      end
                      className={({ isActive }) =>
                        `workspace-nav-item ${isActive ? "is-active" : ""}`
                      }
                    >
                      <Icon size={17} />
                      {label}
                    </NavLink>
                  ),
              )}
        </nav>
        {!root && (
          <p className="workspace-nav-hint">
            Choose an organization above or open a workspace from the directory. Its Command Center
            and workspace sections will appear here.
          </p>
        )}
        <div className="workspace-sidebar-footer">
          <p>
            Your workforce,
            <br />
            <strong>intelligently orchestrated.</strong>
          </p>
          <Link to="/status">
            <Layers3 size={14} />
            System status
            <ArrowRight className="workspace-forward" size={13} />
          </Link>
        </div>
      </aside>
      <div className="workspace-content">
        <header className="workspace-header">
          <div className="workspace-breadcrumb">
            <span>Workspace</span>
            <span>/</span>
            <strong>{title}</strong>
          </div>
          <div className="workspace-header-actions">
            <ThemeToggle dark={dark} toggle={toggle} />
            {account}
          </div>
        </header>
        <main id="main" tabIndex={-1} className="workspace-main">
          {children}
        </main>
        <footer className="workspace-footer">
          <span>Orqentra workspace</span>
          <span>Built around your organization.</span>
        </footer>
      </div>
    </div>
  );
}

export function OrganizationDirectoryView({
  organizations,
}: {
  organizations: OrganizationResponse[];
}) {
  const [search, setSearch] = useState("");
  const [order, setOrder] = useState("asc");
  const filtered = organizations
    .filter((org) => `${org.name} ${org.slug}`.toLowerCase().includes(search.trim().toLowerCase()))
    .sort((a, b) => (order === "asc" ? 1 : -1) * a.name.localeCompare(b.name));
  const owners = organizations.filter((org) => org.role === "OWNER").length;
  return (
    <section className="directory-page">
      <div className="workspace-page-heading">
        <div>
          <p className="workspace-eyebrow">YOUR CONNECTED WORKSPACE</p>
          <h1>Your organizations</h1>
          <p>One account. A dedicated space for every team you belong to.</p>
        </div>
        <Button asChild>
          <Link to="/app/create-organization">
            <Plus size={16} />
            Create organization
          </Link>
        </Button>
      </div>
      <div className="workspace-stats">
        <Summary
          icon={<Building2 size={20} />}
          label="Organizations"
          value={String(organizations.length)}
          caption="Available to your account"
        />
        <Summary
          icon={<ShieldCheck size={20} />}
          label="Owner access"
          value={String(owners)}
          caption="Organizations you own"
        />
        <Summary
          icon={<Users size={20} />}
          label="Other organization roles"
          value={String(organizations.length - owners)}
          caption="Access granted by your role"
        />
      </div>
      <div className="directory-panel">
        <div className="directory-toolbar">
          <div>
            <h2>
              Organization directory <span className="directory-count">{organizations.length}</span>
            </h2>
            <p>Choose an organization to enter its workspace.</p>
          </div>
          <div className="directory-tools">
            <label className="directory-search">
              <Search size={16} />
              <span className="sr-only">Search organizations</span>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search organizations…"
              />
              {search && (
                <button
                  type="button"
                  aria-label="Clear organization search"
                  onClick={() => setSearch("")}
                >
                  <X size={14} />
                </button>
              )}
            </label>
            <label>
              <span className="sr-only">Sort organizations</span>
              <select value={order} onChange={(e) => setOrder(e.target.value)}>
                <option value="asc">Name A–Z</option>
                <option value="desc">Name Z–A</option>
              </select>
            </label>
          </div>
        </div>
        {organizations.length === 0 ? (
          <div className="directory-empty">
            <span className="directory-empty-icon">
              <Building2 size={30} />
            </span>
            <h3>Your first organization starts here</h3>
            <p>
              Create a shared workspace, manage membership, and keep your team’s access in one
              place.
            </p>
            <Button asChild>
              <Link to="/app/create-organization">
                <Plus size={16} />
                Create your first organization
              </Link>
            </Button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="directory-empty">
            <Search size={26} />
            <h3>No matching organizations</h3>
            <p>Try a different name or slug.</p>
            <Button variant="outline" onClick={() => setSearch("")}>
              Clear search
            </Button>
          </div>
        ) : (
          <div className="directory-table-wrap">
            <table className="directory-table" aria-label="Your organizations">
              <thead>
                <tr className="directory-table-header">
                  <th scope="col">ORGANIZATION</th>
                  <th scope="col">YOUR ROLE</th>
                  <th scope="col">STATUS</th>
                  <th scope="col">WORKSPACE</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((org) => (
                  <tr className="directory-row" key={org.id}>
                    <td className="directory-identity">
                      <span className="organization-monogram">
                        {org.name.slice(0, 2).toUpperCase()}
                      </span>
                      <div>
                        <Link to={`/app/organizations/${org.id}`}>{org.name}</Link>
                        <p>{org.slug}</p>
                      </div>
                    </td>
                    <td>
                      <span className="workspace-role">
                        <ShieldCheck size={12} />
                        {org.role}
                      </span>
                    </td>
                    <td>
                      <span className="workspace-status">
                        <span />
                        {org.status === "ACTIVE" ? "Active" : org.status}
                      </span>
                    </td>
                    <td>
                      <Link
                        className="organization-open"
                        aria-label={`Open ${org.name}`}
                        to={`/app/organizations/${org.id}`}
                      >
                        Open workspace
                        <ArrowRight className="workspace-forward" size={15} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="directory-results">
          {filtered.length} of {organizations.length} organizations shown
          <span>
            <ShieldCheck size={13} />
            Access is managed per organization
          </span>
        </div>
      </div>
      <section className="workspace-guide">
        <div>
          <p className="workspace-eyebrow">A CLEAR PLACE TO START</p>
          <h2>Make yourself at home.</h2>
          <p>Each organization keeps its people and workspaces together.</p>
        </div>
        <div>
          <span>01</span>
          <h3>Choose your team</h3>
          <p>Open an organization from the directory above.</p>
        </div>
        <div>
          <span>02</span>
          <h3>Find your workspace</h3>
          <p>See the workspaces available to your membership.</p>
        </div>
        <div>
          <span>03</span>
          <h3>Manage access</h3>
          <p>Review members and the roles that govern access.</p>
        </div>
      </section>
    </section>
  );
}

function Summary({
  icon,
  label,
  value,
  caption,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  caption: string;
}) {
  return (
    <article className="workspace-stat">
      <div>
        <span>{label}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <p>{caption}</p>
    </article>
  );
}

export function OrganizationWorkspaceView({
  organization,
  workspaces,
  loading,
  workspaceError,
  settings = false,
}: {
  organization: OrganizationResponse;
  workspaces?: WorkspaceResponse[];
  loading: boolean;
  workspaceError?: ReactNode;
  settings?: boolean;
}) {
  const root = `/app/organizations/${organization.id}`;
  return (
    <section>
      <div className="workspace-page-heading">
        <div>
          <p className="workspace-eyebrow">
            {organization.name} · {organization.role}
          </p>
          <h1>{settings ? "Organization settings" : "Command Center"}</h1>
          <p>
            {settings
              ? "The details and access that define your organization."
              : "Your team’s shared home. Keep your people, permissions, and workspaces connected."}
          </p>
        </div>
        <Button asChild variant="outline">
          <Link to="/app">
            <Building2 size={16} />
            Switch organization
          </Link>
        </Button>
      </div>
      <div className="workspace-stats">
        <Summary
          icon={<ShieldCheck size={20} />}
          label="Your role"
          value={organization.role}
          caption="Current organization access"
        />
        <Summary
          icon={<Check size={20} />}
          label="Organization status"
          value={organization.status === "ACTIVE" ? "Active" : organization.status}
          caption="Status from your organization"
        />
        <Summary
          icon={<FolderOpen size={20} />}
          label="Workspaces listed"
          value={loading ? "—" : workspaceError ? "Unavailable" : String(workspaces?.length ?? 0)}
          caption="Visible in this workspace list"
        />
      </div>
      {settings && (
        <section className="workspace-details">
          <div>
            <h2>Organization details</h2>
            <p className="workspace-section-description">
              Read-only details for this organization.
            </p>
          </div>
          <dl>
            {[
              ["Organization name", organization.name],
              ["Organization slug", organization.slug],
              ["Your role", organization.role],
              ["Status", organization.status],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      <div className="workspace-overview-grid">
        <section className="workspace-details">
          <div className="workspace-section-header">
            <div>
              <h2>Workspaces</h2>
              <p className="workspace-section-description">The shared spaces available to you.</p>
            </div>
            <FolderOpen className="workspace-section-icon" size={21} />
          </div>
          {loading ? (
            <p role="status" className="p-6">
              Loading workspaces…
            </p>
          ) : workspaceError ? (
            workspaceError
          ) : !workspaces?.length ? (
            <p className="p-6 text-sm">No active workspaces are available in this organization.</p>
          ) : (
            <div className="workspace-list">
              {workspaces.map((workspace) => (
                <article key={workspace.id}>
                  <span className="workspace-folder">
                    <FolderOpen size={22} />
                  </span>
                  <div>
                    <h3>{workspace.name}</h3>
                    <p>Organization workspace</p>
                  </div>
                  <span className="workspace-status">
                    <span />
                    {workspace.status === "ACTIVE" ? "Active" : workspace.status}
                  </span>
                </article>
              ))}
            </div>
          )}
        </section>
        <aside className="workspace-access-panel">
          <ShieldCheck className="workspace-panel-icon" size={24} />
          <p className="workspace-eyebrow">PEOPLE & PERMISSIONS</p>
          <h2>
            The right access.
            <br />
            For the right people.
          </h2>
          <p>Your membership determines what you can view and manage in this organization.</p>
          <Link to={`${root}/members`}>
            View members and roles
            <ArrowRight className="workspace-forward" size={16} />
          </Link>
        </aside>
      </div>
      {!settings && (
        <section className="workspace-action-row">
          <div className="workspace-action-main">
            <Settings size={20} />
            <div>
              <h2>Keep your organization in view</h2>
              <p className="workspace-action-description">
                Review organization details and your current access.
              </p>
            </div>
          </div>
          <Link to={`${root}/settings`}>
            Organization settings
            <ArrowRight className="workspace-forward" size={15} />
          </Link>
        </section>
      )}
    </section>
  );
}
