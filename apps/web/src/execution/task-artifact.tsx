import { Button } from "../components/ui/button";

type Evidence = { document_id: string; quote: string };
type Item = { task: string; evidence: Evidence[] };
function checklist(value: unknown): Item[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (row): row is Item =>
      row &&
      typeof row.task === "string" &&
      Array.isArray(row.evidence) &&
      row.evidence.every(
        (e: Evidence) => typeof e?.document_id === "string" && typeof e?.quote === "string",
      ),
  );
}
export function TaskArtifact({
  output,
  approved,
  runId,
}: {
  output: Record<string, unknown>;
  approved: boolean;
  runId: string;
}) {
  const summary = typeof output.summary === "string" ? output.summary : "";
  const draft = typeof output.draft_reply === "string" ? output.draft_reply : "";
  const items = [
    ...new Map(checklist(output.checklist).map((item) => [JSON.stringify(item), item])).values(),
  ];
  const missing = Array.isArray(output.missing_information)
    ? output.missing_information.filter((v): v is string => typeof v === "string")
    : [];
  function download() {
    const body = [
      `# Approved task artifact`,
      `Task: ${runId}`,
      "",
      summary,
      "",
      ...items.flatMap((item) => [
        `- ${item.task}`,
        ...item.evidence.map((e) => `  Source ${e.document_id}: ${e.quote}`),
      ]),
      "",
      "## Draft reply",
      draft,
      "",
      ...(typeof output.proposed_python === "string"
        ? ["Proposed Python (not executed):", output.proposed_python, ""]
        : []),
      "No external message was sent by this download.",
    ].join("\n");
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `orqentra-approved-${runId}.txt`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <section className="mt-5" aria-label="Task artifact">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold">Generated artifact and evidence</h3>
        {approved && summary && (
          <Button variant="outline" onClick={download}>
            Download approved artifact
          </Button>
        )}
      </div>
      {!summary ? (
        <p className="mt-3 text-sm text-[var(--muted)]">
          The generated artifact will appear here when processing completes.
        </p>
      ) : (
        <p className="mt-3 whitespace-pre-wrap">{summary}</p>
      )}
      {items.length > 0 && (
        <ol className="mt-4 space-y-4">
          {items.map((item, index) => (
            <li key={JSON.stringify(item)} className="rounded-lg border border-[var(--border)] p-4">
              <p className="font-medium">
                {index + 1}. {item.task}
              </p>
              {Array.from(
                new Map(item.evidence.map((e) => [`${e.document_id}:${e.quote}`, e])).values(),
              ).map((e) => (
                <blockquote
                  key={`${e.document_id}:${e.quote}`}
                  className="mt-3 border-l-2 border-[var(--accent)] pl-3 text-sm"
                >
                  <p className="whitespace-pre-wrap">{e.quote}</p>
                  <p className="mt-1 break-all text-xs text-[var(--muted)]">
                    Source: {e.document_id}
                  </p>
                </blockquote>
              ))}
            </li>
          ))}
        </ol>
      )}
      {missing.length > 0 && (
        <section className="mt-4 rounded-lg border border-[var(--border)] p-4">
          <h4 className="font-semibold">Information needed</h4>
          <ul className="mt-2 list-disc pl-5">
            {[...new Set(missing)].map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </section>
      )}
      {typeof output.proposed_python === "string" && output.proposed_python && (
        <section className="mt-4 rounded-lg border border-[var(--border)] p-4">
          <h4 className="font-semibold">Proposed Python analysis · not executed</h4>
          <pre className="mt-3 overflow-auto whitespace-pre-wrap text-sm">
            {output.proposed_python}
          </pre>
          <p className="mt-2 text-sm text-[var(--muted)]">
            After approving the task, submit this code below for independent review. This draft is
            not authorization to execute it.
          </p>
        </section>
      )}
      {draft && (
        <section className="mt-4 rounded-lg border border-[var(--border)] p-4">
          <h4 className="font-semibold">Draft reply</h4>
          <p className="mt-2 whitespace-pre-wrap">{draft}</p>
        </section>
      )}
    </section>
  );
}
