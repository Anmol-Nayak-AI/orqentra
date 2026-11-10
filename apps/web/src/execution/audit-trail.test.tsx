import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { AuditTrail } from "./audit-trail";

it("keeps failed history visible after completion and filters without losing event details", async () => {
  const user = userEvent.setup();
  render(
    <AuditTrail
      events={[
        {
          id: "failed-id",
          action: "chat.failed",
          resource_id: "shared-resource",
          created_at: "2026-11-05T10:00:00Z",
        },
        {
          id: "completed-id",
          action: "chat.completed",
          resource_id: "shared-resource",
          created_at: "2026-11-06T10:00:00Z",
        },
        {
          id: "created-id",
          action: "organization.created",
          resource_id: "org-resource",
          created_at: "2026-11-03T10:00:00Z",
        },
      ]}
    />,
  );
  expect(screen.getAllByRole("listitem")[0]).toHaveTextContent("Chat reply completed");
  expect(screen.getByText("Chat attempt failed")).toBeVisible();
  await user.selectOptions(screen.getByLabelText("Filter event category"), "organization");
  expect(screen.queryByText("Chat reply completed")).not.toBeInTheDocument();
  expect(screen.getByText("Organization created")).toBeVisible();
  await user.selectOptions(screen.getByLabelText("Filter event category"), "all");
  await user.type(screen.getByLabelText("Search audit events"), "shared-resource");
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  await user.click(screen.getAllByText("Event details")[0]);
  expect(screen.getByText("completed-id")).toBeVisible();
  await user.clear(screen.getByLabelText("Search audit events"));
  await user.type(screen.getByLabelText("Search audit events"), "no-match");
  expect(screen.getByText("No events match your filters.")).toBeVisible();
});
