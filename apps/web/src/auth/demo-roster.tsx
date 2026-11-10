import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { useSessionApi } from "./client";
import type { components } from "@orqentra/contracts";

type DemoMember = components["schemas"]["DemoMemberResponse"];
export function DemoRoster({ organizationId }: { organizationId: string }) {
  const { api, userId } = useSessionApi();
  const roster = useQuery({
    queryKey: ["demo-members", userId, organizationId],
    queryFn: ({ signal }) =>
      api<DemoMember[]>(`/organizations/${organizationId}/demo-members`, { signal }),
  });
  if (roster.isError)
    return (
      <p role="alert" className="my-5">
        Demo roster could not load.
      </p>
    );
  if (!roster.data?.length) return null;
  return (
    <section
      className="my-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6"
      aria-label="Fictional demo team"
    >
      <div className="mb-5 flex items-start gap-3">
        <Users size={22} />
        <div>
          <h2 className="text-xl font-semibold">
            Demo team{" "}
            <span className="text-sm text-[var(--muted)]">· {roster.data.length} profiles</span>
          </h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Fictional sample people for exploring the interface. They have no sign-in credentials,
            real membership, or permissions.
          </p>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {roster.data.map((member) => (
          <article key={member.id} className="rounded-xl border border-[var(--border)] p-4">
            <div className="mb-3 flex items-center gap-3">
              <span
                aria-hidden="true"
                className="grid size-10 shrink-0 place-items-center rounded-full bg-[var(--hover)] text-sm font-semibold"
              >
                {member.display_name
                  .split(" ")
                  .map((part) => part[0])
                  .slice(0, 2)
                  .join("")}
              </span>
              <div className="min-w-0">
                <h3 className="font-semibold">{member.display_name}</h3>
                <p className="text-xs text-[var(--muted)]">{member.job_title}</p>
              </div>
            </div>
            <p className="break-all text-xs text-[var(--muted)]">{member.email}</p>
            <span className="mt-3 inline-block rounded-full border border-[var(--border)] px-2 py-1 text-xs">
              Demo · {member.demo_role}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}
