import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components, MembershipResponse, OrganizationResponse } from "@orqentra/contracts";
import { useSessionApi } from "../auth/client";
import { Button } from "../components/ui/button";

type Conversation = components["schemas"]["ConversationResponse"];
type HumanMessage = components["schemas"]["HumanMessageResponse"];
export function SupportInbox({
  organizationId,
  onSelect,
  disabled = false,
}: {
  organizationId: string;
  onSelect: (chat: Conversation) => void;
  disabled?: boolean;
}) {
  const { api, userId } = useSessionApi();
  const base = `/organizations/${organizationId}`;
  const org = useQuery({
    queryKey: ["organization", userId, organizationId],
    queryFn: ({ signal }) => api<OrganizationResponse>(base, { signal }),
  });
  const manages = org.data?.role === "OWNER" || org.data?.role === "ADMIN";
  const queue = useQuery({
    queryKey: ["support-queue", userId, organizationId],
    queryFn: ({ signal }) => api<Conversation[]>(`${base}/support/chats`, { signal }),
    enabled: manages,
    refetchInterval: 3000,
  });
  if (!manages || !org.isSuccess) return null;
  return (
    <section className="mt-6 border-t border-[var(--border)] pt-4" aria-label="Human support inbox">
      <h2 className="font-semibold">Human support inbox</h2>
      <p className="mt-2 text-xs text-[var(--muted)]">
        Only conversations explicitly shared for help appear here. An OWNER or ADMIN must claim a
        request to reply.
      </p>
      {queue.isError && <p role="alert">Support requests could not load.</p>}
      {queue.data?.length === 0 && (
        <p className="mt-3 text-sm text-[var(--muted)]">No open requests.</p>
      )}
      {queue.isSuccess &&
        queue.data?.map((chat) => (
          <button
            key={chat.id}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(chat)}
            className="mt-3 w-full rounded-lg border border-[var(--border)] p-3 text-left text-sm"
          >
            <span className="block break-words">{chat.title}</span>
            <span className="text-xs text-[var(--muted)]">
              {chat.support_state === "WAITING" ? "Waiting for a person" : "Claimed by support"}
            </span>
          </button>
        ))}
    </section>
  );
}

export function HumanSupport({
  organizationId,
  chat,
  requester,
}: {
  organizationId: string;
  chat: Conversation;
  requester: boolean;
}) {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const [content, setContent] = useState("");
  const [key, setKey] = useState(() => crypto.randomUUID());
  const base = `/organizations/${organizationId}/chats/${chat.id}`;
  const own = useQuery({
    queryKey: ["membership", userId, organizationId],
    queryFn: ({ signal }) =>
      api<MembershipResponse>(`/organizations/${organizationId}/memberships/me`, { signal }),
  });
  const history = useQuery({
    queryKey: ["human-messages", userId, organizationId, chat.id],
    queryFn: ({ signal }) => api<HumanMessage[]>(`${base}/human-messages`, { signal }),
    refetchInterval: 3000,
  });
  const refresh = () => {
    for (const queryKey of [
      ["chat-state", userId, organizationId, chat.id],
      ["human-messages", userId, organizationId, chat.id],
      ["support-queue", userId, organizationId],
      ["chats", userId, organizationId],
      ["chat-messages", userId, organizationId, chat.id],
    ])
      void cache.invalidateQueries({ queryKey });
  };
  const action = useMutation({
    mutationFn: (path: string) => api(`${base}/${path}`, { method: "POST" }),
    onSuccess: () => {
      setConfirm(false);
      refresh();
    },
  });
  const send = useMutation({
    mutationFn: () =>
      api(`${base}/human-messages`, {
        method: "POST",
        body: JSON.stringify({ content, idempotency_key: key }),
      }),
    onSuccess: () => {
      setContent("");
      setKey(crypto.randomUUID());
      refresh();
    },
  });
  const active = chat.support_state !== "AI";
  const assigned = own.data?.user_id === chat.assigned_to;
  return (
    <section
      className="border-b border-[var(--border)] bg-[var(--background)] p-5"
      aria-label="Human support"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">
            {active ? "Human support · AI paused" : "Need a person?"}
          </h3>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {chat.support_state === "WAITING"
              ? "Waiting for an authorized teammate. No one has joined yet."
              : chat.support_state === "HUMAN"
                ? "This request has been claimed by a real support teammate."
                : "Request help when sources are insufficient or you want human review."}
          </p>
        </div>
        {!active && requester && (
          <Button variant="outline" onClick={() => setConfirm(true)}>
            Request human help
          </Button>
        )}
        {active && !requester && !chat.assigned_to && (
          <Button disabled={action.isPending} onClick={() => action.mutate("claim")}>
            Claim conversation
          </Button>
        )}
        {active && (requester || assigned) && (
          <Button
            variant="outline"
            disabled={action.isPending}
            onClick={() => action.mutate("resume")}
          >
            Return to AI
          </Button>
        )}
      </div>
      {confirm && (
        <div className="mt-4 rounded-lg border border-[var(--border)] p-4">
          <p className="mb-3 text-sm">
            This shares this conversation and its history with your organization’s OWNER/ADMIN
            support team and pauses AI replies. A real teammate must open the inbox; there is no
            guaranteed response time.
          </p>
          <div className="flex gap-3">
            <Button disabled={action.isPending} onClick={() => action.mutate("handoff")}>
              Confirm request
            </Button>
            <Button variant="outline" onClick={() => setConfirm(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      {action.isError && (
        <p role="alert" className="mt-3 text-sm">
          This action could not complete. Another teammate may have claimed or resolved this
          request. Refresh the conversation before retrying.
        </p>
      )}
      {!history.isError && history.data && history.data.length > 0 && (
        <div
          className="mt-5 max-h-80 space-y-3 overflow-y-auto"
          role="log"
          aria-label="Human support messages"
          aria-live="polite"
        >
          {history.data.map((message) => (
            <article
              key={message.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3"
            >
              <p className="mb-1 text-xs font-semibold">
                {message.sender_role === "SUPPORT" ? "Human support teammate" : "Requester"}
              </p>
              <p className="whitespace-pre-wrap break-words text-sm">{message.content}</p>
              <time className="text-xs text-[var(--muted)]" dateTime={message.created_at}>
                {new Date(message.created_at).toLocaleString()}
              </time>
            </article>
          ))}
        </div>
      )}
      {history.isError && <p role="alert">Human messages could not load.</p>}
      {active && (requester || assigned) && (
        <form
          className="mt-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (content.trim() && !send.isPending && !history.isError) send.mutate();
          }}
        >
          <label className="block text-sm">
            Message to {requester ? "human support" : "requester"}
            <textarea
              className="mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3"
              rows={3}
              required
              maxLength={4000}
              value={content}
              onChange={(e) => {
                setContent(e.target.value);
                if (send.isError) {
                  send.reset();
                  setKey(crypto.randomUUID());
                }
              }}
            />
          </label>
          <Button className="mt-2" disabled={!content.trim() || send.isPending || history.isError}>
            Send human message
          </Button>
        </form>
      )}
      {send.isError && (
        <p role="alert">Human message could not be sent. Your draft is preserved.</p>
      )}
    </section>
  );
}
