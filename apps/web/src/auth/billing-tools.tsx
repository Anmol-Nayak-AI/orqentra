import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "@orqentra/contracts";
import { Button } from "../components/ui/button";
import { ApiError } from "../lib/api";
import { useSessionApi } from "./client";

type Catalog = components["schemas"]["CatalogView"];
type Operation = components["schemas"]["OperationResponse"];
type Invoices = components["schemas"]["InvoiceCollection"];
type Status = components["schemas"]["BillingStatus"];
type History = components["schemas"]["SubscriptionHistory"];
const field =
  "mt-2 block w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3";
export function money(amount: number | null, currency: string | null): string {
  if (amount === null || !currency) return "Not issued";
  const format = new Intl.NumberFormat(undefined, { style: "currency", currency });
  return format.format(amount / 10 ** (format.resolvedOptions().maximumFractionDigits ?? 2));
}
function safeLink(value: string | null): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === "https:" &&
      ["rzp.io", "razorpay.com", "checkout.razorpay.com"].includes(url.hostname) &&
      !url.username &&
      !url.password &&
      !url.hash &&
      (!url.port || url.port === "443")
      ? value
      : undefined;
  } catch {
    return undefined;
  }
}
export function BillingTools({
  organizationId,
  status,
}: {
  organizationId: string;
  status: Status;
}) {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const base = `/organizations/${organizationId}/billing`;
  const [notice, setNotice] = useState("");
  const [planKey, setPlan] = useState("");
  const [checkoutKey, setCheckoutKey] = useState(() => crypto.randomUUID());
  const [cancelKey] = useState(() => crypto.randomUUID());
  const [offset, setOffset] = useState<number | null>(null);
  const catalog = useQuery({
    queryKey: ["billing-catalog", userId, organizationId],
    queryFn: ({ signal }) => api<Catalog>(`${base}/catalog`, { signal }),
  });
  const operations = useQuery({
    queryKey: ["billing-operations", userId, organizationId],
    queryFn: ({ signal }) => api<Operation[]>(`${base}/operations`, { signal }),
    refetchInterval: 15000,
  });
  const invoices = useQuery({
    queryKey: ["billing-invoices", userId, organizationId],
    queryFn: ({ signal }) => api<Invoices>(`${base}/invoices`, { signal }),
  });
  const history = useQuery({
    queryKey: ["billing-history", userId, organizationId],
    queryFn: ({ signal }) => api<History[]>(`${base}/history`, { signal }),
  });
  const refresh = () => {
    for (const key of [
      "billing",
      "billing-catalog",
      "billing-operations",
      "billing-invoices",
      "billing-history",
    ])
      void cache.invalidateQueries({ queryKey: [key, userId, organizationId] });
  };
  const mutation = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) =>
      api<unknown>(base + path, {
        method: "POST",
        ...(body ? { body: JSON.stringify(body) } : {}),
      }),
    onSuccess: (data, variables) => {
      let message = "Provider information refreshed. Access follows verified subscription state.";
      if (variables.path === "/checkout") {
        const operation = data as Operation;
        message =
          operation.status === "READY"
            ? "Test authorization link prepared. Opening or returning from it does not establish payment success; reconcile afterward."
            : "The checkout result is not confirmed. Review the operation below before attempting another request.";
        if (operation.status === "READY" || operation.status === "FAILED")
          setCheckoutKey(crypto.randomUUID());
      } else if (variables.path === "/cancel")
        message =
          "Cancellation request recorded. Active access continues until the provider confirms the end of the period. Review any uncertain result below.";
      else if (variables.path === "/test-subscription")
        message =
          "Existing test subscription linked as pending. Reconcile to verify its current provider state.";
      if (variables.path.startsWith("/invoices/sync")) {
        const page = data as Invoices;
        setOffset(page.next_offset ?? null);
        message = `Stored ${page.invoices.length} provider test invoice snapshots.${page.next_offset !== null ? " More provider pages may be available." : " End of this provider page range."}`;
      }
      setNotice(message);
      refresh();
    },
    onError: (error) => {
      setNotice(
        error instanceof ApiError && error.status === 503
          ? "Billing provider or test actions are unavailable. No success is assumed. Refresh before retrying."
          : error instanceof ApiError && error.status === 409
            ? "The quote, subscription, access, or operation changed. Refresh and review the existing operation before proceeding."
            : "The billing request could not be confirmed. Review operation history before retrying.",
      );
      refresh();
    },
  });
  const selected = catalog.data?.plans.find((p) => p.key === planKey);
  const blocked = operations.data?.some(
    (op) => op.kind === "CHECKOUT" && ["CREATING", "UNKNOWN"].includes(op.status),
  );
  const canCheckout =
    !!catalog.data?.checkout_enabled &&
    !!selected &&
    operations.isSuccess &&
    !blocked &&
    ["UNAVAILABLE", "EXPIRED", "CANCELLED"].includes(status.subscription_status);
  const canReadProvider = catalog.data?.mode === "test" && !!status.external_id;
  return (
    <section
      className="mt-6 border-t border-[var(--border)] pt-5"
      aria-label="Subscription management"
    >
      <h3 className="text-lg font-semibold">Subscription management · test mode only</h3>
      <p className="mt-2 text-sm text-[var(--muted)]">
        Live payments are disabled. A checkout link is an authorization step; entitlement requires
        verified provider state. Invoice snapshots below are test records.
      </p>
      {notice && (
        <p className="mt-3" role="status">
          {notice}
        </p>
      )}
      <div className="my-4 flex flex-wrap gap-3">
        <Button
          variant="outline"
          disabled={mutation.isPending || !canReadProvider}
          onClick={() => mutation.mutate({ path: "/reconcile" })}
        >
          Reconcile provider state
        </Button>
        <Button variant="outline" onClick={refresh}>
          Refresh billing details
        </Button>
      </div>
      {status.period_end && (
        <p className="mb-3 text-sm">
          Verified period end: {new Date(status.period_end).toLocaleString()}
        </p>
      )}
      {catalog.isError ? (
        <p role="alert">Plan catalog could not load. Refresh billing details to retry.</p>
      ) : catalog.isPending ? (
        <p>Loading configured plans…</p>
      ) : (
        <>
          <p className="text-sm">{catalog.data.notice}</p>
          {catalog.data.plans.length ? (
            <div className="mt-4">
              <label>
                Configured test plan
                <select
                  className={field}
                  value={planKey}
                  onChange={(event) => {
                    setPlan(event.target.value);
                    setCheckoutKey(crypto.randomUUID());
                  }}
                >
                  <option value="">Choose a plan</option>
                  {catalog.data.plans.map((plan) => (
                    <option key={plan.key} value={plan.key}>
                      {plan.key} · {money(plan.amount_minor, plan.currency)} / {plan.interval}{" "}
                      {plan.period}
                    </option>
                  ))}
                </select>
              </label>
              {selected && (
                <p className="mt-2 text-sm">
                  Configured test amount: {money(selected.amount_minor, selected.currency)} per{" "}
                  {selected.interval} {selected.period}; {catalog.data.total_cycles} billing cycles.
                  Daily quotas:{" "}
                  {Object.entries(selected.quotas)
                    .map(([name, value]) => `${name.replaceAll("_", " ")}: ${value}`)
                    .join(" · ")}
                  . No real charge is enabled.
                </p>
              )}
              <Button
                className="mt-3"
                disabled={mutation.isPending || !canCheckout}
                onClick={() => {
                  if (selected)
                    mutation.mutate({
                      path: "/checkout",
                      body: {
                        plan_key: selected.key,
                        quote_hash: selected.quote_hash,
                        idempotency_key: checkoutKey,
                      },
                    });
                }}
              >
                Prepare test checkout
              </Button>
              <details className="mt-4">
                <summary>Link an existing test subscription</summary>
                <form
                  className="mt-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    mutation.mutate({
                      path: "/test-subscription",
                      body: {
                        external_id: new FormData(event.currentTarget).get("external_id"),
                        plan_key: planKey,
                      },
                    });
                  }}
                >
                  <label>
                    Provider subscription reference
                    <input
                      name="external_id"
                      required
                      pattern="sub_[A-Za-z0-9]+"
                      className={field}
                    />
                  </label>
                  <Button className="mt-3" disabled={!selected || mutation.isPending}>
                    Verify and link test subscription
                  </Button>
                </form>
              </details>
            </div>
          ) : (
            <p className="mt-3 text-sm">
              No verified test plans configured. An operator must configure a Razorpay test
              application and plan mapping.
            </p>
          )}
        </>
      )}
      {status.external_id && (
        <Button
          className="mt-4"
          variant="outline"
          disabled={
            !status.actions_enabled ||
            mutation.isPending ||
            !["ACTIVE", "PENDING", "PAST_DUE"].includes(status.subscription_status)
          }
          onClick={() => {
            if (
              window.confirm(
                "Request cancellation of this TEST subscription at the end of its period? Access follows verified provider state.",
              )
            )
              mutation.mutate({ path: "/cancel", body: { idempotency_key: cancelKey } });
          }}
        >
          Request cancellation at period end
        </Button>
      )}
      <section className="mt-6">
        <h4 className="font-semibold">Recent provider operations</h4>
        {operations.isError ? (
          <p role="alert">Operation history could not load.</p>
        ) : operations.isPending ? (
          <p>Loading operations…</p>
        ) : !operations.data.length ? (
          <p className="mt-2 text-sm">No provider operations recorded.</p>
        ) : (
          operations.data.map((op) => (
            <article key={op.id} className="mt-3 rounded-lg border border-[var(--border)] p-3">
              <p className="font-medium">
                {op.kind === "CHECKOUT" ? "Test checkout" : "Period-end cancellation"} · {op.status}
              </p>
              <p className="mt-1 text-xs">
                {new Date(op.created_at).toLocaleString()} · {op.plan_key}
              </p>
              {op.error_code && <p className="mt-2 text-sm">Reference: {op.error_code}</p>}
              {op.status === "READY" && op.kind === "CHECKOUT" && safeLink(op.hosted_url) && (
                <a
                  className="mt-3 inline-block underline"
                  href={safeLink(op.hosted_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open provider test authorization
                </a>
              )}
              {["UNKNOWN", "CREATING"].includes(op.status) && (
                <>
                  <p className="mt-2 text-sm">
                    The result is not confirmed. No new provider request will be issued
                    automatically. Find the matching subscription in the provider dashboard before
                    resolving it. An uncertain cancellation can be confirmed only after the provider
                    reports it ended.
                  </p>
                  <form
                    className="mt-3"
                    onSubmit={(event) => {
                      event.preventDefault();
                      mutation.mutate({
                        path: `/operations/${op.id}/resolve`,
                        body: { external_id: new FormData(event.currentTarget).get("reference") },
                      });
                    }}
                  >
                    <label>
                      Matching provider reference
                      <input
                        className={field}
                        name="reference"
                        required
                        pattern="sub_[A-Za-z0-9]+"
                        defaultValue={op.external_id ?? ""}
                      />
                    </label>
                    <Button className="mt-3" variant="outline" disabled={mutation.isPending}>
                      Resolve by verified provider lookup
                    </Button>
                  </form>
                </>
              )}
            </article>
          ))
        )}
      </section>
      <section className="mt-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h4 className="font-semibold">Verified test invoice snapshots</h4>
          <Button
            variant="outline"
            disabled={!canReadProvider || mutation.isPending}
            onClick={() => mutation.mutate({ path: `/invoices/sync?offset=${offset ?? 0}` })}
          >
            {offset !== null ? "Sync next invoice page" : "Sync provider invoices"}
          </Button>
        </div>
        {invoices.isError ? (
          <p role="alert">Invoice history could not load.</p>
        ) : invoices.isPending ? (
          <p>Loading invoice snapshots…</p>
        ) : (
          <>
            <p className="mt-2 text-sm text-[var(--muted)]">{invoices.data.notice}</p>
            {!invoices.data.invoices.length ? (
              <p className="mt-2 text-sm">No verified invoices stored.</p>
            ) : (
              invoices.data.invoices.map((invoice) => (
                <article
                  key={invoice.external_id}
                  className="mt-3 rounded-lg border border-[var(--border)] p-3"
                >
                  <p className="font-medium">
                    {invoice.external_id} · {invoice.status}
                  </p>
                  <p className="mt-2 text-sm">
                    Total {money(invoice.amount_minor, invoice.currency)} · Paid{" "}
                    {money(invoice.paid_minor, invoice.currency)} · Due{" "}
                    {money(invoice.due_minor, invoice.currency)}
                  </p>
                  {safeLink(invoice.hosted_url) && (
                    <a
                      className="mt-2 inline-block underline"
                      target="_blank"
                      rel="noopener noreferrer"
                      href={safeLink(invoice.hosted_url)}
                    >
                      View provider test invoice
                    </a>
                  )}
                </article>
              ))
            )}
          </>
        )}
      </section>
      <details className="mt-6">
        <summary>Subscription state history</summary>
        {history.isError ? (
          <p role="alert">Subscription history could not load.</p>
        ) : (
          history.data?.map((row) => (
            <p key={`${row.created_at}-${row.external_id}-${row.source}`} className="mt-2 text-sm">
              {new Date(row.created_at).toLocaleString()} · {row.status} · {row.plan_key} ·{" "}
              {row.source.replaceAll("_", " ")}
            </p>
          ))
        )}
      </details>
    </section>
  );
}
