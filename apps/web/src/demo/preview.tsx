import { useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Bot,
  Building2,
  Check,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  FileText,
  GitBranch,
  LayoutDashboard,
  MessageSquare,
  Search,
  Send,
  ShieldCheck,
  Users,
} from "lucide-react";

const repository = "https://github.com/Anmol-Nayak-AI/orqentra";
const sections = [
  ["Command Center", LayoutDashboard],
  ["Teammates", Bot],
  ["Chat", MessageSquare],
  ["Knowledge", BookOpen],
  ["Tasks & reviews", GitBranch],
  ["Members", Users],
  ["Release status", ShieldCheck],
] as const;
type Section = (typeof sections)[number][0];
const sectionSlug = (name: Section) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
const organizations = ["Northstar Labs", "Meridian Studio"];
const knowledge = [
  {
    title: "Orqentra product guide",
    topic: "Product",
    body: "Orqentra brings organization workspaces, AI teammates, source-grounded knowledge chat, bounded tasks and human oversight into one application.",
  },
  {
    title: "Knowledge and cited answers",
    topic: "RAG",
    body: "In the full local application, approved workspace text is chunked, embedded with OpenAI and stored in PostgreSQL/pgvector. Answers include validated quotations. Missing evidence should lead to an explicit limitation, not an invented answer.",
  },
  {
    title: "Human review and escalation",
    topic: "Oversight",
    body: "The application supports explicit conversation sharing with a human support agent. Task approvals bind to an artifact revision, hash and expiry. Code execution needs a separate, independent reviewer. No live human agent is connected to this preview.",
  },
  {
    title: "Organization access and isolation",
    topic: "Security",
    body: "Clerk verifies identity in the full application. Organization membership and RBAC restrict actions, while PostgreSQL forced row-level security isolates tenant records. The organization switch in this preview only selects fictional in-memory examples; it does not demonstrate authenticated isolation.",
  },
];
const people = [
  { name: "Avery Chen", role: "OWNER", team: "Operations" },
  { name: "Jordan Patel", role: "ADMIN", team: "Customer success" },
  { name: "Morgan Ellis", role: "MEMBER", team: "Research" },
  { name: "Riley Brooks", role: "VIEWER", team: "Leadership" },
];
const teammates = [
  {
    name: "Onboarding specialist",
    initials: "OS",
    purpose: "Turn approved guidance into a clear onboarding checklist.",
    workflow: "Retrieve → draft → validate → human review",
    output: "Checklist with source quotations",
  },
  {
    name: "Knowledge assistant",
    initials: "KA",
    purpose: "Find answers in approved workspace sources and show the evidence.",
    workflow: "Workspace retrieval → cited answer → optional human handoff",
    output: "Answer with inspectable sources",
  },
  {
    name: "Python analyst",
    initials: "PA",
    purpose: "Propose a bounded analysis for an independent person to review.",
    workflow: "Analysis proposal → independent code review → isolated execution when authorized",
    output: "Reviewed proposal; execution disabled here",
  },
];
type Reply = {
  id: string;
  question: string;
  answer: string;
  source: number | null;
};
export function previewAnswer(question: string): Omit<Reply, "question" | "id"> {
  const q = question.toLowerCase();
  if (/human|review|escalat|approv/.test(q)) return { answer: knowledge[2].body, source: 2 };
  if (/rag|knowledge|source|vector|chat|citation/.test(q))
    return { answer: knowledge[1].body, source: 1 };
  if (/security|tenant|member|organi|login|sign.in/.test(q))
    return { answer: knowledge[3].body, source: 3 };
  if (/orqentra|workforce|teammate|what.*do/.test(q))
    return { answer: knowledge[0].body, source: 0 };
  return {
    answer:
      "This guided preview has no live AI connection. Try asking about Orqentra, RAG, human review or organization security. Explore the repository for the real backend implementation.",
    source: null,
  };
}

