import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { components } from "@orqentra/contracts";
import { useSessionApi } from "./client";
import { OrganizationBilling } from "./billing";
import { WorkspaceAdministration } from "./workspace-admin";
import { Button } from "../components/ui/button";
import { ApiError } from "../lib/api";

type Overview = components["schemas"]["AdministrationResponse"];
type AuditPage = components["schemas"]["AuditExport"];
const panel = "rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6";
export function OrganizationAdministration({ organizationId }: { organizationId: string }) {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const base = `/organizations/${organizationId}/administration`;
  const [notice, setNotice] = useState("");
  const [cursor, setCursor] = useState<{ before: string; before_id: string } | null>(null);
  const overview = useQuery({
    queryKey: ["administration", userId, organizationId],
    queryFn: ({ signal }) => api<Overview>(base, { signal }),
  });
  const rename = useMutation({
    mutationFn: (name: string) =>
      api(`${base}/name`, {
        method: "PATCH",
        body: JSON.stringify({ name, expected_updated_at: overview.data?.updated_at }),
      }),
    onSuccess: () => {
      setNotice("Organization name updated.");
      for (const queryKey of [
        ["administration", userId, organizationId],
        ["organization", userId, organizationId],
        ["organizations", userId],
      ])
        void cache.invalidateQueries({ queryKey });
    },
    onError: (error) => {
      setNotice(
        error instanceof ApiError && error.status === 409
          ? "Another administrator changed this organization. Refresh before saving again."
          : "The organization could not be updated. Check your current access.",
      );
    },
  });
  const download = useMutation({
    mutationFn: () => api<AuditPage>(`${base}/audit-export?${new URLSearchParams(cursor ?? {})}`),
    onSuccess: (page) => {
      const url = URL.createObjectURL(
        new Blob(
          [
            JSON.stringify(
              { exported_at: new Date().toISOString(), organization_id: organizationId, ...page },
              null,
              2,
            ),
          ],
          { type: "application/json" },
        ),
      );
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `orqentra-audit-${organizationId}-${Date.now()}.json`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setCursor(
        page.next_before && page.next_before_id
          ? { before: page.next_before, before_id: page.next_before_id }
          : null,
      );
      setNotice(
        `Downloaded ${page.events.length} audit events.${page.next_before ? " More history is available: download the next page." : " End of available history."}`,
      );
    },
    onError: () => setNotice("Audit export failed. Your access may have changed; please retry."),
  });
  if (overview.isPending) return <p role="status">Loading organization administration…</p>;
  if (overview.isError)
    return (
      <section role="alert">
        <h1>Administration could not load</h1>
        <Button onClick={() => void overview.refetch()}>Retry</Button>
      </section>
    );
  const data = overview.data;
  const stats = [
    ["Active members", data.active_members],
    ["Active workspaces", data.active_workspaces],
    ["Indexed knowledge", `${data.indexed_documents} / ${data.active_documents}`],
    ["AI teammate definitions", data.teammates],
    ["Chat turns · 30 days", data.chat_turns],
    ["Task runs · 30 days", data.task_runs],
    ["Recorded input tokens", data.recorded_input_tokens.toLocaleString()],
    ["Recorded output tokens", data.recorded_output_tokens.toLocaleString()],
    ["Open human requests", data.pending_human_requests],
  ];
  return (
    <section>
      <div className="workspace-page-heading">
        <div>
          <p className="workspace-eyebrow">ORGANIZATION ADMINISTRATION</p>
          <h1>Organization settings</h1>
          <p>Manage your organization and review recorded activity.</p>
        </div>
        <Button asChild variant="outline">
          <Link to={`/app/organizations/${organizationId}`}>Command Center</Link>
        </Button>
      </div>
      {notice && (
        <p role="status" className={`${panel} mb-5`}>
          {notice}
        </p>
      )}
      <section className={`${panel} mb-6`}>
        <h2 className="text-xl font-semibold">Organization identity</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Slug: {data.slug} · Status: {data.status}. Renaming keeps existing URLs and records.
        </p>
        <form
          className="mt-5 flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            const name = String(new FormData(event.currentTarget).get("name") ?? "").trim();
            if (name) rename.mutate(name);
          }}
        >
          <label className="min-w-0 flex-1 text-sm">
            Organization name
            <input
              name="name"
              required
              maxLength={200}
              defaultValue={data.name}
              disabled={rename.isPending}
              className="mt-2 block w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3"
            />
          </label>
          <Button disabled={rename.isPending}>{rename.isPending ? "Saving…" : "Save name"}</Button>
        </form>
      </section>
      <section className={`${panel} mb-6`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Usage and resources</h2>
          <Button
            variant="outline"
            disabled={overview.isFetching}
            onClick={() => void overview.refetch()}
          >
            Refresh
          </Button>
        </div>
        <p className="mt-2 text-xs text-[var(--muted)]">
          Rolling period: {new Date(data.period_start).toLocaleDateString()} –{" "}
          {new Date(data.period_end).toLocaleDateString()}
        </p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {stats.map(([label, value]) => (
            <article key={label} className="rounded-lg border border-[var(--border)] p-4">
              <p className="text-xs text-[var(--muted)]">{label}</p>
              <p className="mt-2 text-2xl font-semibold">{value}</p>
            </article>
          ))}
        </div>
        <p className="mt-5 text-sm text-[var(--muted)]">{data.usage_notice}</p>
      </section>
      <WorkspaceAdministration organizationId={organizationId} />
      <OrganizationBilling organizationId={organizationId} />
      <section className={`${panel} mb-6`} aria-label="Commercial integrations">
        <h2 className="text-xl font-semibold">Commercial integrations</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">
          External capabilities remain unavailable until implemented, configured and verified.
        </p>
        <dl className="mt-4 space-y-3">
          {Object.entries(data.service_status ?? {}).map(([name, status]) => (
            <div key={name}>
              <dt className="font-semibold">{name}</dt>
              <dd className="text-sm text-[var(--muted)]">{status}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section className={panel}>
        <h2 className="text-xl font-semibold">Export audit history</h2>
        <p className="my-3 text-sm text-[var(--muted)]">
          Download up to 500 organization events per JSON file. Large histories provide a next-page
          download. Exports contain identifiers and timestamps; protect the downloaded files
          according to your organization’s policies.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button disabled={download.isPending} onClick={() => download.mutate()}>
            {download.isPending
              ? "Preparing…"
              : cursor
                ? "Download next page"
                : "Download audit JSON"}
          </Button>
          {cursor && (
            <Button variant="outline" onClick={() => setCursor(null)}>
              Start a new export
            </Button>
          )}
        </div>
      </section>
    </section>
  );
}
