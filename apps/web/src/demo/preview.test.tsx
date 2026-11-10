import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DemoApp } from "./preview";

describe("isolated public preview", () => {
  it("keeps guided answers local, labels limitations and clears them when switching organizations", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockRejectedValue(new Error("No preview network"));
    const user = userEvent.setup();
    render(<DemoApp />);
    await user.click(screen.getByRole("button", { name: "Chat" }));
    await user.click(screen.getByRole("button", { name: "How does RAG chat work?" }));
    const log = screen.getByRole("log");
    expect(log).toHaveTextContent(/PostgreSQL\/pgvector/);
    expect(within(log).getByText(/scripted answer/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Ask about the product"), "Predict tomorrow's weather");
    await user.click(screen.getByRole("button", { name: "Ask" }));
    expect(
      within(log).getByText(/This guided preview has no live AI connection/),
    ).toBeInTheDocument();
    await user.selectOptions(
      screen.getByLabelText("Choose sample organization"),
      "Meridian Studio",
    );
    expect(within(log).getByText("Start with a question.")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("scopes the sample review state to the selected fictional organization", async () => {
    const user = userEvent.setup();
    render(<DemoApp />);
    await user.click(screen.getByRole("button", { name: "Tasks & reviews" }));
    await user.click(screen.getByRole("button", { name: "Mark preview reviewed" }));
    expect(screen.getByRole("button", { name: "Preview reviewed" })).toBeDisabled();
    await user.selectOptions(
      screen.getByLabelText("Choose sample organization"),
      "Meridian Studio",
    );
    expect(screen.getByRole("button", { name: "Mark preview reviewed" })).toBeEnabled();
    expect(
      screen.queryByText("Sample checklist marked reviewed in this browser tab."),
    ).not.toBeInTheDocument();
  });
});
