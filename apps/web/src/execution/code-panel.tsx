import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "@orqentra/contracts";
import { useSessionApi } from "../auth/client";
import { Button } from "../components/ui/button";
import { ApiError } from "../lib/api";

type CodeJob = components["schemas"]["CodeResult"];
const panel = "mt-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6";
const field =
  "mt-2 block w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3";
export function CodeExecutionPanel({
  organizationId,
  runId,
  initialCode = "",
  manages,
  writes,
}: {
  organizationId: string;
  runId?: string;
  initialCode?: string;
  manages: boolean;
  writes: boolean;
}) {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const base = `/organizations/${organizationId}`;
  const [notice, setNotice] = useState("");
  const [key, setKey] = useState(() => crypto.randomUUID());
  const jobs = useQuery({
    queryKey: ["code-executions", userId, organizationId],
    queryFn: ({ signal }) => api<CodeJob[]>(`${base}/code-executions`, { signal }),
    refetchInterval: 5000,
  });
  const me = useQuery({
    queryKey: ["me", userId],
    queryFn: ({ signal }) => api<{ id: string }>("/me", { signal }),
  });
  const capability = useQuery({
    queryKey: ["capabilities", userId, organizationId],
    queryFn: ({ signal }) =>
      api<components["schemas"]["ExecutionCapabilities"]>(`${base}/capabilities`, { signal }),
    refetchInterval: 15000,
  });
  const available = capability.data?.sandbox_execution_available === true;
  const mutation = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) =>
      api(`${base}/code-executions${path}`, {
        method: "POST",
        ...(body ? { body: JSON.stringify(body) } : {}),
      }),
    onSuccess: (_, variables) => {
      setNotice(
        variables.path.endsWith("/start")
          ? "Execution queued for the isolated worker."
          : "Saved. Review and execution are separate steps.",
      );
      if (!variables.path) setKey(crypto.randomUUID());
      void cache.invalidateQueries({ queryKey: ["code-executions", userId, organizationId] });
      void cache.invalidateQueries({ queryKey: ["billing", userId, organizationId] });
    },
    onError: (error) =>
      setNotice(
        error instanceof ApiError && error.status === 503
          ? "The isolated worker is unavailable. Your approved code has not been queued."
          : error instanceof ApiError && error.status === 409
            ? "This approval or revision is no longer current. Refresh the request before proceeding."
            : "The action was denied or could not be saved. Check your access and try again.",
      ),
  });
  return (
    <section className={panel} aria-label="Isolated code execution">
      <h2 className="text-xl font-semibold">Code review and isolated execution</h2>
      <p className="mt-2 text-sm text-[var(--muted)]">
        Prepare a Python analysis for an approved task. A different administrator must review its
        exact code before a separate execution request. Code is never run in the web or API server.
      </p>
      <p className="mt-3 text-sm" role="status">
        {available
          ? "Isolated worker available"
          : "Isolated execution unavailable. Proposals and reviews can be saved; execution requires an enabled E2B worker."}
      </p>
      {notice && (
        <p className="mt-3" role="status">
          {notice}
        </p>
      )}
      {writes && runId ? (
        <form
          className="mt-5"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            mutation.mutate({
              path: "",
              body: {
                run_id: runId,
                title: data.get("title"),
                code: data.get("code"),
                idempotency_key: key,
              },
            });
          }}
        >
          <label className="block">
            Analysis title
            <input
              name="title"
              required
              maxLength={200}
              className={field}
              onChange={() => setKey(crypto.randomUUID())}
            />
          </label>
          <label className="mt-3 block">
            Python code
            <textarea
              name="code"
              defaultValue={initialCode}
              required
              maxLength={16384}
              rows={8}
              spellCheck={false}
              className={`${field} font-mono text-sm`}
              onChange={() => setKey(crypto.randomUUID())}
            />
          </label>
          <p className="my-3 text-sm text-[var(--muted)]">
            Python only, up to 16 KB UTF-8. Execution denies network access and uses a fresh,
            bounded sandbox. Do not paste credentials.
          </p>
          <Button disabled={mutation.isPending}>Submit code for independent review</Button>
        </form>
      ) : (
        writes && (
          <p className="mt-4 text-sm">Select an approved task above to prepare a code proposal.</p>
        )
      )}
      {jobs.isPending ? (
        <p className="mt-4">Loading code requests…</p>
      ) : jobs.isError ? (
        <div role="alert" className="mt-4">
          Code requests could not load.{" "}
          <Button variant="outline" onClick={() => void jobs.refetch()}>
            Retry
          </Button>
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          {jobs.data.length === 0 && <p>No code proposals yet.</p>}
          {jobs.data.map((job) => (
            <article key={job.id} className="rounded-lg border border-[var(--border)] p-4">
              <h3 className="font-semibold">{job.title}</h3>
              <p className="my-2 text-sm">
                {job.status.replaceAll("_", " ")} · Revision {job.revision}
              </p>
              <details>
                <summary>Review exact Python code</summary>
                <pre className="mt-3 overflow-auto whitespace-pre-wrap text-sm">{job.code}</pre>
                <p className="mt-3 break-all text-xs">SHA-256: {job.code_hash}</p>
              </details>
              {job.status === "AWAITING_REVIEW" &&
                (manages && me.data?.id !== job.created_by ? (
                  <div className="mt-3 flex flex-wrap gap-3">
                    {(["APPROVE", "REJECT"] as const).map((decision) => (
                      <Button
                        key={decision}
                        disabled={mutation.isPending || !me.data}
                        variant={decision === "REJECT" ? "outline" : "default"}
                        onClick={() =>
                          mutation.mutate({
                            path: `/${job.id}/review`,
                            body: {
                              expected_revision: job.revision,
                              code_hash: job.code_hash,
                              decision,
                            },
                          })
                        }
                      >
                        {decision === "APPROVE" ? "Approve this code" : "Reject code"}
                      </Button>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm">
                    A different administrator must review this proposal.
                  </p>
                ))}
              {job.status === "APPROVED" && (
                <div className="mt-3">
                  <p className="mb-3 text-sm">
                    Approval expires{" "}
                    {job.approval_expires_at
                      ? new Date(job.approval_expires_at).toLocaleString()
                      : "—"}
                    .
                  </p>
                  {writes && (
                    <Button
                      disabled={
                        !available ||
                        mutation.isPending ||
                        !job.approval_expires_at ||
                        Date.parse(job.approval_expires_at) <= Date.now()
                      }
                      onClick={() =>
                        mutation.mutate({
                          path: `/${job.id}/start`,
                          body: { expected_revision: job.revision, code_hash: job.code_hash },
                        })
                      }
                    >
                      Run in isolated sandbox
                    </Button>
                  )}
                </div>
              )}
              {job.status === "COMPLETED" && (
                <section className="mt-4">
                  <h4 className="font-semibold">Execution output</h4>
                  <pre className="mt-2 overflow-auto whitespace-pre-wrap text-sm">
                    {job.output || "Execution completed with no text output."}
                  </pre>
                </section>
              )}
              {job.status === "UNKNOWN" && (
                <p className="mt-3" role="alert">
                  Execution could not be confirmed. It will not retry automatically because remote
                  code may already have run. An administrator must investigate before creating a new
                  request.
                </p>
              )}
              {job.error_code && <p className="mt-2 text-sm">Reference: {job.error_code}</p>}
              {writes && ["AWAITING_REVIEW", "APPROVED", "QUEUED"].includes(job.status) && (
                <Button
                  className="mt-3"
                  variant="outline"
                  disabled={mutation.isPending}
                  onClick={() => mutation.mutate({ path: `/${job.id}/cancel` })}
                >
                  Cancel code request
                </Button>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
