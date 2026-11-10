import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { OrganizationAdministration } from "./administration";
import { ApiError } from "../lib/api";
const api = vi.hoisted(() => vi.fn());
vi.mock("./client", () => ({ useSessionApi: () => ({ api, userId: "user-admin-unit" }) }));
const overview = {
  name: "Unit organization",
  slug: "unit-org",
  status: "ACTIVE",
  updated_at: "2026-11-09T00:00:00Z",
  period_start: "2026-10-10T00:00:00Z",
  period_end: "2026-11-09T00:00:00Z",
  active_members: 3,
  active_workspaces: 2,
  active_documents: 5,
  indexed_documents: 4,
  teammates: 2,
  chat_turns: 8,
  task_runs: 4,
  recorded_input_tokens: 123,
  recorded_output_tokens: 45,
  pending_human_requests: 1,
  usage_notice: "Recorded usage only, not an invoice.",
};
it("shows recorded usage and preserves inputs after a conflicting administrator update", async () => {
  api.mockImplementation(async (_path: string, options?: RequestInit) => {
    if (
      _path.endsWith("/workspaces") ||
      _path.endsWith("/operations") ||
      _path.endsWith("/history")
    )
      return [];
    if (_path.endsWith("/catalog"))
      return {
        mode: "disabled",
        checkout_enabled: false,
        plans: [],
        total_cycles: 12,
        notice: "Test provider disabled.",
      };
    if (_path.endsWith("/invoices"))
      return { invoices: [], next_offset: null, notice: "Test invoices only." };
    if (_path.endsWith("/billing"))
      return {
        mode: "disabled",
        subscription_status: "UNAVAILABLE",
        plan_key: "development",
        entitlements_available: true,
        quotas: { chat_turns: { used: 2, limit: 20, remaining: 18 } },
        notice: "Draft quotas; no payments.",
      };
    if (options?.method === "PATCH") throw new ApiError(409, "synthetic-request-id");
    return overview;
  });
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={cache}>
      <MemoryRouter>
        <OrganizationAdministration organizationId="org-unit" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Recorded usage only, not an invoice.")).toBeVisible();
  expect(await screen.findByText("Payments disabled", { exact: false })).toBeVisible();
  expect(screen.getByText("2 used / 20 allowed · 18 remaining")).toBeVisible();
  const input = screen.getByRole("textbox", { name: "Organization name" });
  await userEvent.clear(input);
  await userEvent.type(input, "A newer name");
  await userEvent.click(screen.getByRole("button", { name: "Save name" }));
  expect(await screen.findByText(/Another administrator changed this organization/)).toBeVisible();
  expect(input).toHaveValue("A newer name");
  const call = api.mock.calls.find(([, options]) => options?.method === "PATCH");
  expect(JSON.parse(call![1].body)).toEqual({
    name: "A newer name",
    expected_updated_at: overview.updated_at,
  });
  view.unmount();
  cache.clear();
});
