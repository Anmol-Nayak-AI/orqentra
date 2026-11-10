import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import type { components, WorkspaceResponse, OrganizationResponse } from "@orqentra/contracts";
import { useSessionApi } from "../auth/client";
import { Button } from "../components/ui/button";
import { AuditTrail } from "./audit-trail";
import { CodeExecutionPanel } from "./code-panel";
import { TaskArtifact } from "./task-artifact";

type Document = components["schemas"]["DocumentResponse"];
type Run = components["schemas"]["RunResponse"];
type Agent = components["schemas"]["AgentResponse"];
type Version = components["schemas"]["AgentVersionResponse"];
type Receipt = components["schemas"]["ReceiptResponse"];
const panel = "rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6";
const field = "mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3";

export function WorkbenchPage({ section }: { section: "knowledge" | "runs" | "audit" }) {
  const { organizationId = "" } = useParams();
  return (
    <Workbench
      key={`${organizationId}-${section}`}
      organizationId={organizationId}
      section={section}
    />
  );
}
function Workbench({
  organizationId,
  section,
}: {
  organizationId: string;
  section: "knowledge" | "runs" | "audit";
}) {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const base = `/organizations/${organizationId}`;
  const [notice, setNotice] = useState("");
  const [agentId, setAgentId] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [intakeKey, setIntakeKey] = useState(() => crypto.randomUUID());
  const organization = useQuery({
    queryKey: ["organization", userId, organizationId],
    queryFn: ({ signal }) => api<OrganizationResponse>(base, { signal }),
  });
  const workspaces = useQuery({
    queryKey: ["workspaces", userId, organizationId],
    queryFn: ({ signal }) => api<WorkspaceResponse[]>(`${base}/workspaces`, { signal }),
  });
  const agents = useQuery({
    queryKey: ["agents", userId, organizationId],
    queryFn: ({ signal }) => api<Agent[]>(`${base}/agents`, { signal }),
    enabled: section === "runs",
  });
  const versions = useQuery({
    queryKey: ["agent-versions", userId, organizationId, agentId],
    queryFn: ({ signal }) => api<Version[]>(`${base}/agents/${agentId}/versions`, { signal }),
    enabled: !!agentId,
  });
  const documents = useQuery({
    queryKey: ["knowledge", userId, organizationId],
    queryFn: ({ signal }) => api<Document[]>(`${base}/knowledge`, { signal }),
    enabled: section === "knowledge",
    refetchInterval: (query) =>
      query.state.data?.some(
        (doc) => doc.index_status === "PENDING" || doc.index_status === "INDEXING",
      )
        ? 3000
        : false,
  });
  const runs = useQuery({
    queryKey: ["runs", userId, organizationId],
    queryFn: ({ signal }) => api<Run[]>(`${base}/runs`, { signal }),
    enabled: section === "runs",
    refetchInterval: 5000,
  });
  const audits = useQuery({
    queryKey: ["audit", userId, organizationId],
    queryFn: ({ signal }) =>
      api<
        {
          id: string;
          action: string;
          resource_id: string;
          created_at: string;
        }[]
      >(`${base}/audit`, { signal }),
    enabled: section === "audit",
  });
  const receipt = useQuery({
    queryKey: ["receipt", userId, organizationId, selected],
    queryFn: ({ signal }) => api<Receipt>(`${base}/runs/${selected}/receipt`, { signal }),
    enabled: !!selected && runs.data?.find((r) => r.id === selected)?.status === "APPROVED",
  });
  const mutation = useMutation({
    mutationFn: ({ path, method, body }: { path: string; method: string; body?: unknown }) =>
      api(base + path, {
        method,
        ...(body ? { body: JSON.stringify(body) } : {}),
      }),
    onSuccess: (_, variables) => {
      setNotice(
        variables.path.endsWith("/review")
          ? "Draft review recorded. Approved output can be downloaded; no external message was sent."
          : "Saved.",
      );
      if (variables.path === "/runs") setIntakeKey(crypto.randomUUID());
      for (const key of ["knowledge", "runs", "audit", "receipt"])
        void cache.invalidateQueries({
          queryKey: [key, userId, organizationId],
        });
    },
    onError: () =>
      setNotice(
        "Request failed. Review your access, input, and the latest run revision before retrying.",
      ),
  });
  const manages = organization.data?.role === "OWNER" || organization.data?.role === "ADMIN";
  const writes = manages || organization.data?.role === "MEMBER";
  const capabilities = useQuery({
    queryKey: ["capabilities", userId, organizationId],
    queryFn: ({ signal }) =>
      api<components["schemas"]["ExecutionCapabilities"]>(`${base}/capabilities`, { signal }),
    enabled: section === "runs",
  });
  const current = runs.data?.find((r) => r.id === selected);
  const activeQuery = section === "knowledge" ? documents : section === "runs" ? runs : audits;
  return (
    <section>
      <div className="workspace-page-heading">
        <div>
          <p className="workspace-eyebrow">WORKFORCE OPERATIONS</p>
          <h1>
            {section === "knowledge"
              ? "Knowledge library"
              : section === "runs"
                ? "Tasks & reviews"
                : "Audit trail"}
          </h1>
          <p>
            {section === "knowledge"
              ? "Approved sources with a semantic vector index for tasks and chat."
              : section === "runs"
                ? "Track durable tasks, inspect evidence, and review exact drafts."
                : "Recorded changes across your organization."}
          </p>
        </div>
      </div>
      {section === "runs" && capabilities.data?.model_configured === false && (
        <p role="status" className={`${panel} mb-5`}>
          AI processing is not configured for this environment. Ask your administrator to enable it
          before starting tasks.
        </p>
      )}
      {section === "runs" && capabilities.data?.worker_online === false && (
        <p role="status" className={`${panel} mb-5`}>
          The AI worker is offline or has not been enabled for this organization. Existing drafts
          and reviews remain available. An operator must activate processing before new tasks can
          run.
        </p>
      )}
      {notice && (
        <p role="status" className={`${panel} mb-5`}>
          {notice}
        </p>
      )}
      {activeQuery.isPending ? (
        <p role="status">Loading…</p>
      ) : activeQuery.isError ? (
        <div role="alert">
          Could not load this section.{" "}
          <Button onClick={() => void activeQuery.refetch()}>Retry</Button>
        </div>
      ) : null}
      {section === "knowledge" && (
        <div className="grid gap-6 lg:grid-cols-2">
          {manages && (
            <form
              className={panel}
              onSubmit={(e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                mutation.mutate({
                  path: "/knowledge",
                  method: "POST",
                  body: {
                    workspace_id: data.get("workspace"),
                    title: data.get("title"),
                    content,
                  },
                });
              }}
            >
              <h2 className="text-xl font-semibold">Add approved source</h2>
              <label className="mt-4 block">
                Workspace
                <select className={field} name="workspace" required>
                  {workspaces.data?.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="mt-4 block">
                Title
                <input name="title" className={field} required maxLength={200} />
              </label>
              <label className="mt-4 block">
                Upload UTF-8 text
                <input
                  className={field}
                  type="file"
                  accept=".txt,text/plain"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      if (file.size > 24000) {
                        setNotice("Use a text file up to 24 KB.");
                        return;
                      }
                      setContent(await file.text());
                    }
                  }}
                />
              </label>
              <label className="mt-4 block">
                Source text
                <textarea
                  className={field}
                  required
                  rows={8}
                  maxLength={24000}
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                />
              </label>
              <Button className="mt-4" disabled={mutation.isPending}>
                Save source
              </Button>
              <p className="mt-3 text-sm text-[var(--muted)]">
                Up to 20 active sources per workspace. Text only; PDF ingestion is not available
                yet.
              </p>
            </form>
          )}
          <div>
            {documents.data?.length === 0 && <p className={panel}>No approved sources yet.</p>}
            {documents.data?.map((doc) => (
              <article key={doc.id} className={`${panel} mb-4`}>
                <h2 className="text-lg font-semibold">{doc.title}</h2>
                <p className="my-2 text-sm">
                  {doc.status} · Vector index: {doc.index_status}
                </p>
                {doc.index_error && (
                  <p role="alert" className="text-sm text-[var(--muted)]">
                    Indexing failed: {doc.index_error}
                  </p>
                )}
                {manages && doc.status === "ACTIVE" && doc.index_status === "FAILED" && (
                  <Button
                    variant="outline"
                    disabled={mutation.isPending}
                    onClick={() =>
                      mutation.mutate({
                        path: `/knowledge/${doc.id}/reindex`,
                        method: "POST",
                      })
                    }
                  >
                    Retry indexing
                  </Button>
                )}
                <details>
                  <summary>Read source</summary>
                  <p className="mt-3 whitespace-pre-wrap text-sm">{doc.content}</p>
                </details>
                {manages && doc.status === "ACTIVE" && (
                  <Button
                    variant="outline"
                    className="mt-4"
                    disabled={mutation.isPending}
                    onClick={() => {
                      if (
                        window.confirm(
                          "Revoke this source? Pending approvals that cite it will be blocked.",
                        )
                      )
                        mutation.mutate({
                          path: `/knowledge/${doc.id}`,
                          method: "DELETE",
                        });
                    }}
                  >
                    Revoke source
                  </Button>
                )}
              </article>
            ))}
          </div>
        </div>
      )}
      {section === "runs" && (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            {writes && (
              <form
                className={panel}
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  mutation.mutate({
                    path: "/runs",
                    method: "POST",
                    body: {
                      agent_version_id: data.get("version"),
                      request_text: data.get("request"),
                      idempotency_key: intakeKey,
                    },
                  });
                }}
              >
                <h2 className="text-xl font-semibold">Start a task</h2>
                <label className="mt-4 block">
                  Teammate
                  <select
                    className={field}
                    required
                    value={agentId}
                    onChange={(e) => setAgentId(e.target.value)}
                  >
                    <option value="">Choose a teammate</option>
                    {agents.data
                      ?.filter((a) => a.lifecycle_status !== "ARCHIVED")
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                  </select>
                </label>
                <label className="mt-4 block">
                  Published version
                  <select key={agentId} className={field} required name="version">
                    <option value="">Choose a published version</option>
                    {versions.data?.map((v) => (
                      <option key={v.id} value={v.id}>
                        Version {v.version_number}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="mt-4 block">
                  Customer request
                  <textarea
                    className={field}
                    name="request"
                    required
                    minLength={10}
                    maxLength={4000}
                    rows={5}
                  />
                </label>
                <Button
                  className="mt-4"
                  disabled={
                    mutation.isPending ||
                    capabilities.data?.model_configured === false ||
                    capabilities.data?.worker_online === false
                  }
                >
                  Queue task
                </Button>
                <p className="mt-3 text-sm text-[var(--muted)]">
                  A configured worker processes queued tasks. Missing provider credentials or an
                  offline worker leave tasks queued.
                </p>
              </form>
            )}
            <section className={panel}>
              <h2 className="mb-4 text-xl font-semibold">Recent tasks</h2>
              {!runs.data?.length && <p>No tasks yet.</p>}
              {runs.data?.map((run) => (
                <button
                  type="button"
                  key={run.id}
                  className="mb-3 block w-full rounded-lg border border-[var(--border)] p-3 text-left"
                  onClick={() => setSelected(run.id)}
                >
                  <span className="block">{run.request_text.slice(0, 100)}</span>
                  <small>
                    {run.status} · {new Date(run.created_at).toLocaleString()}
                  </small>
                </button>
              ))}
            </section>
          </div>
          {current && (
            <article className={`${panel} mt-6`}>
              <h2 className="text-xl font-semibold">Task detail · {current.status}</h2>
              <p className="mt-3">{current.request_text}</p>
              {current.error_code && (
                <p role="alert" className="mt-3">
                  {current.error_code}
                </p>
              )}
              <TaskArtifact
                output={current.output}
                approved={current.status === "APPROVED"}
                runId={current.id}
              />
              <details className="mt-4">
                <summary>Usage and reservation</summary>
                <pre className="whitespace-pre-wrap text-xs">
                  {JSON.stringify(current.usage, null, 2)}
                </pre>
              </details>
              {manages && current.status === "AWAITING_REVIEW" && (
                <div className="mt-5 flex gap-3">
                  {(["APPROVE", "REJECT"] as const).map((decision) => (
                    <Button
                      key={decision}
                      disabled={mutation.isPending}
                      onClick={() =>
                        mutation.mutate({
                          path: `/runs/${current.id}/review`,
                          method: "POST",
                          body: {
                            expected_revision: current.revision,
                            artifact_hash: current.artifact_hash,
                            decision,
                          },
                        })
                      }
                    >
                      {decision === "APPROVE" ? "Approve draft" : "Reject draft"}
                    </Button>
                  ))}
                </div>
              )}
              {writes && current.status === "NEEDS_CLARIFICATION" && (
                <form
                  className="mt-5"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const facts = new FormData(e.currentTarget).get("facts");
                    mutation.mutate({
                      path: `/runs/${current.id}/clarify`,
                      method: "POST",
                      body: {
                        expected_revision: current.revision,
                        additional_facts: facts,
                      },
                    });
                  }}
                >
                  <label className="block">
                    Additional facts
                    <textarea
                      name="facts"
                      required
                      minLength={10}
                      maxLength={1000}
                      className={field}
                    />
                  </label>
                  <Button className="mt-3" disabled={mutation.isPending}>
                    Submit clarification
                  </Button>
                </form>
              )}
              {writes &&
                ["QUEUED", "RUNNING", "NEEDS_CLARIFICATION", "AWAITING_REVIEW"].includes(
                  current.status,
                ) && (
                  <Button
                    className="mt-4"
                    variant="outline"
                    disabled={mutation.isPending}
                    onClick={() =>
                      mutation.mutate({
                        path: `/runs/${current.id}/cancel`,
                        method: "POST",
                      })
                    }
                  >
                    Cancel task
                  </Button>
                )}
              {receipt.data && (
                <section className="mt-5 rounded-lg border border-[var(--accent)] p-4">
                  <h3 className="font-semibold">Review receipt</h3>
                  <p>No external message was sent.</p>
                  <p className="break-all text-sm">Receipt {receipt.data.id}</p>
                </section>
              )}
            </article>
          )}
          <CodeExecutionPanel
            key={`${organizationId}-${current?.id ?? "none"}`}
            organizationId={organizationId}
            initialCode={
              current?.status === "APPROVED" && typeof current.output.proposed_python === "string"
                ? current.output.proposed_python
                : ""
            }
            runId={current?.status === "APPROVED" ? current.id : undefined}
            manages={manages}
            writes={writes}
          />
        </>
      )}
      {section === "audit" && audits.data && <AuditTrail events={audits.data} />}
    </section>
  );
}
