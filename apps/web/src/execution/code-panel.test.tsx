import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { CodeExecutionPanel } from "./code-panel";
const api = vi.hoisted(() => vi.fn());
vi.mock("../auth/client", () => ({ useSessionApi: () => ({ api, userId: "clerk-synthetic" }) }));
afterEach(cleanup);
const hash = "a".repeat(64);
const request = {
  id: "code-unit",
  run_id: "run-unit",
  created_by: "creator-unit",
  reviewed_by: null,
  title: "Unit analysis",
  code: "print(4)",
  code_hash: hash,
  status: "AWAITING_REVIEW",
  revision: 2,
  approval_expires_at: null,
  output: "",
  error_code: null,
  created_at: "2026-11-10T00:00:00Z",
};
function mount() {
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={cache}>
      <CodeExecutionPanel organizationId="tenant-unit" runId="run-unit" manages writes />
    </QueryClientProvider>,
  );
  return () => {
    view.unmount();
    cache.clear();
  };
}
it("binds independent approval to the exact displayed code hash and revision", async () => {
  let status = "AWAITING_REVIEW";
  api.mockImplementation(async (path, options) => {
    if (path === "/me") return { id: "reviewer-unit" };
    if (path.endsWith("/capabilities")) return { sandbox_execution_available: false };
    if (options?.method === "POST") {
      status = "APPROVED";
      return {};
    }
    return [{ ...request, status, approval_expires_at: "2099-11-10T00:00:00Z" }];
  });
  const dispose = mount();
  await userEvent.click(await screen.findByRole("button", { name: "Approve this code" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/organizations/tenant-unit/code-executions/code-unit/review",
      expect.objectContaining({
        body: JSON.stringify({ expected_revision: 2, code_hash: hash, decision: "APPROVE" }),
      }),
    ),
  );
  expect(await screen.findByRole("button", { name: "Run in isolated sandbox" })).toBeDisabled();
  expect(screen.getByText(/Isolated execution unavailable/)).toBeVisible();
  dispose();
});
it("prevents self-approval and submits a separate proposal for the selected approved task", async () => {
  api.mockImplementation(async (path, options) => {
    if (path === "/me") return { id: "creator-unit" };
    if (path.endsWith("/capabilities")) return { sandbox_execution_available: false };
    if (options?.method === "POST") return {};
    return [request];
  });
  const dispose = mount();
  expect(
    await screen.findByText("A different administrator must review this proposal."),
  ).toBeVisible();
  expect(screen.queryByRole("button", { name: "Approve this code" })).not.toBeInTheDocument();
  await userEvent.type(screen.getByRole("textbox", { name: "Analysis title" }), "A new analysis");
  await userEvent.type(screen.getByRole("textbox", { name: "Python code" }), "print(4)");
  await userEvent.click(screen.getByRole("button", { name: "Submit code for independent review" }));
  await waitFor(() =>
    expect(
      api.mock.calls.some(
        ([path, options]) => path.endsWith("/code-executions") && options?.method === "POST",
      ),
    ).toBe(true),
  );
  const [, options] = api.mock.calls.find(
    ([path, options]) => path.endsWith("/code-executions") && options?.method === "POST",
  )!;
  expect(JSON.parse(options.body)).toMatchObject({
    run_id: "run-unit",
    title: "A new analysis",
    code: "print(4)",
  });
  dispose();
});

it("prefills approved AI code without making an execution request", async () => {
  api.mockImplementation(async (path) => {
    if (path === "/me") return { id: "creator-unit" };
    if (path.endsWith("/capabilities")) return { sandbox_execution_available: false };
    return [];
  });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={cache}>
      <CodeExecutionPanel
        organizationId="tenant-unit"
        runId="run-unit"
        initialCode="print(3 + 5 + 2)"
        manages
        writes
      />
    </QueryClientProvider>,
  );
  expect(screen.getByRole("textbox", { name: "Python code" })).toHaveValue("print(3 + 5 + 2)");
  await screen.findByText("No code proposals yet.");
  expect(api.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
  view.unmount();
  cache.clear();
});
