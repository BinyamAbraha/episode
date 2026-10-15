import { useEffect, useState } from "react";
type Props = {
  id: number;
  revision: number;
  seek: (t: number) => void;
  request: (path: string, body?: any) => Promise<any>;
  action: (fn: () => Promise<any>, message: string) => Promise<void>;
};
export function Analysis({ id, revision, seek, request, action }: Props) {
  const [selectedRun, setSelectedRun] = useState("");
  const [runs, setRuns] = useState<any[] | null>(null),
    [error, setError] = useState(""),
    [tick, setTick] = useState(0),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    request(`/episodes/${id}/analyses`)
      .then((r) => {
        if (live) {
          setRuns(r);
          setError("");
        }
      })
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
  }, [id, revision, tick]);
  useEffect(() => {
    const timer = setInterval(() => setTick((x) => x + 1), 5000);
    return () => clearInterval(timer);
  }, []);
  async function queue(mode: string) {
    setBusy(true);
    try {
      await action(
        () => request("/analysis-jobs", { episodes: [id], mode }),
        "Analysis queued. Jobs shows progress; completed results appear here.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="analysis-section" aria-label="Episode analysis">
      <div className="section-heading">
        <h2>Analysis and suggestions</h2>
        <div className="analysis-actions">
          <button disabled={busy} onClick={() => queue("diagnostics")}>
            Analyze images and signals
          </button>
          <button disabled={busy} onClick={() => queue("vlm")}>
            Suggest annotations locally
          </button>
        </div>
      </div>
      <p>
        Recorded evidence. Visual hints are heuristic. Model suggestions require
        review and do not change task outcome automatically.
      </p>
      {error && (
        <p role="alert">{error} Previously loaded results may be stale.</p>
      )}
      {!runs && <p role="status">Loading analysis…</p>}
      {runs?.length === 0 && (
        <p>
          No completed analysis. Queue diagnostics or local model suggestions.
          The optional analysis environment must be installed.
        </p>
      )}
      {!!runs?.length && (
        <label>
          Analysis run
          <select
            value={
              selectedRun || (runs.find((r) => r.mode === "vlm") || runs[0]).id
            }
            onChange={(e) => setSelectedRun(e.target.value)}
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.mode} · {r.created} · {r.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
      )}
      {runs
        ?.filter(
          (r) =>
            r.id ===
            (selectedRun || (runs.find((x) => x.mode === "vlm") || runs[0]).id),
        )
        .map((run) => (
          <article className="panel" key={run.id}>
            <div className="section-heading">
              <h3>
                {run.mode === "vlm"
                  ? "Model-assisted review"
                  : "Visual and signal diagnostics"}
              </h3>
              <span>{run.result.seconds.toFixed(2)} s measured</span>
            </div>
            <p>
              <small>
                Recorded {run.created} · {run.id.slice(0, 12)}
              </small>
            </p>
            {run.result.semantic && <p>{run.result.semantic.summary}</p>}
            {run.result.model_output_error && (
              <p role="alert">
                Model output failed evidence validation. No suggestions were
                published. Inspect raw output below.
              </p>
            )}
            {run.mode === "vlm" && (
              <details>
                <summary>Sampled model evidence</summary>
                <img
                  className="contact-sheet"
                  src={`/api/analyses/${run.id}/evidence/contact-sheet.png`}
                  alt="Two camera rows with four timestamped evidence frames each"
                />
                <p>Eight sparse frames. Events between them may be missed.</p>
              </details>
            )}
            <div className="suggestion-list">
              {run.suggestions.map((s: any) => (
                <Suggestion
                  key={s.id}
                  suggestion={s}
                  run={run}
                  seek={seek}
                  request={request}
                  action={action}
                />
              ))}
            </div>
            <details>
              <summary>
                Diagnostic samples ({run.result.diagnostics.length})
              </summary>
              <div
                className="table-scroll"
                role="region"
                aria-label="Visual diagnostic measurements"
                tabIndex={0}
              >
                <table>
                  <thead>
                    <tr>
                      <th>Camera / time</th>
                      <th>Luminance</th>
                      <th>Blur proxy</th>
                      <th>Motion proxy</th>
                      <th>Review hints</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.result.diagnostics.map((d: any) => (
                      <tr key={d.evidence}>
                        <td>
                          <button onClick={() => seek(d.time)}>
                            {d.camera} {d.time.toFixed(2)} s
                          </button>
                        </td>
                        <td>{d.values.luminance_mean.toFixed(1)}</td>
                        <td>{d.values.laplacian_variance.toFixed(1)}</td>
                        <td>
                          {d.values.flow_pixels_per_sample?.toFixed(2) ??
                            "First sample"}
                        </td>
                        <td>
                          {d.hints
                            .map(
                              (h: any) =>
                                `${h.rule}: ${h.observed.toFixed(2)} (threshold ${h.threshold})`,
                            )
                            .join("; ") || "No hints"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p>
                Blur proxy is Laplacian variance at 320 × 240. Motion is
                optical-flow pixels between sparse samples, not physical
                velocity. Low texture and intentional stillness can explain
                hints.
              </p>
            </details>
            <details>
              <summary>Signal ranges and changes</summary>
              <pre tabIndex={0} aria-label="Signal diagnostic measurements">
                {JSON.stringify(run.result.signals, null, 2)}
              </pre>
            </details>
            <details>
              <summary>Analysis provenance and raw model output</summary>
              <pre tabIndex={0} aria-label="Analysis provenance">
                {JSON.stringify(run.result, null, 2)}
              </pre>
            </details>
          </article>
        ))}
    </section>
  );
}
function Suggestion({ suggestion: s, run, seek, request, action }: any) {
  const b = s.body;
  const [decision, setDecision] = useState("accept"),
    [reason, setReason] = useState(""),
    [label, setLabel] = useState(b.label),
    [start, setStart] = useState(String(b.start)),
    [end, setEnd] = useState(String(b.end)),
    [busy, setBusy] = useState(false);
  return (
    <article className="suggestion" aria-label={`Suggestion ${s.id}`}>
      <div className="section-heading">
        <h4>
          {b.label.replaceAll("_", " ")} · {b.start.toFixed(2)} to{" "}
          {b.end.toFixed(2)} s
        </h4>
        <span className="badge">
          {s.decision ? `Reviewed: ${s.decision}` : "Pending review"}
        </span>
      </div>
      {b.label === "outcome" && (
        <p>
          Outcome hypothesis: <strong>{b.outcome}</strong>
        </p>
      )}
      <p>{b.explanation}</p>
      <div className="evidence-strip">
        {b.evidence.map((fid: string) => {
          const ev = run.result.evidence.find((x: any) => x.id === fid);
          return (
            <button key={fid} onClick={() => seek(ev.time)}>
              <img
                loading="lazy"
                src={`/api/analyses/${run.id}/evidence/${ev.file}`}
                alt={`${ev.camera.split(".").pop()} at ${ev.time.toFixed(2)} seconds`}
              />
              <span>
                {fid} · {ev.time.toFixed(2)} s
              </span>
            </button>
          );
        })}
      </div>
      {s.annotation && (
        <p>
          Approved annotation: <strong>{s.approved_label}</strong> ·{" "}
          {s.approved_start?.toFixed(2)} to {s.approved_end?.toFixed(2)} s
        </p>
      )}
      {s.decision ? (
        <p>
          Review reason: {s.reason}
          {s.annotation ? ` · Annotation ${s.annotation}` : ""}
        </p>
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              await action(
                () =>
                  request(`/suggestions/${s.id}/decision`, {
                    decision,
                    reason,
                    label,
                    start: Number(start),
                    end: Number(end),
                  }),
                "Suggestion decision saved. Episode outcome remains separately reviewed.",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Suggestion decision
            <select
              value={decision}
              onChange={(e) => setDecision(e.target.value)}
            >
              <option value="accept">Accept as interval annotation</option>
              <option value="edit">Edit and approve annotation</option>
              <option value="reject">Reject suggestion</option>
            </select>
          </label>
          {decision === "edit" && (
            <div className="form-row">
              <label>
                Approved label
                <input
                  required
                  maxLength={100}
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                />
              </label>
              <label>
                Approved start (s)
                <input
                  required
                  type="number"
                  step="any"
                  min="0"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
              </label>
              <label>
                Approved end (s)
                <input
                  required
                  type="number"
                  step="any"
                  min="0"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                />
              </label>
            </div>
          )}
          <label>
            Suggestion review reason
            <textarea
              required
              maxLength={2000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <button disabled={busy}>Save suggestion decision</button>
        </form>
      )}
    </article>
  );
}
