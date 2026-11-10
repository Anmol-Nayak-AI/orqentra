import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useSessionApi } from "./client";
import { Button } from "../components/ui/button";

type Invitation = { id: string; role: string; status: string; expires_at: string };
export function InvitationManager({ organizationId }: { organizationId: string }) {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const [link, setLink] = useState("");
  const [notice, setNotice] = useState("");
  const base = `/organizations/${organizationId}/invitations`;
  const invitations = useQuery({
    queryKey: ["invitations", userId, organizationId],
    queryFn: ({ signal }) => api<Invitation[]>(base, { signal }),
  });
  const create = useMutation({
    mutationFn: (role: string) =>
      api<Invitation & { token: string }>(base, { method: "POST", body: JSON.stringify({ role }) }),
    onSuccess: (result) => {
      setLink(`${window.location.origin}/app/join#${result.token}`);
      void cache.invalidateQueries({ queryKey: ["invitations", userId, organizationId] });
    },
    onError: () => setNotice("Invitation could not be created."),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`${base}/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setLink("");
      void cache.invalidateQueries({ queryKey: ["invitations", userId, organizationId] });
    },
    onError: () => setNotice("Invitation could not be revoked."),
  });
  return (
    <section className="mb-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
      <h2 className="text-xl font-semibold">Invite a teammate</h2>
      <p className="mt-2 text-sm text-[var(--muted)]">
        Create a single-use link valid for 48 hours. Share it privately with the intended person.
        They must sign in, then open the link. No email is sent automatically.
      </p>
      <form
        className="mt-4 flex flex-wrap gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          const role = new FormData(e.currentTarget).get("role");
          create.mutate(String(role));
        }}
      >
        <label>
          Role{" "}
          <select
            name="role"
            className="rounded border border-[var(--border)] bg-[var(--background)] p-2"
          >
            <option value="MEMBER">Member</option>
            <option value="VIEWER">Viewer</option>
          </select>
        </label>
        <Button disabled={create.isPending}>Create invite link</Button>
      </form>
      {link && (
        <div className="mt-4">
          <label className="block">
            Private invitation link
            <input
              readOnly
              className="mt-2 w-full rounded border border-[var(--border)] bg-[var(--background)] p-3 text-sm"
              value={link}
            />
          </label>
          <Button
            variant="outline"
            className="mt-2"
            onClick={() => {
              setLink("");
            }}
          >
            Hide link
          </Button>
        </div>
      )}
      {notice && <p role="alert">{notice}</p>}
      {invitations.isError && <p role="alert">Invitations could not load.</p>}
      {invitations.data?.map((invite) => (
        <div
          key={invite.id}
          className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] pt-3"
        >
          <span>
            {invite.role} · {invite.status} · expires {new Date(invite.expires_at).toLocaleString()}
          </span>
          {invite.status === "PENDING" && (
            <Button
              variant="outline"
              disabled={revoke.isPending}
              onClick={() => revoke.mutate(invite.id)}
            >
              Revoke invite
            </Button>
          )}
        </div>
      ))}
    </section>
  );
}
export function AcceptInvitation() {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const navigate = useNavigate();
  const [token] = useState(() => window.location.hash.slice(1));
  useEffect(() => {
    window.history.replaceState(null, "", window.location.pathname);
  }, []);
  const accept = useMutation({
    mutationFn: () =>
      api<{ organization_id: string }>("/invitations/accept", {
        method: "POST",
        body: JSON.stringify({ token }),
      }),
    onSuccess: (result) => {
      void cache.invalidateQueries({ queryKey: ["organizations", userId] });
      navigate(`/app/organizations/${result.organization_id}`, { replace: true });
    },
  });
  return (
    <section className="mx-auto max-w-xl rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8">
      <h1 className="text-2xl font-semibold">Join your organization</h1>
      <p className="my-4">
        Accept this invitation only if you trust the person who shared it. Your signed-in account
        will receive the role selected by the inviter.
      </p>
      {token ? (
        <Button disabled={accept.isPending} onClick={() => accept.mutate()}>
          Accept invitation
        </Button>
      ) : (
        <p>Sign in first, then open the full private invitation link again.</p>
      )}
      {accept.isError && (
        <p role="alert" className="mt-4">
          Invitation is unavailable, expired, already used, or your membership already exists.
        </p>
      )}
    </section>
  );
}
