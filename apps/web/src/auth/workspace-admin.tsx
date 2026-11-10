import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { WorkspaceResponse } from "@orqentra/contracts";
import { Button } from "../components/ui/button";
import { ApiError } from "../lib/api";
import { useSessionApi } from "./client";
const field =
  "mt-2 block w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3";
export function WorkspaceAdministration({ organizationId }: { organizationId: string }) {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const base = `/organizations/${organizationId}/workspaces`;
  const [notice, setNotice] = useState("");
  const workspaces = useQuery({
    queryKey: ["workspaces", userId, organizationId],
    queryFn: ({ signal }) => api<WorkspaceResponse[]>(base, { signal }),
  });
  const save = useMutation({
    mutationFn: ({
      workspace,
      name,
      slug,
    }: {
      workspace?: WorkspaceResponse;
      name: string;
      slug?: string;
    }) =>
      api(workspace ? `${base}/${workspace.id}` : base, {
        method: workspace ? "PATCH" : "POST",
        body: JSON.stringify(
          workspace ? { name, expected_updated_at: workspace.updated_at } : { name, slug },
        ),
      }),
    onSuccess: () => {
      setNotice("Workspace saved. It is available in Knowledge, Teammates and Chat.");
      for (const key of ["workspaces", "administration"])
        void cache.invalidateQueries({ queryKey: [key, userId, organizationId] });
    },
    onError: (error) =>
      setNotice(
        error instanceof ApiError && error.status === 409
          ? "A workspace changed, the slug is already used, or the workspace limit was reached. Refresh before retrying."
          : "Workspace could not be saved. Check your access and input.",
      ),
  });
  return (
    <section
      className="mb-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6"
      aria-label="Workspace administration"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Workspaces</h2>
        <Button variant="outline" onClick={() => void workspaces.refetch()}>
          Refresh workspaces
        </Button>
      </div>
      <p className="mt-2 text-sm text-[var(--muted)]">
        Group knowledge, teammates and conversations. Workspaces share your organization’s
        membership permissions. Up to 20 workspaces per organization.
      </p>
      {notice && (
        <p className="mt-3" role="status">
          {notice}
        </p>
      )}
      <form
        className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          save.mutate({ name: String(data.get("name")), slug: String(data.get("slug")) });
        }}
      >
        <label>
          Workspace name
          <input className={field} name="name" required maxLength={200} />
        </label>
        <label>
          Workspace slug
          <input
            className={field}
            name="slug"
            required
            maxLength={100}
            pattern="[a-z0-9]+(-[a-z0-9]+)*"
          />
        </label>
        <Button disabled={save.isPending}>Create workspace</Button>
      </form>
      {workspaces.isPending ? (
        <p className="mt-4" role="status">
          Loading workspaces…
        </p>
      ) : workspaces.isError ? (
        <p className="mt-4" role="alert">
          Workspaces could not load. Use Refresh workspaces to retry.
        </p>
      ) : (
        <div className="mt-5 space-y-3">
          {workspaces.data.map((workspace) => (
            <form
              key={workspace.id}
              className="flex flex-wrap items-end gap-3 rounded-lg border border-[var(--border)] p-4"
              onSubmit={(event) => {
                event.preventDefault();
                save.mutate({
                  workspace,
                  name: String(new FormData(event.currentTarget).get("name")),
                });
              }}
            >
              <label className="min-w-0 flex-1">
                Name for {workspace.slug}
                <input
                  className={field}
                  name="name"
                  required
                  maxLength={200}
                  defaultValue={workspace.name}
                />
              </label>
              <Button variant="outline" disabled={save.isPending}>
                Save workspace name
              </Button>
            </form>
          ))}
        </div>
      )}
    </section>
  );
}
