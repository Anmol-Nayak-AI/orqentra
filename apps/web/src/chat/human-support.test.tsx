import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { HumanSupport } from "./human-support";
const api = vi.hoisted(() => vi.fn());
vi.mock("../auth/client", () => ({ useSessionApi: () => ({ api, userId: "user-unit" }) }));
it("requires explicit consent before sharing a private chat with human support", async () => {
  api.mockImplementation(async (path: string) =>
    path.endsWith("/me") ? { user_id: "local-user" } : [],
  );
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={cache}>
      <HumanSupport
        organizationId="org-unit"
        requester
        chat={{
          id: "chat-unit",
          workspace_id: "workspace-unit",
          title: "Private chat",
          created_at: "2026-11-09T04:00:00Z",
          support_state: "AI",
          assigned_to: null,
        }}
      />
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Request human help" }));
  expect(screen.getByText(/This shares this conversation and its history/)).toBeVisible();
  expect(api.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Confirm request" }));
  expect(api).toHaveBeenCalledWith("/organizations/org-unit/chats/chat-unit/handoff", {
    method: "POST",
  });
  view.unmount();
  cache.clear();
});
it("shows an honest waiting state without claiming that a human has joined", async () => {
  api.mockImplementation(async (path: string) =>
    path.endsWith("/me") ? { user_id: "local-user" } : [],
  );
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={cache}>
      <HumanSupport
        organizationId="org-unit"
        requester
        chat={{
          id: "chat-unit",
          workspace_id: "workspace-unit",
          title: "Shared chat",
          created_at: "2026-11-09T04:00:00Z",
          support_state: "WAITING",
          assigned_to: null,
        }}
      />
    </QueryClientProvider>,
  );
  expect(
    screen.getByText("Waiting for an authorized teammate. No one has joined yet."),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: "Return to AI" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Claim conversation" })).not.toBeInTheDocument();
  view.unmount();
  cache.clear();
});