export function DemoApp() {
  const [section, setSection] = useState<Section>(
    () =>
      sections.find(([name]) => sectionSlug(name) === window.location.hash.slice(1))?.[0] ??
      "Command Center",
  );
  const [organization, setOrganization] = useState(organizations[0]);
  const [search, setSearch] = useState("");
  const [question, setQuestion] = useState("");
  const [replies, setReplies] = useState<Reply[]>([]);
  const [reviewed, setReviewed] = useState(false);
  const [specialist, setSpecialist] = useState(0);
  const [activity, setActivity] = useState<string[]>([]);
  function navigate(next: Section) {
    window.history.replaceState(null, "", `#${sectionSlug(next)}`);
    setSection(next);
    setSearch("");
  }
  function switchOrganization(value: string) {
    setOrganization(value);
    setReplies([]);
    setQuestion("");
    setReviewed(false);
    setActivity([]);
    setSearch("");
  }
  function ask(value: string) {
    const input = value.trim().slice(0, 1000);
    if (!input) return;
    setReplies((old) => [
      ...old.slice(-9),
      { id: crypto.randomUUID(), question: input, ...previewAnswer(input) },
    ]);
    setQuestion("");
  }
  const filteredSources = knowledge.filter((source) =>
    `${source.title} ${source.body}`.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <div className="demo-app">
      <a className="skip-link" href="#demo-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="Orqentra preview home">
          <span className="brand-mark">O</span>orqentra<span className="brand-dot">.</span>
        </a>
        <div className="brand-subtitle">WORKFORCE PLATFORM</div>
        <label className="organization-picker">
          <span>
            <Building2 size={18} /> Fictional workspace
          </span>
          <select
            aria-label="Choose sample organization"
            value={organization}
            onChange={(event) => switchOrganization(event.target.value)}
          >
            {organizations.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <div className="nav-label">EXPLORE THE PLATFORM</div>
        <nav aria-label="Preview navigation">
          {sections.map(([name, Icon]) => (
            <button
              type="button"
              key={name}
              aria-current={section === name ? "page" : undefined}
              onClick={() => navigate(name)}
            >
              <Icon size={19} />
              <span>{name}</span>
              {section === name && <ChevronRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <p>
            Your workforce,
            <br />
            <strong>intelligently orchestrated.</strong>
          </p>
          <a href={repository} target="_blank" rel="noreferrer">
            Explore the source <ExternalLink size={15} />
          </a>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            Workspace <span>/</span> <strong>{section}</strong>
          </div>
          <a className="source-link" href={repository} target="_blank" rel="noreferrer">
            View on GitHub <ExternalLink size={15} />
          </a>
        </header>
        <div className="preview-notice">
          <span className="preview-tag">INTERACTIVE PREVIEW</span>
          <span>
            Fictional data · no live AI, account, payment or code execution. Changes reset on
            refresh.
          </span>
        </div>
        <main id="demo-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">{organization.toUpperCase()} · SAMPLE ORGANIZATION</div>
              <h1>{section === "Command Center" ? "A clear view of your workforce." : section}</h1>
              <p>
                {section === "Command Center"
                  ? "Specialized teammates. Grounded answers. People in control."
                  : "Explore an illustrative workflow. Your local Orqentra data is never used here."}
              </p>
            </div>
            <span className="sample-badge">
              <ShieldCheck size={15} /> Free public preview
            </span>
          </div>

          {section === "Command Center" && (
            <>
              <section className="welcome-panel">
                <div>
                  <div className="eyebrow">BUILT FOR WORK THAT NEEDS TRUST</div>
                  <h2>
                    From a question
                    <br />
                    to a reviewed outcome.
                  </h2>
                  <p>
                    Give your team a shared place to find knowledge, coordinate specialists and
                    review the work before it moves forward.
                  </p>
                  <button className="primary" type="button" onClick={() => navigate("Chat")}>
                    Explore workspace chat <ArrowRight size={17} />
                  </button>
                </div>
                <div className="workflow-preview">
                  <div className="workflow-top">
                    <Bot size={20} />
                    <strong>Onboarding specialist</strong>
                    <span className="pill">Sample workflow</span>
                  </div>
                  {["Approved workspace sources", "Source-grounded draft", "Human review gate"].map(
                    (label, index) => (
                      <div className="workflow-step" key={label}>
                        <span>{index === 2 ? <ShieldCheck size={17} /> : <Check size={17} />}</span>
                        <div>
                          <strong>{label}</strong>
                          <small>
                            {
                              [
                                "Knowledge stays within its workspace",
                                "Evidence accompanies the proposed answer",
                                "A person decides what happens next",
                              ][index]
                            }
                          </small>
                        </div>
                      </div>
                    ),
                  )}
                </div>
              </section>
              <div className="metric-grid">
                {[
                  ["Specialist examples", teammates.length, "Explore three focused roles"],
                  ["Guide sources", knowledge.length, "Read the evidence behind answers"],
                  [
                    "Review state",
                    reviewed ? "Reviewed" : "Needs review",
                    "Local preview state only",
                  ],
                ].map(([label, value, note]) => (
                  <article className="metric" key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                    <small>{note}</small>
                  </article>
                ))}
              </div>
              <div className="section-label">
                <h2>Choose your next step</h2>
                <span>Explore at your own pace</span>
              </div>
              <div className="card-grid">
                {[
                  [
                    "Knowledge",
                    "Start with the evidence",
                    "Inspect the sample sources that power this guided preview.",
                  ],
                  [
                    "Teammates",
                    "Meet the specialists",
                    "See how bounded roles help keep work focused.",
                  ],
                  [
                    "Tasks & reviews",
                    "Keep people in control",
                    "Walk through a local review interaction.",
                  ],
                ].map(([target, title, text]) => (
                  <button
                    className="explore-card"
                    type="button"
                    key={target}
                    onClick={() => navigate(target as Section)}
                  >
                    <div className="tile-icon">
                      <ArrowRight size={21} />
                    </div>
                    <h3>{title}</h3>
                    <p>{text}</p>
                    <span>
                      Explore {target.toLowerCase()} <ArrowRight size={16} />
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}

          {section === "Teammates" && (
            <>
              <div className="card-grid">
                {teammates.map((agent, index) => (
                  <article className="panel teammate" key={agent.name}>
                    <div className="avatar">{agent.initials}</div>
                    <h2>{agent.name}</h2>
                    <p>{agent.purpose}</p>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setSpecialist(index)}
                      aria-pressed={specialist === index}
                    >
                      View workflow <ArrowRight size={15} />
                    </button>
                  </article>
                ))}
              </div>
              <section className="panel detail-panel">
                <div className="eyebrow">ROLE DESIGN</div>
                <h2>{teammates[specialist].name}</h2>
                <p>{teammates[specialist].workflow}</p>
                <div className="inset">
                  <strong>Proposed output</strong>
                  <p>{teammates[specialist].output}</p>
                </div>
                <p className="muted">
                  Examples only. No agent runs or sandbox resources are created from this page.
                </p>
              </section>
            </>
          )}

          {section === "Chat" && (
            <div className="chat-grid">
              <aside className="panel chat-context">
                <div className="tile-icon">
                  <BookOpen size={21} />
                </div>
                <h2>Ask about Orqentra</h2>
                <p>
                  Explore guided answers from the product guide. These answers are selected locally;
                  no model or vector database is called.
                </p>
                {[
                  "What is Orqentra?",
                  "How does RAG chat work?",
                  "When is human review needed?",
                  "How are organizations isolated?",
                ].map((prompt) => (
                  <button className="prompt" type="button" key={prompt} onClick={() => ask(prompt)}>
                    {prompt}
                    <ArrowRight size={14} />
                  </button>
                ))}
                <small>
                  Do not enter secrets or personal information. Input remains in this browser tab
                  and is not submitted to a server.
                </small>
              </aside>
              <section className="panel chat-panel">
                <div className="panel-header">
                  <div>
                    <h2>Product guide</h2>
                    <span>Guided preview · {organization}</span>
                  </div>
                  <span className="pill">No live AI</span>
                </div>
                <div className="messages" role="log" aria-live="polite">
                  {replies.length === 0 ? (
                    <div className="chat-empty">
                      <MessageSquare size={32} />
                      <h3>Start with a question.</h3>
                      <p>Choose a suggested prompt or ask about the product.</p>
                    </div>
                  ) : (
                    replies.map((reply) => (
                      <div className="exchange" key={reply.id}>
                        <div className="question">
                          <small>You · local input</small>
                          <p>{reply.question}</p>
                        </div>
                        <div className="answer">
                          <small>Orqentra product guide · scripted answer</small>
                          <p>{reply.answer}</p>
                          {reply.source !== null && (
                            <details>
                              <summary>
                                <FileText size={15} /> Source: {knowledge[reply.source].title}
                              </summary>
                              <p>{knowledge[reply.source].body}</p>
                            </details>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    ask(question);
                  }}
                >
                  <label htmlFor="preview-question">Ask about the product</label>
                  <div className="composer">
                    <input
                      id="preview-question"
                      maxLength={1000}
                      autoComplete="off"
                      value={question}
                      onChange={(event) => setQuestion(event.target.value)}
                      placeholder="How does human review work?"
                    />
                    <button className="primary" disabled={!question.trim()} type="submit">
                      <Send size={16} />
                      <span>Ask</span>
                    </button>
                  </div>
                  <small>Guided sample responses, not a live RAG session.</small>
                </form>
              </section>
            </div>
          )}

          {section === "Knowledge" && (
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2>Product knowledge</h2>
                  <p>Static guide excerpts used in this public preview.</p>
                </div>
                <span className="pill">{filteredSources.length} sources</span>
              </div>
              <label className="search-field">
                <Search size={18} />
                <input
                  aria-label="Search sample knowledge"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search the product guide…"
                />
              </label>
              <div className="source-list">
                {filteredSources.map((source) => (
                  <details key={source.title}>
                    <summary>
                      <FileText size={21} />
                      <span>
                        <strong>{source.title}</strong>
                        <small>{source.topic} · sample excerpt</small>
                      </span>
                      <ChevronRight size={16} />
                    </summary>
                    <p>{source.body}</p>
                  </details>
                ))}
                {filteredSources.length === 0 && (
                  <p className="empty-state">No guide excerpts match your search.</p>
                )}
              </div>
            </section>
          )}

          {section === "Tasks & reviews" && (
            <div className="review-grid">
              <section className="panel detail-panel">
                <div className="eyebrow">ILLUSTRATIVE ONBOARDING TASK</div>
                <h2>Prepare a new teammate's first week</h2>
                <p>A structured draft with a person at the decision point.</p>
                <div className="inset">
                  <h3>Sample checklist</h3>
                  {[
                    "Review the team's approved operating guide",
                    "Confirm the workspace and membership role",
                    "Meet the assigned onboarding reviewer",
                  ].map((task) => (
                    <div className="check-row" key={task}>
                      <CheckCircle2 size={19} />
                      <span>{task}</span>
                    </div>
                  ))}
                </div>
                <p className="muted">
                  This static example is not a generated artifact or an approved execution. The
                  backend implements revision/hash-bound reviews separately.
                </p>
              </section>
              <aside className="panel detail-panel">
                <ShieldCheck size={27} />
                <h2>{reviewed ? "Preview marked reviewed" : "A person makes the call."}</h2>
                <p>
                  Try the review interaction. It only changes this page's in-memory sample state.
                </p>
                <button
                  type="button"
                  className="primary"
                  disabled={reviewed}
                  onClick={() => {
                    setReviewed(true);
                    setActivity(["Sample checklist marked reviewed in this browser tab."]);
                  }}
                >
                  {reviewed ? "Preview reviewed" : "Mark preview reviewed"}
                  <Check size={16} />
                </button>
                <div className="inset">
                  <strong>Preview activity</strong>
                  {activity.length ? (
                    activity.map((event) => <p key={event}>{event}</p>)
                  ) : (
                    <p>No local preview changes yet.</p>
                  )}
                </div>
              </aside>
            </div>
          )}

          {section === "Members" && (
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2>The sample team</h2>
                  <p>Fictional profiles. No login accounts or permissions are granted.</p>
                </div>
                <span className="pill">4 example profiles</span>
              </div>
              <label className="search-field">
                <Search size={18} />
                <input
                  aria-label="Search fictional members"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search name, team or role…"
                />
              </label>
              <div className="member-list">
                {people
                  .filter((person) =>
                    `${person.name} ${person.team} ${person.role}`
                      .toLowerCase()
                      .includes(search.toLowerCase()),
                  )
                  .map((person) => (
                    <div className="member-row" key={person.name}>
                      <span className="avatar">
                        {person.name
                          .split(" ")
                          .map((part) => part[0])
                          .join("")}
                      </span>
                      <div>
                        <strong>{person.name}</strong>
                        <small>{person.team} · fictional profile</small>
                      </div>
                      <span className="role-badge">{person.role}</span>
                    </div>
                  ))}
              </div>
            </section>
          )}

          {section === "Release status" && (
            <section className="panel detail-panel release-panel">
              <div className="eyebrow">TRANSPARENT BY DESIGN</div>
              <h2>Explore the product. Inspect the implementation.</h2>
              <p>
                This free preview is a separate static build of the interface. It has no connection
                to the local database, Clerk sessions, OpenAI, payment provider or sandbox. All
                organizations, team profiles and workflow data shown here are illustrative.
              </p>
              <div className="release-grid">
                <div>
                  <h3>Implemented in the full local application</h3>
                  <ul>
                    <li>Clerk identity, organization RBAC and forced PostgreSQL RLS</li>
                    <li>pgvector RAG with validated source quotations</li>
                    <li>Persistent LangGraph tasks and human review gates</li>
                    <li>Human support handoff and member administration</li>
                    <li>Test billing lifecycle and an isolated E2B execution boundary</li>
                  </ul>
                </div>
                <div>
                  <h3>Commercial acceptance still pending</h3>
                  <ul>
                    <li>Real-provider payment and sandbox acceptance</li>
                    <li>Hosted full-stack deployment and recovery evidence</li>
                    <li>Remaining genuine-session and two-human verification</li>
                    <li>Broader load, security and reliability assessment</li>
                    <li>Approved customer connectors and operating procedures</li>
                  </ul>
                </div>
              </div>
              <a
                className="primary"
                href={`${repository}/blob/main/docs/RELEASE_ACCEPTANCE.md`}
                target="_blank"
                rel="noreferrer"
              >
                Read the release evidence <ExternalLink size={16} />
              </a>
            </section>
          )}
          <footer>
            <span>Orqentra · Your workforce, intelligently orchestrated.</span>
            <button type="button" onClick={() => navigate("Release status")}>
              Preview limits <ArrowRight size={14} />
            </button>
          </footer>
        </main>
      </div>
    </div>
  );
}
