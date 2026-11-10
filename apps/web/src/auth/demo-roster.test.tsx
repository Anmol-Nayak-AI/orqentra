import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { DemoRoster } from "./demo-roster";
vi.mock("./client", () => ({
  useSessionApi: () => ({
    userId: "user_roster_unit",
    api: async () => [
      {
        id: "demo-unit",
        display_name: "Mira Demo",
        email: "mira.demo@example.invalid",
        job_title: "Fictional analyst",
        demo_role: "ADMIN",
      },
    ],
  }),
}));
it("labels fictional profiles and exposes no real role-management controls", async () => {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <DemoRoster organizationId="tenant-unit" />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { name: "Mira Demo" })).toBeInTheDocument();
  expect(
    screen.getByText(/no sign-in credentials, real membership, or permissions/),
  ).toBeInTheDocument();
  expect(screen.getByText("Demo · ADMIN")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
});
