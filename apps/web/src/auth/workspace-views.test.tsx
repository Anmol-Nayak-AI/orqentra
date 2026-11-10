import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { expect, it } from "vitest";
import {
  WorkspaceFrame,
  OrganizationDirectoryView,
  OrganizationWorkspaceView,
} from "./workspace-views";
const organizations = [
  { id: "a", name: "Atlas Team", slug: "atlas", status: "ACTIVE" as const, role: "OWNER" as const },
  {
    id: "b",
    name: "Beacon Group",
    slug: "beacon",
    status: "ACTIVE" as const,
    role: "VIEWER" as const,
  },
];
it("filters actual organization data and recovers from an empty search", async () => {
  render(
    <MemoryRouter>
      <OrganizationDirectoryView organizations={organizations} />
    </MemoryRouter>,
  );
  await userEvent.type(screen.getByRole("textbox", { name: "Search organizations" }), "beacon");
  expect(screen.queryByRole("link", { name: "Atlas Team" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open Beacon Group" })).toHaveAttribute(
    "href",
    "/app/organizations/b",
  );
  await userEvent.clear(screen.getByRole("textbox", { name: "Search organizations" }));
  await userEvent.type(screen.getByRole("textbox", { name: "Search organizations" }), "missing");
  expect(screen.getByRole("heading", { name: "No matching organizations" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Clear search" }));
  expect(screen.getByRole("link", { name: "Atlas Team" })).toBeInTheDocument();
});
it("sorts without changing membership roles or organization destinations", async () => {
  render(
    <MemoryRouter>
      <OrganizationDirectoryView organizations={organizations} />
    </MemoryRouter>,
  );
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Sort organizations" }),
    "desc",
  );
  const rows = within(screen.getByRole("table", { name: "Your organizations" })).getAllByRole(
    "row",
  );
  expect(within(rows[1]).getByRole("link", { name: "Beacon Group" })).toBeInTheDocument();
  expect(within(rows[1]).getByText("VIEWER")).toBeInTheDocument();
});
it("shows real workspace names and scopes member/settings links to the selected organization", () => {
  render(
    <MemoryRouter>
      <OrganizationWorkspaceView
        organization={organizations[1]}
        loading={false}
        workspaces={[
          {
            id: "w",
            organization_id: "b",
            slug: "beacon-workspace",
            name: "Beacon workspace",
            status: "ACTIVE",
            updated_at: "2026-11-10T00:00:00Z",
          },
        ]}
      />
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { name: "Beacon workspace" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View members and roles" })).toHaveAttribute(
    "href",
    "/app/organizations/b/members",
  );
  expect(screen.getByRole("link", { name: "Organization settings" })).toHaveAttribute(
    "href",
    "/app/organizations/b/settings",
  );
});

function NavigationFixture() {
  const { pathname } = useLocation();
  const root = pathname.match(/^\/app\/organizations\/[^/]+/)?.[0] ?? null;
  return (
    <WorkspaceFrame
      title="Workspace"
      root={root}
      dark={false}
      toggle={() => {}}
      account={null}
      organizations={organizations}
    >
      <p>Test content</p>
    </WorkspaceFrame>
  );
}

it("requires organization selection before showing workspace navigation", async () => {
  render(
    <MemoryRouter initialEntries={["/app"]}>
      <NavigationFixture />
    </MemoryRouter>,
  );
  const nav = screen.getByRole("navigation", { name: "Workspace navigation" });
  expect(within(nav).getAllByRole("link")).toHaveLength(1);
  expect(within(nav).getByRole("link", { name: "All organizations" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Command Center" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Command Center" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Members" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Choose organization/ }));
  await userEvent.click(screen.getByRole("link", { name: /Atlas Team/ }));
  expect(within(nav).getByRole("link", { name: "Command Center" })).toHaveAttribute(
    "href",
    "/app/organizations/a",
  );
  expect(within(nav).getByRole("link", { name: "Members" })).toHaveAttribute(
    "href",
    "/app/organizations/a/members",
  );
  await userEvent.click(within(nav).getByRole("link", { name: "Command Center" }));
  expect(screen.queryByRole("region", { name: "Choose organization" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Atlas Team/ }));
  await userEvent.click(screen.getByRole("link", { name: /Beacon Group/ }));
  expect(within(nav).getByRole("link", { name: "Command Center" })).toHaveAttribute(
    "href",
    "/app/organizations/b",
  );
  expect(within(nav).queryByRole("link", { name: "Audit trail" })).not.toBeInTheDocument();
  await userEvent.click(within(nav).getByRole("link", { name: "All organizations" }));
  expect(within(nav).getAllByRole("link")).toHaveLength(1);
  expect(within(nav).queryByRole("link", { name: "Chat" })).not.toBeInTheDocument();
});
