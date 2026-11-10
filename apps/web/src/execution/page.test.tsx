import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { WorkbenchPage } from "./page";
const api = vi.hoisted(() => vi.fn());
vi.mock("../auth/client", () => ({ useSessionApi: () => ({ api, userId: "user_unit" }) }));
it("binds approval to the displayed revision and artifact, then displays simulation receipt", async () => {
  let status = "AWAITING_REVIEW";
  const hash = "a".repeat(64);
  api.mockImplementation(async (path: string) => {
    if (path.endsWith("/review")) {
      status = "APPROVED";
      return {};
    }
    if (path.endsWith("/receipt")) return { id: "receipt-unit", mode: "SIMULATED" };
    if (path.endsWith("/runs"))
      return [
        {
          id: "run-unit",
          status,
          request_text: "Unit onboarding request",
          revision: 3,
          artifact_hash: hash,
          created_at: "2026-11-04T00:00:00Z",
          output: { summary: "Synthetic unit output" },
          usage: {},
        },
      ];
    if (
      path.endsWith("/agents") ||
      path.endsWith("/workspaces") ||
      path.endsWith("/code-executions")
    )
      return [];
    return { role: "OWNER" };
  });
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={["/app/organizations/tenant-unit/runs"]}>
        <Routes>
          <Route
            path="/app/organizations/:organizationId/runs"
            element={<WorkbenchPage section="runs" />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await userEvent.click(await screen.findByRole("button", { name: /Unit onboarding request/ }));
  await userEvent.click(screen.getByRole("button", { name: "Approve draft" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/organizations/tenant-unit/runs/run-unit/review",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expected_revision: 3, artifact_hash: hash, decision: "APPROVE" }),
      }),
    ),
  );
  expect(await screen.findByRole("heading", { name: "Review receipt" })).toBeInTheDocument();
  expect(screen.getByText("No external message was sent.")).toBeInTheDocument();
});
