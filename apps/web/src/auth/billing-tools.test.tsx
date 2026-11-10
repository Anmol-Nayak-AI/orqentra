import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { OrganizationBilling } from "./billing";
const api = vi.hoisted(() => vi.fn());
vi.mock("./client", () => ({ useSessionApi: () => ({ api, userId: "clerk-billing-unit" }) }));
afterEach(cleanup);
const quote = "a".repeat(64);
function setup(enabled: boolean) {
  const operations: unknown[] = [];
  api.mockClear();
  api.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.endsWith("/checkout") && options?.method === "POST") {
      const item = {
        id: "operation-unit",
        kind: "CHECKOUT",
        status: "READY",
        mode: "test",
        plan_key: "pilot",
        external_id: "sub_unit",
        hosted_url: "https://rzp.io/rzp/unit",
        error_code: null,
        created_at: "2026-11-10T00:00:00Z",
      };
      operations.push(item);
      return item;
    }
    if (path.endsWith("/catalog"))
      return {
        mode: "test",
        checkout_enabled: enabled,
        total_cycles: 12,
        plans: [
          {
            key: "pilot",
            quote_hash: quote,
            amount_minor: 50000,
            currency: "INR",
            interval: 1,
            period: "monthly",
            quotas: { chat_turns: 100 },
          },
        ],
        notice: "Test plans only.",
      };
    if (path.endsWith("/operations")) return [...operations];
    if (path.endsWith("/history")) return [];
    if (path.endsWith("/invoices"))
      return { invoices: [], next_offset: null, notice: "Provider test records only." };
    return {
      provider: "razorpay",
      mode: "test",
      subscription_status: operations.length ? "PENDING" : "UNAVAILABLE",
      plan_key: "pilot",
      entitlements_available: false,
      quotas: {},
      recorded_usage: {},
      notice: "No actual invoice.",
      actions_enabled: enabled,
      external_id: operations.length ? "sub_unit" : null,
      period_end: null,
    };
  });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={cache}>
      <OrganizationBilling organizationId="tenant-unit" />
    </QueryClientProvider>,
  );
  return () => {
    view.unmount();
    cache.clear();
  };
}
it("binds test checkout to the displayed quote and keeps authorization separate from entitlement", async () => {
  const dispose = setup(true);
  await userEvent.selectOptions(
    await screen.findByRole("combobox", { name: "Configured test plan" }),
    "pilot",
  );
  await userEvent.click(screen.getByRole("button", { name: "Prepare test checkout" }));
  await waitFor(() =>
    expect(
      api.mock.calls.some(
        ([path, options]) => path.endsWith("/checkout") && options?.method === "POST",
      ),
    ).toBe(true),
  );
  const [, options] = api.mock.calls.find(
    ([path, options]) => path.endsWith("/checkout") && options?.method === "POST",
  )!;
  expect(JSON.parse(String(options.body))).toMatchObject({ plan_key: "pilot", quote_hash: quote });
  const link = await screen.findByRole("link", { name: "Open provider test authorization" });
  expect(link).toHaveAttribute("href", "https://rzp.io/rzp/unit");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
  expect(await screen.findByText(/Subscription: pending/)).toBeVisible();
  expect(screen.getByText(/AI intake is unavailable under the current policy/)).toBeVisible();
  expect(screen.getByText(/does not establish payment success/)).toBeVisible();
  dispose();
});
it("does not issue a provider action while the explicit test action flag is disabled", async () => {
  const dispose = setup(false);
  await userEvent.selectOptions(
    await screen.findByRole("combobox", { name: "Configured test plan" }),
    "pilot",
  );
  const button = screen.getByRole("button", { name: "Prepare test checkout" });
  expect(button).toBeDisabled();
  await userEvent.click(button);
  expect(api.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
  dispose();
});
