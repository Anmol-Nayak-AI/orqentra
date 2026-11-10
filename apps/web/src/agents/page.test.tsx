import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { TeammatesPage } from "./page";
const api = vi.hoisted(() => vi.fn());
vi.mock("../auth/client", () => ({ useSessionApi: () => ({ api, userId: "user_unit" }) }));
it.each(["onboarding.v1", "python-analysis.v1"] as const)(
  "creates a bounded %s teammate in the selected tenant and workspace",
  async (workflow) => {
    api.mockClear();
    const agents: unknown[] = [];
    api.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path.endsWith("/agents") && options?.method === "POST") {
        const body = JSON.parse(String(options.body));
        const agent = {
          ...body,
          id: "agent-unit",
          draft_configuration: body.configuration,
          lifecycle_status: "DRAFT",
          revision: 1,
        };
        agents.push(agent);
        return agent;
      }
      if (path.endsWith("/agents")) return [...agents];
      if (path.endsWith("/workspaces")) return [{ id: "workspace-unit", name: "Unit workspace" }];
      return { role: "OWNER" };
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={["/app/organizations/tenant-unit/teammates"]}>
          <Routes>
            <Route
              path="/app/organizations/:organizationId/teammates"
              element={<TeammatesPage />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Create teammate" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Onboarding specialist");
    await userEvent.type(screen.getByRole("textbox", { name: "Slug" }), "onboarding-specialist");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Workflow" }), workflow);
    await userEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        "/organizations/tenant-unit/agents",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    const call = api.mock.calls.find(
      ([path, options]) =>
        path === "/organizations/tenant-unit/agents" && options?.method === "POST",
    );
    expect(JSON.parse(String(call?.[1].body))).toMatchObject({
      workspace_id: "workspace-unit",
      configuration: {
        workflow,
        output_schema:
          workflow === "python-analysis.v1" ? "python_analysis_plan.v1" : "onboarding_plan.v1",
        tools: ["knowledge.search", "draft.compose"],
      },
    });
    expect(await screen.findByText("Draft saved.")).toBeInTheDocument();
  },
);
