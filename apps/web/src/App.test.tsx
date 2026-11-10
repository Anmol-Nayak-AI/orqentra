import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";

function renderApp(path = "/status") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("shows real fetched liveness without claiming database readiness", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ status: "ok", service: "orqentra-api", checkpoint: "2A" })),
      ),
  );
  renderApp();
  expect(await screen.findByText("API connected")).toBeInTheDocument();
  expect(
    screen.getByText(/Database and identity readiness are checked separately/),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Switch to light theme" }));
  expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeInTheDocument();
});

it("recovers from a network error on explicit retry", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Network error"))
      .mockImplementation(
        async () =>
          new Response(JSON.stringify({ status: "ok", service: "orqentra-api", checkpoint: "2A" })),
      ),
  );
  renderApp();
  expect(await screen.findByText("API unavailable")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Check again" }));
  expect(await screen.findByText("API connected")).toBeInTheDocument();
});

it("provides a usable unknown route", () => {
  renderApp("/missing");
  expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Return home" })).toHaveAttribute("href", "/");
});

it("shows a clear public entry page with sign-in and registration routes", () => {
  renderApp("/");
  expect(screen.getByRole("heading", { name: /Your workforce,/ })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Get started" })).toHaveAttribute("href", "/sign-up");
});
