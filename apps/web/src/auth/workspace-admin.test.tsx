import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { WorkspaceAdministration } from "./workspace-admin";
const api = vi.hoisted(() => vi.fn());
vi.mock("./client", () => ({ useSessionApi: () => ({ api, userId: "clerk-unit" }) }));
it("creates a workspace inside the current organization and refreshes the available list", async () => {
  const rows: unknown[] = [];
  api.mockImplementation(async (_path, options) => {
    if (options?.method === "POST") {
      rows.push({
        ...JSON.parse(options.body),
        id: "workspace-unit",
        updated_at: "2026-11-10T00:00:00Z",
      });
      return rows[0];
    }
    return [...rows];
  });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={cache}>
      <WorkspaceAdministration organizationId="tenant-unit" />
    </QueryClientProvider>,
  );
  await userEvent.type(screen.getByRole("textbox", { name: "Workspace name" }), "Customer success");
  await userEvent.type(screen.getByRole("textbox", { name: "Workspace slug" }), "customer-success");
  await userEvent.click(screen.getByRole("button", { name: "Create workspace" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/organizations/tenant-unit/workspaces",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "Customer success", slug: "customer-success" }),
      }),
    ),
  );
  expect(await screen.findByRole("textbox", { name: "Name for customer-success" })).toHaveValue(
    "Customer success",
  );
  view.unmount();
  cache.clear();
});
