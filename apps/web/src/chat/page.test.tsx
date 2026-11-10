import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { ChatPage } from "./page";
const api = vi.hoisted(() => vi.fn());
vi.mock("../auth/client", () => ({ useSessionApi: () => ({ api, userId: "user_chat_unit" }) }));
it("queues a question in the selected chat without inventing an assistant reply", async () => {
  let queued = false;
  api.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.endsWith("/human-messages")) return [];
    if (path.endsWith("/memberships/me")) return { user_id: "local-requester" };
    if (/\/chats\/[^/]+$/.test(path))
      return {
        id: path.split("/").at(-1),
        workspace_id: "workspace-unit",
        title: "Test chat",
        support_state: "AI",
        assigned_to: null,
      };
    if (path.endsWith("/workspaces")) return [{ id: "workspace-unit", name: "Unit workspace" }];
    if (path.endsWith("/chats"))
      return [{ id: "chat-unit", workspace_id: "workspace-unit", title: "Demo knowledge chat" }];
    if (options?.method === "POST") {
      queued = true;
      return { id: "message-unit" };
    }
    return queued
      ? [
          {
            id: "message-unit",
            question: "What are support hours?",
            answer: "",
            citations: [],
            status: "QUEUED",
          },
        ]
      : [];
  });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={["/app/organizations/tenant-unit/chat"]}>
        <Routes>
          <Route path="/app/organizations/:organizationId/chat" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await userEvent.click(await screen.findByRole("button", { name: "Demo knowledge chat" }));
  await userEvent.type(
    screen.getByRole("textbox", { name: "Ask a knowledge question" }),
    "What are support hours?",
  );
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/organizations/tenant-unit/chats/chat-unit/messages",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(
    await screen.findByText("Waiting for source indexing and processing…"),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  view.unmount();
  cache.clear();
});

it("shows a completed answer with expandable source evidence", async () => {
  const quote = "Demo support is available from 09:00 to 17:00 UTC.";
  api.mockImplementation(async (path: string) => {
    if (path.endsWith("/human-messages")) return [];
    if (path.endsWith("/memberships/me")) return { user_id: "local-requester" };
    if (/\/chats\/[^/]+$/.test(path))
      return {
        id: path.split("/").at(-1),
        workspace_id: "workspace-unit",
        title: "Test chat",
        support_state: "AI",
        assigned_to: null,
      };
    if (path.endsWith("/workspaces")) return [{ id: "workspace-unit", name: "Unit workspace" }];
    if (path.endsWith("/chats"))
      return [{ id: "chat-unit", workspace_id: "workspace-unit", title: "Source review" }];
    return [
      {
        id: "message-evidence",
        question: "When is demo support available?",
        answer: "Demo support is available during the documented hours.",
        status: "COMPLETED",
        citations: [
          { chunk_id: "chunk-unit", document_id: "doc-unit", title: "Demo handbook", quote },
        ],
      },
    ];
  });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={["/app/organizations/tenant-unit/chat"]}>
        <Routes>
          <Route path="/app/organizations/:organizationId/chat" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await userEvent.click(await screen.findByRole("button", { name: "Source review" }));
  expect(
    await screen.findByText("Demo support is available during the documented hours."),
  ).toBeVisible();
  await userEvent.click(screen.getByText("1. Demo handbook"));
  expect(screen.getByText(quote)).toBeVisible();
  view.unmount();
  cache.clear();
});

it("opens the latest workspace conversation automatically", async () => {
  api.mockImplementation(async (path: string) => {
    if (path.endsWith("/human-messages")) return [];
    if (path.endsWith("/memberships/me")) return { user_id: "local-requester" };
    if (/\/chats\/[^/]+$/.test(path))
      return {
        id: path.split("/").at(-1),
        workspace_id: "workspace-unit",
        title: "Test chat",
        support_state: "AI",
        assigned_to: null,
      };
    if (path.endsWith("/workspaces")) return [{ id: "workspace-unit", name: "Unit workspace" }];
    if (path.endsWith("/chats"))
      return [{ id: "latest-chat", workspace_id: "workspace-unit", title: "Latest chat" }];
    return [
      {
        id: "latest-message",
        question: "What are support hours?",
        answer: "The saved answer is ready.",
        status: "COMPLETED",
        citations: [],
      },
    ];
  });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={["/app/organizations/tenant-unit/chat"]}>
        <Routes>
          <Route path="/app/organizations/:organizationId/chat" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("The saved answer is ready.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Latest chat" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  view.unmount();
  cache.clear();
});

it("uses a new idempotency key when editing a failed submission", async () => {
  const bodies: { question: string; idempotency_key: string }[] = [];
  api.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.endsWith("/human-messages")) return [];
    if (path.endsWith("/memberships/me")) return { user_id: "local-requester" };
    if (/\/chats\/[^/]+$/.test(path))
      return {
        id: path.split("/").at(-1),
        workspace_id: "workspace-unit",
        title: "Test chat",
        support_state: "AI",
        assigned_to: null,
      };
    if (path.endsWith("/workspaces")) return [{ id: "workspace-unit", name: "Unit workspace" }];
    if (path.endsWith("/chats"))
      return [{ id: "chat-unit", workspace_id: "workspace-unit", title: "Retry chat" }];
    if (options?.method === "POST") {
      bodies.push(JSON.parse(String(options.body)));
      throw new Error("synthetic network failure");
    }
    return [];
  });
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={["/app/organizations/tenant-unit/chat"]}>
        <Routes>
          <Route path="/app/organizations/:organizationId/chat" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const input = await screen.findByRole("textbox", { name: "Ask a knowledge question" });
  await waitFor(() => expect(input).toBeEnabled());
  await userEvent.type(input, "What are support hours?");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Message could not be queued");
  await userEvent.type(input, " And escalation?");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(bodies).toHaveLength(2));
  expect(bodies[0].idempotency_key).not.toBe(bodies[1].idempotency_key);
  view.unmount();
  cache.clear();
});

it("disables new AI questions when the worker is offline while keeping human help available", async () => {
  api.mockClear();
  api.mockImplementation(async (path: string) => {
    if (path.endsWith("/capabilities")) return { model_configured: true, worker_online: false };
    if (path.endsWith("/memberships/me")) return { user_id: "local-requester" };
    if (path.endsWith("/workspaces")) return [{ id: "workspace-unit", name: "Unit workspace" }];
    if (path.endsWith("/chats"))
      return [{ id: "chat-unit", workspace_id: "workspace-unit", title: "Offline-worker chat" }];
    if (/\/chats\/[^/]+$/.test(path))
      return {
        id: "chat-unit",
        workspace_id: "workspace-unit",
        title: "Offline-worker chat",
        support_state: "AI",
        created_by: "local-requester",
        assigned_to: null,
      };
    if (path === "/organizations/tenant-unit") return { role: "OWNER" };
    return [];
  });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={["/app/organizations/tenant-unit/chat"]}>
        <Routes>
          <Route path="/app/organizations/:organizationId/chat" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(
    await screen.findByText(/AI processing is unavailable for this organization/),
  ).toBeVisible();
  expect(await screen.findByRole("button", { name: "Send" })).toBeDisabled();
  expect(await screen.findByRole("button", { name: "Request human help" })).toBeEnabled();
  view.unmount();
  cache.clear();
});
