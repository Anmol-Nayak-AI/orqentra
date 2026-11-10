import { SupportInbox, HumanSupport } from "./human-support";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { MessageSquare, Plus, Send, BookOpen } from "lucide-react";
import type { components, WorkspaceResponse } from "@orqentra/contracts";
import { useSessionApi } from "../auth/client";
import { Button } from "../components/ui/button";
import { ApiError } from "../lib/api";

type Conversation = components["schemas"]["ConversationResponse"];
type Message = components["schemas"]["MessageResponse"];
const panel = "rounded-xl border border-[var(--border)] bg-[var(--surface)]";

export function ChatPage() {
  const { organizationId = "" } = useParams();
  return <KnowledgeChat key={organizationId} organizationId={organizationId} />;
}
function KnowledgeChat({ organizationId }: { organizationId: string }) {
  const { api, userId } = useSessionApi();
  const cache = useQueryClient();
  const base = `/organizations/${organizationId}`;
  const [workspace, setWorkspace] = useState("");
  const [selectedId, setSelected] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [notice, setNotice] = useState("");
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const workspaces = useQuery({
    queryKey: ["workspaces", userId, organizationId],
    queryFn: ({ signal }) => api<WorkspaceResponse[]>(`${base}/workspaces`, { signal }),
  });
  const capabilities = useQuery({
    queryKey: ["capabilities", userId, organizationId],
    queryFn: ({ signal }) =>
      api<components["schemas"]["ExecutionCapabilities"]>(`${base}/capabilities`, { signal }),
    refetchInterval: 15000,
  });
  const aiOffline =
    capabilities.data?.worker_online === false || capabilities.data?.model_configured === false;
  const workspaceId = workspace || workspaces.data?.[0]?.id || "";
  const chats = useQuery({
    queryKey: ["chats", userId, organizationId],
    queryFn: ({ signal }) => api<Conversation[]>(`${base}/chats`, { signal }),
  });
  const selected =
    selectedId ?? chats.data?.find((chat) => chat.workspace_id === workspaceId)?.id ?? null;
  const chatState = useQuery({
    queryKey: ["chat-state", userId, organizationId, selected],
    queryFn: ({ signal }) => api<Conversation>(`${base}/chats/${selected}`, { signal }),
    enabled: !!selected,
    refetchInterval: 3000,
  });
  const aiPaused = !!chatState.data && chatState.data.support_state !== "AI";
  const history = useQuery({
    queryKey: ["chat-messages", userId, organizationId, selected],
    queryFn: ({ signal }) => api<Message[]>(`${base}/chats/${selected}/messages`, { signal }),
    enabled: !!selected,
    refetchInterval: (query) =>
      query.state.data?.some((item) => item.status === "QUEUED" || item.status === "RUNNING")
        ? 2000
        : 10000,
  });
  const create = useMutation({
    mutationFn: () =>
      api<Conversation>(`${base}/chats`, {
        method: "POST",
        body: JSON.stringify({ workspace_id: workspaceId }),
      }),
    onSuccess: (chat) => {
      cache.setQueryData<Conversation[]>(["chats", userId, organizationId], (old) => [
        chat,
        ...(old ?? []),
      ]);
      setSelected(chat.id);
      setNotice("");
      void cache.invalidateQueries({ queryKey: ["chats", userId, organizationId] });
    },
    onError: () => setNotice("A new chat could not be created. Check your workspace access."),
  });
  const send = useMutation({
    mutationFn: () =>
      api<Message>(`${base}/chats/${selected}/messages`, {
        method: "POST",
        body: JSON.stringify({ question, idempotency_key: requestId }),
      }),
    onSuccess: () => {
      setQuestion("");
      setRequestId(crypto.randomUUID());
      setNotice("");
      void cache.invalidateQueries({
        queryKey: ["chat-messages", userId, organizationId, selected],
      });
      void cache.invalidateQueries({ queryKey: ["chats", userId, organizationId] });
    },
    onError: (error) =>
      setNotice(
        error instanceof ApiError && error.status === 429
          ? "The development chat quota has been reached. Please try again later."
          : "Message could not be queued. A reply may still be processing; refresh before retrying.",
      ),
  });
  const waiting = history.data?.some(
    (item) => item.status === "QUEUED" || item.status === "RUNNING",
  );
  if (workspaces.isError || chats.isError)
    return (
      <section role="alert">
        <h1>Chat could not load</h1>
        <Button
          onClick={() => {
            void chats.refetch();
            void workspaces.refetch();
          }}
        >
          Retry
        </Button>
      </section>
    );
  return (
    <section className="knowledge-chat">
      {aiOffline && (
        <p
          role="status"
          className="mb-5 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm"
        >
          AI processing is unavailable for this organization. Existing conversations and human
          support remain available. An operator must activate the AI worker before new AI questions
          can be processed.
        </p>
      )}
      <div className="workspace-page-heading">
        <div>
          <p className="workspace-eyebrow">GROUNDED IN YOUR KNOWLEDGE</p>
          <h1>Workspace chat</h1>
          <p>
            Ask about Orqentra or your workspace’s approved knowledge. Inspect the sources behind
            each answer.
          </p>
        </div>
      </div>
      {notice && (
        <p role="alert" className={`${panel} mb-4 p-4`}>
          {notice}
        </p>
      )}
      <div className="grid items-start gap-5 lg:grid-cols-[260px_1fr]">
        <aside className={`${panel} p-5`} aria-label="Chat conversations">
          <label className="block text-sm font-medium">
            Workspace
            <select
              className="mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-2"
              disabled={send.isPending || create.isPending}
              value={workspaceId}
              onChange={(event) => {
                setWorkspace(event.target.value);
                setSelected(null);
                setQuestion("");
                setNotice("");
                setRequestId(crypto.randomUUID());
              }}
            >
              {workspaces.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <Button
            className="my-4 w-full"
            disabled={!workspaceId || create.isPending || send.isPending}
            onClick={() => create.mutate()}
          >
            <Plus size={16} />
            {create.isPending ? "Creating…" : "New chat"}
          </Button>
          {chats.isPending && <p role="status">Loading conversations…</p>}
          {chats.isSuccess && !chats.data.some((chat) => chat.workspace_id === workspaceId) && (
            <p className="text-sm text-[var(--muted)]">
              No conversations yet. Select New chat to start.
            </p>
          )}
          {chats.data
            ?.filter((chat) => chat.workspace_id === workspaceId)
            .map((chat) => (
              <button
                type="button"
                key={chat.id}
                disabled={send.isPending || create.isPending}
                aria-pressed={selected === chat.id}
                className={`mb-2 flex w-full items-start gap-2 rounded-lg border p-3 text-left text-sm ${selected === chat.id ? "border-[var(--accent)]" : "border-transparent"}`}
                onClick={() => {
                  setSelected(chat.id);
                  setQuestion("");
                  setNotice("");
                  setRequestId(crypto.randomUUID());
                }}
              >
                <MessageSquare size={15} className="mt-1 shrink-0" />
                <span className="break-words">{chat.title}</span>
              </button>
            ))}
          <p className="mt-4 text-xs leading-5 text-[var(--muted)]">
            Conversations are private until you explicitly request human support. AI answers use
            only active, indexed workspace sources.
          </p>
          <SupportInbox
            organizationId={organizationId}
            disabled={send.isPending || create.isPending}
            onSelect={(chat) => {
              setWorkspace(chat.workspace_id);
              setSelected(chat.id);
              setQuestion("");
              setNotice("");
              setRequestId(crypto.randomUUID());
            }}
          />
        </aside>
        <div className={`${panel} min-w-0 overflow-hidden`}>
          {!selected ? (
            <div className="p-8">
              <BookOpen size={32} className="mb-5 text-[var(--muted)]" />
              <h2 className="text-xl font-semibold">Ask Orqentra</h2>
              <p className="mt-3 text-[var(--muted)]">
                Choose a conversation or create a new chat. Add approved sources in Knowledge and
                wait for their vector index to become ready.
              </p>
              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                {["How do I use Orqentra chat?", "How do I invite a teammate?"].map((prompt) => (
                  <p key={prompt} className="rounded-lg border border-[var(--border)] p-4 text-sm">
                    {prompt}
                  </p>
                ))}
              </div>
            </div>
          ) : (
            <>
              <div className="border-b border-[var(--border)] px-6 py-4">
                <h2 className="font-semibold">Knowledge assistant</h2>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  Vector retrieval · Source citations · No external actions
                </p>
              </div>
              {chatState.isSuccess && chatState.data && (
                <HumanSupport
                  key={selected}
                  organizationId={organizationId}
                  chat={chatState.data}
                  requester={!!chats.data?.some((chat) => chat.id === selected)}
                />
              )}
              {chatState.isError && (
                <p role="alert" className="p-4">
                  Conversation access could not be verified. Refresh to retry.
                </p>
              )}
              <div
                role="log"
                className="chat-transcript space-y-6 p-5 sm:p-6"
                aria-label="Chat history"
                aria-live="polite"
              >
                {history.isPending && <p role="status">Loading messages…</p>}
                {history.isError || chatState.isError ? (
                  <p role="alert">Messages could not load. Your current access may have changed.</p>
                ) : history.data?.length === 0 ? (
                  <p className="text-sm text-[var(--muted)]">
                    Ask your first question about this workspace’s knowledge.
                  </p>
                ) : (
                  history.data?.map((message) => (
                    <article key={message.id} className="space-y-3">
                      <div className="ml-auto max-w-[90%] rounded-2xl rounded-tr-sm border border-[var(--border)] bg-[var(--hover)] p-4">
                        <p className="mb-2 text-xs font-semibold text-[var(--muted)]">You</p>
                        <p className="whitespace-pre-wrap break-words text-sm leading-6">
                          {message.question}
                        </p>
                      </div>
                      <div className="max-w-[95%] rounded-2xl rounded-tl-sm border border-[var(--border)] p-4">
                        <p className="mb-2 text-xs font-semibold text-[var(--muted)]">
                          Orqentra assistant
                        </p>
                        {message.status === "QUEUED" || message.status === "RUNNING" ? (
                          <p role="status" className="text-sm">
                            {message.status === "QUEUED"
                              ? "Waiting for source indexing and processing…"
                              : "Retrieving evidence and preparing an answer…"}
                          </p>
                        ) : message.status === "FAILED" ? (
                          <p role="alert" className="text-sm">
                            The answer could not be completed. Your question is saved; you can send
                            another question.
                            <details className="mt-2 text-xs">
                              <summary>Error details</summary>
                              {message.error_code}
                            </details>
                          </p>
                        ) : (
                          <p className="whitespace-pre-wrap break-words text-sm leading-6">
                            {message.answer}
                          </p>
                        )}
                        {message.citations.length > 0 && (
                          <section
                            aria-label="Answer sources"
                            className="mt-4 border-t border-[var(--border)] pt-3"
                          >
                            <h3 className="text-xs font-semibold">Sources</h3>
                            {message.citations.map((cite, index) => (
                              <details
                                key={`${cite.chunk_id}-${cite.quote}`}
                                className="mt-2 rounded-lg bg-[var(--background)] p-3 text-sm"
                              >
                                <summary>
                                  {index + 1}. {cite.title}
                                </summary>
                                <blockquote className="mt-3 border-l-2 border-[var(--accent)] pl-3 text-[var(--muted)]">
                                  {cite.quote}
                                </blockquote>
                              </details>
                            ))}
                          </section>
                        )}
                      </div>
                    </article>
                  ))
                )}
              </div>
              <form
                className="border-t border-[var(--border)] p-5"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (
                    selected &&
                    question.trim().length >= 3 &&
                    !history.isError &&
                    !history.isPending &&
                    !send.isPending &&
                    !waiting &&
                    !aiPaused &&
                    !aiOffline &&
                    chatState.isSuccess
                  )
                    send.mutate();
                }}
              >
                <label className="sr-only" htmlFor="chat-question">
                  Ask a knowledge question
                </label>
                <textarea
                  id="chat-question"
                  className="w-full resize-y rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 text-sm"
                  required
                  minLength={3}
                  maxLength={2000}
                  rows={3}
                  placeholder="Ask about Orqentra or your workspace’s knowledge…"
                  value={question}
                  onChange={(event) => {
                    setQuestion(event.target.value);
                    if (send.isError) {
                      setRequestId(crypto.randomUUID());
                      send.reset();
                      setNotice("");
                    }
                  }}
                  disabled={
                    send.isPending ||
                    waiting ||
                    history.isError ||
                    history.isPending ||
                    aiPaused ||
                    aiOffline ||
                    !chatState.isSuccess
                  }
                />
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                  <span className="text-xs text-[var(--muted)]">
                    Check source quotes before relying on an answer.
                  </span>
                  <Button
                    disabled={
                      aiPaused ||
                      aiOffline ||
                      !chatState.isSuccess ||
                      send.isPending ||
                      waiting ||
                      history.isError ||
                      history.isPending ||
                      question.trim().length < 3
                    }
                  >
                    <Send size={15} />
                    Send
                  </Button>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
