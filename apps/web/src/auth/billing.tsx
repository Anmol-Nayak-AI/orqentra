import { useQuery } from "@tanstack/react-query";
import type { components } from "@orqentra/contracts";
import { useSessionApi } from "./client";
import { Button } from "../components/ui/button";
import { BillingTools } from "./billing-tools";

type Billing = components["schemas"]["BillingStatus"];
export function OrganizationBilling({ organizationId }: { organizationId: string }) {
  const { api, userId } = useSessionApi();
  const query = useQuery({
    queryKey: ["billing", userId, organizationId],
    queryFn: ({ signal }) => api<Billing>(`/organizations/${organizationId}/billing`, { signal }),
  });
  return (
    <section
      className="mb-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6"
      aria-label="Plans and quotas"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Plans and quotas</h2>
        <Button variant="outline" disabled={query.isFetching} onClick={() => void query.refetch()}>
          Refresh quotas
        </Button>
      </div>
      {query.isPending ? (
        <p role="status" className="mt-4">
          Loading quota policy…
        </p>
      ) : query.isError ? (
        <p role="alert" className="mt-4">
          Quota information could not load. Refresh to retry.
        </p>
      ) : (
        <>
          <p className="mt-3 text-sm text-[var(--muted)]">
            {query.data.mode === "disabled" ? "Payments disabled" : "Test integration only"} ·
            Subscription: {query.data.subscription_status.toLowerCase()}
          </p>
          <p className="mt-2 text-sm">
            Policy: {query.data.plan_key ?? "Unavailable"}.{" "}
            {query.data.entitlements_available
              ? "Intake allowances are available."
              : "AI intake is unavailable under the current policy."}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {Object.entries(query.data.quotas).map(([metric, quota]) => (
              <div key={metric} className="rounded-lg border border-[var(--border)] p-4">
                <h3 className="font-semibold">
                  {metric === "chat_turns"
                    ? "Chat turns"
                    : metric === "sandbox_runs"
                      ? "Sandbox runs"
                      : "Task runs"}{" "}
                  · UTC day
                </h3>
                <p className="mt-2">
                  {quota.used} used / {quota.limit} allowed · {quota.remaining} remaining
                </p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-sm text-[var(--muted)]">{query.data.notice}</p>
          <BillingTools organizationId={organizationId} status={query.data} />
        </>
      )}
    </section>
  );
}
