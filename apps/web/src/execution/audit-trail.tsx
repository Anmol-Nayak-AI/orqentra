import { useState } from "react";
import { CheckCircle2, CircleAlert, History, Search, ShieldCheck } from "lucide-react";

export type AuditEvent = {
  id: string;
  action: string;
  resource_id: string;
  created_at: string;
};
const labels: Record<string, [string, string]> = {
  "chat.completed": [
    "Chat reply completed",
    "A reply was saved to a conversation. Open Chat to review the answer and any sources.",
  ],
  "chat.failed": [
    "Chat attempt failed",
    "This attempt did not produce an accepted reply. Later attempts are recorded separately.",
  ],
  "demo.chat_requeued": [
    "Demo chat retried",
    "A failed demo reply was queued for another attempt.",
  ],
  "demo.roster_seeded": [
    "Demo team added",
    "Fictional profiles were added for demonstration. No account access was granted.",
  ],
  "organization.created": [
    "Organization created",
    "Your organization and initial workspace were created.",
  ],
};
function describeEvent(action: string): [string, string] {
  return (
    labels[action] ?? [
      action.replaceAll(/[._]/g, " ").replace(/^./, (c) => c.toUpperCase()),
      "An organization change was recorded.",
    ]
  );
}
export function AuditTrail({ events }: { events: AuditEvent[] }) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const categories = [...new Set(events.map((e) => e.action.split(".")[0]))].sort();
  const visible = [...events]
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
    .filter(
      (e) =>
        (category === "all" || e.action.startsWith(`${category}.`)) &&
        `${describeEvent(e.action).join(" ")} ${e.action} ${e.resource_id}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    );
  return (
    <section
      className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)]"
      aria-label="Organization audit events"
    >
      <div className="flex flex-wrap items-start justify-between gap-5 border-b border-[var(--border)] p-6">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-semibold">
            <History size={20} aria-hidden="true" /> Activity history
          </h2>
          <p className="mt-2 max-w-xl text-sm text-[var(--muted)]">
            A permanent record of changes. A past failed attempt stays here even after a successful
            retry.
          </p>
        </div>
        <span className="flex items-center gap-2 text-xs text-[var(--muted)]">
          <ShieldCheck size={16} aria-hidden="true" /> Read-only history
        </span>
      </div>
      <div className="flex flex-wrap gap-3 border-b border-[var(--border)] p-5">
        <label className="flex w-full min-w-0 items-center sm:w-auto sm:flex-1 gap-2 rounded-lg border border-[var(--border)] px-3">
          <Search size={16} aria-hidden="true" />
          <input
            aria-label="Search audit events"
            placeholder="Search events or resource IDs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="min-w-0 w-full bg-transparent py-3 text-sm"
          />
        </label>
        <select
          aria-label="Filter event category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm"
        >
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </option>
          ))}
        </select>
      </div>
      <ol className="divide-y divide-[var(--border)]">
        {visible.map((event) => {
          const [title, description] = describeEvent(event.action);
          const failed = event.action.endsWith(".failed");
          const completed = event.action.endsWith(".completed");
          const recovered =
            event.action === "chat.failed" &&
            events.some(
              (later) =>
                later.action === "chat.completed" &&
                later.resource_id === event.resource_id &&
                Date.parse(later.created_at) > Date.parse(event.created_at),
            );
          const Icon = failed ? CircleAlert : completed ? CheckCircle2 : History;
          return (
            <li key={event.id} className="flex gap-4 p-5 sm:p-6">
              <span
                className={`mt-1 shrink-0 self-start rounded-lg bg-[var(--background)] p-2 ${failed ? "text-amber-700 dark:text-amber-400" : "text-[var(--muted)]"}`}
              >
                <Icon size={18} aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-semibold">{title}</h3>
                  <time dateTime={event.created_at} className="text-xs text-[var(--muted)]">
                    {new Intl.DateTimeFormat(undefined, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    }).format(new Date(event.created_at))}
                  </time>
                </div>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  {recovered
                    ? "Historical failure: a later reply for this same message completed successfully."
                    : description}
                </p>
                <details className="mt-3 text-xs text-[var(--muted)]">
                  <summary className="w-fit cursor-pointer">Event details</summary>
                  <dl className="mt-2 grid gap-2 break-all rounded-lg bg-[var(--background)] p-3">
                    <div>
                      <dt className="font-semibold">Event type</dt>
                      <dd>{event.action}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold">Resource ID</dt>
                      <dd>{event.resource_id}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold">Event ID</dt>
                      <dd>{event.id}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold">Timestamp (UTC)</dt>
                      <dd>{event.created_at}</dd>
                    </div>
                  </dl>
                </details>
              </div>
            </li>
          );
        })}
      </ol>
      {visible.length === 0 && (
        <p className="p-8 text-center text-sm text-[var(--muted)]">
          {events.length ? "No events match your filters." : "No activity has been recorded yet."}
        </p>
      )}
      <p
        className="border-t border-[var(--border)] px-6 py-4 text-xs text-[var(--muted)]"
        role="status"
      >
        Showing {visible.length} of {events.length} loaded events · Newest first · Times shown in
        your local time zone
      </p>
    </section>
  );
}
