import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import type { components } from "@orqentra/contracts";
import type { OrganizationResponse, WorkspaceResponse } from "@orqentra/contracts";
import { useSessionApi } from "../auth/client";
import { ApiError } from "../lib/api";
import { Button } from "../components/ui/button";

type Agent = components["schemas"]["AgentResponse"];
type Version = components["schemas"]["AgentVersionResponse"];
type Configuration = components["schemas"]["TeammateConfiguration"];
const panel = "rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6";
const field = "mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3";

export function TeammatesPage() {
  const { organizationId = "" } = useParams();
  return <Teammates key={organizationId} organizationId={organizationId} />;
}
function Teammates({ organizationId }: { organizationId: string }) {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const base = `/organizations/${organizationId}`;
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState("");
  const agents = useQuery({
    queryKey: ["agents", userId, organizationId],
    queryFn: ({ signal }) => api<Agent[]>(`${base}/agents`, { signal }),
  });
  const organization = useQuery({
    queryKey: ["organization", userId, organizationId],
    queryFn: ({ signal }) => api<OrganizationResponse>(base, { signal }),
  });
  const workspaces = useQuery({
    queryKey: ["workspaces", userId, organizationId],
    queryFn: ({ signal }) => api<WorkspaceResponse[]>(`${base}/workspaces`, { signal }),
  });
  const versions = useQuery({
    queryKey: ["agent-versions", userId, organizationId, selected],
    queryFn: ({ signal }) => api<Version[]>(`${base}/agents/${selected}/versions`, { signal }),
    enabled: !!selected,
  });
  const current = agents.data?.find((agent) => agent.id === selected);
  const canEdit = organization.data?.role !== "VIEWER";
  const canPublish = organization.data?.role === "OWNER" || organization.data?.role === "ADMIN";
  const mutation = useMutation({
    mutationFn: ({ path, method, body }: { path: string; method: string; body: unknown }) =>
      api<Agent | Version>(`${base}/agents${path}`, { method, body: JSON.stringify(body) }),
    onSuccess: (_, variables) => {
      setNotice(
        variables.path.endsWith("/publish")
          ? "Version published. Published versions are immutable."
          : variables.path.endsWith("/archive")
            ? "Teammate archived. Version history is preserved."
            : "Draft saved.",
      );
      setCreating(false);
      void cache.invalidateQueries({ queryKey: ["agents", userId, organizationId] });
      void cache.invalidateQueries({ queryKey: ["agent-versions", userId, organizationId] });
    },
    onError: (error) =>
      setNotice(
        error instanceof ApiError && error.status === 409
          ? "This draft changed in another session. Refresh and review the latest revision before saving."
          : "The change failed. Check your permissions and configuration, then retry.",
      ),
  });
  if (agents.isPending || organization.isPending || workspaces.isPending)
    return <p role="status">Loading teammates…</p>;
  if (agents.isError || organization.isError || workspaces.isError)
    return (
      <section role="alert">
        <h1>Teammates could not load</h1>
        <Button
          onClick={() => {
            void agents.refetch();
            void organization.refetch();
            void workspaces.refetch();
          }}
        >
          Retry
        </Button>
      </section>
    );
  return (
    <section>
      <div className="workspace-page-heading">
        <div>
          <p className="workspace-eyebrow">TEAMMATE FORGE</p>
          <h1>Your AI teammates</h1>
          <p>Define a specialist, set its boundaries, and publish a version.</p>
        </div>
        {canEdit && (
          <Button
            disabled={mutation.isPending}
            onClick={() => {
              setCreating(true);
              setSelected(null);
              setNotice("");
            }}
          >
            Create teammate
          </Button>
        )}
      </div>
      <p className="mb-6 text-sm text-[var(--muted)]">
        Published configurations are ready for the execution integration. Publishing does not run a
        model or send messages.
      </p>
      {notice && (
        <p role="status" className={`${panel} mb-5`}>
          {notice}
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <section className={panel} aria-label="Teammate list">
          <h2 className="mb-4 text-lg font-semibold">Teammates</h2>
          {!agents.data.length && <p>No teammates yet. Create your first specialist.</p>}
          {agents.data.map((agent) => (
            <button
              type="button"
              key={agent.id}
              className={`mb-3 block w-full rounded-lg border p-3 text-left ${selected === agent.id ? "border-[var(--accent)]" : "border-[var(--border)]"}`}
              onClick={() => {
                setSelected(agent.id);
                setCreating(false);
                setNotice("");
              }}
            >
              <strong className="block">{agent.name}</strong>
              <span className="text-xs text-[var(--muted)]">
                {agent.lifecycle_status} · revision {agent.revision}
              </span>
            </button>
          ))}
          {agents.data.length === 50 && <p className="text-sm">Showing the first 50 teammates.</p>}
        </section>
        <div>
          {creating ? (
            <AgentEditor
              key="new"
              workspaces={workspaces.data}
              pending={mutation.isPending}
              onSave={(body) => mutation.mutate({ path: "", method: "POST", body })}
              onCancel={() => setCreating(false)}
            />
          ) : current ? (
            <>
              <AgentEditor
                key={`${current.id}-${current.revision}`}
                agent={current}
                workspaces={workspaces.data}
                pending={mutation.isPending}
                readOnly={!canEdit || current.lifecycle_status === "ARCHIVED"}
                onSave={(body) =>
                  mutation.mutate({ path: `/${current.id}`, method: "PATCH", body })
                }
                onCancel={() => setSelected(null)}
              />
              {canPublish && current.lifecycle_status !== "ARCHIVED" && (
                <div className="my-4 flex flex-wrap gap-3">
                  <Button
                    disabled={mutation.isPending}
                    onClick={() =>
                      mutation.mutate({
                        path: `/${current.id}/publish`,
                        method: "POST",
                        body: { expected_revision: current.revision },
                      })
                    }
                  >
                    Publish saved revision {current.revision}
                  </Button>
                  <Button
                    variant="outline"
                    disabled={mutation.isPending}
                    onClick={() => {
                      if (
                        window.confirm(
                          "Archive this teammate? Existing versions will be preserved.",
                        )
                      )
                        mutation.mutate({
                          path: `/${current.id}/archive`,
                          method: "POST",
                          body: { expected_revision: current.revision },
                        });
                    }}
                  >
                    Archive
                  </Button>
                </div>
              )}
              <section className={`${panel} mt-5`}>
                <h2 className="text-lg font-semibold">Version history</h2>
                {versions.isPending ? (
                  <p>Loading versions…</p>
                ) : versions.isError ? (
                  <p role="alert">Version history could not load.</p>
                ) : !versions.data?.length ? (
                  <p>No published versions yet.</p>
                ) : (
                  versions.data.map((version) => (
                    <details key={version.id} className="mt-4 border-t border-[var(--border)] pt-3">
                      <summary>
                        Version {version.version_number} ·{" "}
                        {new Date(version.published_at).toLocaleString()}
                      </summary>
                      <pre className="mt-3 overflow-auto whitespace-pre-wrap text-xs">
                        {JSON.stringify(version.configuration_snapshot, null, 2)}
                      </pre>
                    </details>
                  ))
                )}
              </section>
            </>
          ) : (
            <section className={panel}>
              <h2 className="text-xl font-semibold">Build a specialist for your team</h2>
              <p className="mt-3">
                Select a teammate to edit its instructions and review published versions.
              </p>
              <Link
                className="mt-4 inline-block underline"
                to={`/app/organizations/${organizationId}`}
              >
                Back to Command Center
              </Link>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}
function AgentEditor({
  agent,
  workspaces,
  pending,
  readOnly = false,
  onSave,
  onCancel,
}: {
  agent?: Agent;
  workspaces: WorkspaceResponse[];
  pending: boolean;
  readOnly?: boolean;
  onSave: (body: unknown) => void;
  onCancel: () => void;
}) {
  const initial = agent?.draft_configuration as Partial<Configuration> | undefined;
  const [instructions, setInstructions] = useState(
    initial?.instructions ??
      "Help onboarding teams prepare grounded plans. Use only approved sources and ask for missing information.",
  );
  const [model, setModel] = useState<Configuration["model"]>(
    initial?.model ?? "openai:gpt-4.1-mini",
  );
  const [workflow, setWorkflow] = useState<Configuration["workflow"]>(
    initial?.workflow ?? "onboarding.v1",
  );
  const [budget, setBudget] = useState(initial?.max_run_cost_cents ?? 300);
  return (
    <form
      className={panel}
      onSubmit={(event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const configuration: Configuration = {
          instructions,
          model,
          max_run_cost_cents: budget,
          max_model_calls: 3,
          workflow,
          output_schema:
            workflow === "python-analysis.v1" ? "python_analysis_plan.v1" : "onboarding_plan.v1",
          tools: ["knowledge.search", "draft.compose"],
        };
        onSave(
          agent
            ? { expected_revision: agent.revision, configuration }
            : {
                name: data.get("name"),
                slug: data.get("slug"),
                workspace_id: data.get("workspace"),
                configuration,
              },
        );
      }}
    >
      <h2 className="mb-5 text-xl font-semibold">{agent?.name ?? "New teammate"}</h2>
      <fieldset disabled={readOnly || pending} className="space-y-5">
        {!agent && (
          <>
            <label className="block">
              Name
              <input name="name" required maxLength={200} className={field} />
            </label>
            <label className="block">
              Slug
              <input
                name="slug"
                required
                pattern="[a-z0-9]+(-[a-z0-9]+)*"
                maxLength={100}
                className={field}
                placeholder="onboarding-specialist"
              />
            </label>
            <label className="block">
              Workspace
              <select name="workspace" required className={field}>
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
        <label className="block">
          Workflow
          <select
            className={field}
            value={workflow}
            onChange={(event) => {
              const next = event.target.value as Configuration["workflow"];
              setWorkflow(next);
              if (
                !agent &&
                instructions ===
                  "Help onboarding teams prepare grounded plans. Use only approved sources and ask for missing information." &&
                next === "python-analysis.v1"
              ) {
                setInstructions(
                  "Prepare source-backed Python analysis proposals. Use approved facts, print text results, avoid network calls and credentials, and ask for missing information. Never execute code.",
                );
              }
            }}
          >
            <option value="onboarding.v1">Grounded onboarding plan</option>
            <option value="python-analysis.v1">Python analysis proposal</option>
          </select>
        </label>
        <label className="block">
          Role instructions
          <textarea
            required
            minLength={20}
            maxLength={12000}
            rows={8}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            className={field}
          />
        </label>
        <label className="block">
          Model
          <select
            value={model}
            onChange={(e) => setModel(e.target.value as Configuration["model"])}
            className={field}
          >
            <option value="openai:gpt-4.1-mini">GPT-4.1 mini</option>
            <option value="openai:gpt-4.1">GPT-4.1</option>
          </select>
        </label>
        <label className="block">
          Maximum run budget (US cents)
          <input
            type="number"
            required
            min={1}
            max={1000}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            className={field}
          />
        </label>
        <p className="text-sm text-[var(--muted)]">
          Knowledge search and draft composition. Python proposals require separate, independent
          code approval before isolated execution. Publishing never executes code.
        </p>
        {!readOnly && <Button type="submit">{pending ? "Saving…" : "Save draft"}</Button>}
      </fieldset>
      <Button type="button" variant="outline" className="mt-4" onClick={onCancel}>
        Close editor
      </Button>
    </form>
  );
}
