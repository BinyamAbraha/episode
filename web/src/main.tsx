import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
type Row = {
  id: number;
  task: string;
  duration: number;
  samples: number;
  review: string;
  outcome: string;
  findings: number;
  errors: number;
};
type Sample = {
  timestamp: number;
  frame_index: number;
  "observation.state": number[];
  action: number[];
};
type Finding = {
  id: number;
  rule: string;
  severity: string;
  start: number;
  end: number;
  observed: string;
  threshold: string;
  explanation: string;
};
type Episode = Row & {
  metadata: Record<string, any>;
  samples: Sample[];
  info: any;
  cameras: { key: string; label: string; offset: number; url: string }[];
  reviews: any[];
  annotations: any[];
  findings: Finding[];
};
async function api<T = any>(path: string, body?: any): Promise<T> {
  const r = await fetch(
    "/api" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!r.ok) {
    const e = await r.json();
    throw Error(
      typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail),
    );
  }
  return r.json();
}
const f = (n: number) => n.toFixed(2);
function App() {
  const params = new URLSearchParams(location.search);
  const [view, setView] = useState(params.get("view") || "catalog");
  const [id, setId] = useState<number | null>(
    params.has("episode") ? Number(params.get("episode")) : null,
  );
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [revision, refresh] = useState(0);
  function navigate(v: string, e: number | null = null) {
    setView(v);
    setId(e);
    history.pushState({}, "", `?view=${v}${e !== null ? "&episode=" + e : ""}`);
    setError("");
    setNotice("");
  }
  async function action(fn: () => Promise<any>, message: string) {
    setError("");
    try {
      await fn();
      setNotice(message);
      refresh((x) => x + 1);
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    const handler = () => {
      const p = new URLSearchParams(location.search);
      setView(p.get("view") || "catalog");
      setId(p.has("episode") ? Number(p.get("episode")) : null);
    };
    addEventListener("popstate", handler);
    return () => removeEventListener("popstate", handler);
  }, []);
  return (
    <div className="shell">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="top">
        <a href="?view=catalog" className="brand">
          EPISODE<span>Robotics data workbench</span>
        </a>
        <span className="local">LOCAL / RECORDED DATA</span>
      </header>
      <div className="layout">
        <nav aria-label="Main navigation">
          {[
            ["catalog", "Episodes"],
            ["quality", "Quality review"],
            ["selections", "Selections"],
            ["versions", "Dataset versions"],
            ["jobs", "Jobs"],
            ["verification", "Verification"],
          ].map(([v, label]) => (
            <button
              key={v}
              className={view === v ? "active" : ""}
              onClick={() => navigate(v)}
            >
              {label}
            </button>
          ))}
          <div className="nav-note">
            LeRobot v3 adapter
            <br />
            Pinned source revision
            <br />
            <code>f641879e2217</code>
          </div>
        </nav>
        <main id="main">
          {notice && (
            <div role="status" className="notice">
              {notice}
            </div>
          )}
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          {id !== null ? (
            <Inspector
              key={id}
              id={id}
              revision={revision}
              action={action}
              back={() => navigate("catalog")}
            />
          ) : view === "catalog" || view === "quality" ? (
            <Catalog
              key={view}
              quality={view === "quality"}
              open={(n) => navigate("catalog", n)}
              revision={revision}
              action={action}
            />
          ) : view === "versions" ? (
            <Versions revision={revision} action={action} />
          ) : view === "selections" ? (
            <Selections revision={revision} action={action} />
          ) : view === "jobs" ? (
            <Jobs revision={revision} action={action} />
          ) : (
            <Verification revision={revision} />
          )}
        </main>
      </div>
      <footer>
        Source: lerobot/svla_so101_pickplace · Apache-2.0 · Camera
        synchronization and physical units are undocumented.
      </footer>
    </div>
  );
}
type Action = (fn: () => Promise<any>, message: string) => Promise<void>;
function Catalog({
  quality,
  open,
  revision,
  action,
}: {
  quality: boolean;
  open: (id: number) => void;
  revision: number;
  action: Action;
}) {
  const source = useData("/source", revision);
  const p = new URLSearchParams(location.search);
  const [search, setSearch] = useState(p.get("search") || "");
  const [review, setReview] = useState(p.get("review") || "");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("id");
  const [min, setMin] = useState("0");
  const [result, setResult] = useState<{ items: Row[]; total: number } | null>(
    null,
  );
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setResult(null);
    setError("");
    const q = new URLSearchParams({
      search,
      review,
      page: String(page),
      sort,
      min_duration: min || "0",
      findings: String(quality),
    });
    api("/episodes?" + q)
      .then((x) => live && setResult(x))
      .catch((e) => live && setError(String(e)));
    history.replaceState(
      {},
      "",
      `?view=${quality ? "quality" : "catalog"}&search=${encodeURIComponent(search)}&review=${review}`,
    );
    return () => {
      live = false;
    };
  }, [search, review, page, sort, min, revision, quality]);
  return (
    <>
      <div className="heading">
        <div>
          <div className="eyebrow">SOURCE COLLECTION / 01</div>
          <h1>{quality ? "Quality review" : "Episode catalog"}</h1>
          <p>Pick-and-place demonstrations from a preserved, pinned source.</p>
        </div>
        <button
          onClick={() =>
            action(
              () => api("/jobs", { limit: 50 }),
              "Import queued. A running worker will process it.",
            )
          }
        >
          Import source
        </button>
      </div>
      <div className="source-line">
        {source.data?.info ? (
          <>
            <strong>{source.data.info.robot_type}</strong>
            <span>
              {
                Object.values(source.data.info.features).filter(
                  (f: any) => f.dtype === "video",
                ).length
              }{" "}
              cameras
            </span>
            <span>
              {source.data.info.features["observation.state"].shape[0]} state /{" "}
              {source.data.info.features.action.shape[0]} action dimensions
            </span>
            <span>{source.data.info.fps} FPS nominal</span>
          </>
        ) : (
          <span>No imported source metadata</span>
        )}
      </div>
      <div className="filters">
        <label>
          Search task or episode
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search recordings"
          />
        </label>
        <label>
          Review status
          <select
            value={review}
            onChange={(e) => {
              setReview(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All reviews</option>
            <option value="unreviewed">Unreviewed</option>
            <option value="accepted">Accepted</option>
            <option value="excluded">Excluded</option>
          </select>
        </label>
        <label>
          Minimum duration (s)
          <input
            type="number"
            min="0"
            value={min}
            onChange={(e) => {
              setMin(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          Sort
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="id">Episode index</option>
            <option value="duration">Duration</option>
          </select>
        </label>
      </div>
      {error ? (
        <p role="alert">{error}</p>
      ) : !result ? (
        <p role="status">Loading episodes…</p>
      ) : (
        <>
          <div className="table-caption">
            <span>{result.total} matching episodes</span>
            <span>Technical findings and human review are independent</span>
          </div>
          <div
            className="table-wrap"
            role="region"
            aria-label="Episode catalog"
            tabIndex={0}
          >
            <table>
              <thead>
                <tr>
                  <th scope="col">Episode</th>
                  <th scope="col">Task</th>
                  <th scope="col">Duration</th>
                  <th scope="col">Samples</th>
                  <th scope="col">Validation</th>
                  <th scope="col">Review</th>
                  <th scope="col">Inspect</th>
                </tr>
              </thead>
              <tbody>
                {result.items.map((e) => (
                  <tr key={e.id}>
                    <td className="mono">EP {String(e.id).padStart(3, "0")}</td>
                    <td>{e.task}</td>
                    <td>{f(e.duration)} s</td>
                    <td>{e.samples}</td>
                    <td>
                      <span className={"badge " + (e.errors ? "bad" : "good")}>
                        {e.errors
                          ? "Structural error"
                          : e.findings
                            ? e.findings + " findings"
                            : "No findings"}
                      </span>
                    </td>
                    <td>{e.review}</td>
                    <td>
                      <button
                        className="text-button"
                        onClick={() => open(e.id)}
                      >
                        Open {e.id} <span aria-hidden="true">↗</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.total === 0 && (
            <div className="empty">
              <h2>No matching episodes</h2>
              <p>
                {quality
                  ? "No real-source findings match this view. Controlled faults are available below."
                  : "Adjust the filters or import the pinned source to begin."}
              </p>
            </div>
          )}
          <div className="pager">
            <button disabled={page === 1} onClick={() => setPage((x) => x - 1)}>
              Previous
            </button>
            <span>
              Page {page} of {Math.max(1, Math.ceil(result.total / 20))}
            </span>
            <button
              disabled={page * 20 >= result.total}
              onClick={() => setPage((x) => x + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
      {quality && <Faults />}
    </>
  );
}
function Plot({
  samples,
  field,
  dimension,
  time,
  duration,
  onSeek,
}: {
  samples: Sample[];
  field: "observation.state" | "action";
  dimension: number;
  time: number;
  duration: number;
  onSeek: (t: number) => void;
}) {
  const values = samples.map((s) => s[field][dimension]);
  const low = Math.min(...values),
    high = Math.max(...values),
    range = high - low || 1;
  const path = samples
    .map(
      (s, i) =>
        `${i ? "L" : "M"} ${30 + (s.timestamp / duration) * 870} ${100 - ((values[i] - low) / range) * 75}`,
    )
    .join(" ");
  return (
    <div className="plot">
      <div className="plot-label">
        <strong>{field === "action" ? "Action" : "Observed state"}</strong>
        <span>
          {f(low)} to {f(high)} · source units unknown
        </span>
      </div>
      <svg
        viewBox="0 0 930 125"
        role="img"
        aria-label={`${field} signal; values available in the sample table below`}
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          onSeek(
            Math.max(
              0,
              Math.min(
                duration - 1 / 30,
                ((((e.clientX - rect.left) / rect.width) * 930 - 30) / 870) *
                  duration,
              ),
            ),
          );
        }}
      >
        <line x1="30" x2="900" y1="100" y2="100" stroke="#c8d1cb" />
        <line x1="30" x2="900" y1="60" y2="60" stroke="#e1e6e2" />
        <path
          d={path}
          fill="none"
          stroke={field === "action" ? "#9a4c20" : "#116457"}
          strokeWidth="2"
        />
        <line
          x1={30 + (time / duration) * 870}
          x2={30 + (time / duration) * 870}
          y1="15"
          y2="108"
          stroke="#172b2a"
          strokeDasharray="3 3"
        />
        <text x="30" y="121">
          0 s
        </text>
        <text x="860" y="121">
          {f(duration)} s
        </text>
      </svg>
    </div>
  );
}
function Inspector({
  id,
  revision,
  action,
  back,
}: {
  id: number;
  revision: number;
  action: Action;
  back: () => void;
}) {
  const [e, setE] = useState<Episode | null>(null);
  const [error, setError] = useState("");
  const [time, setTime] = useState(
    Number(new URLSearchParams(location.search).get("time") || 0),
  );
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [dimension, setDimension] = useState(0);
  const [decoded, setDecoded] = useState(false);
  const [issue, setIssue] = useState<Finding | null>(null);
  const videos = useRef<(HTMLVideoElement | null)[]>([]);
  const [status, setStatus] = useState("accepted");
  const [outcome, setOutcome] = useState("unknown");
  const [reason, setReason] = useState("");
  const [label, setLabel] = useState("");
  const [note, setNote] = useState("");
  const [start, setStart] = useState("0");
  const [end, setEnd] = useState("1");
  const [busy, setBusy] = useState(false);
  const [mediaError, setMediaError] = useState("");
  useEffect(() => {
    api<Episode>("/episodes/" + id)
      .then((data) => {
        setE(data);
        setTime((t) => Math.min(Math.max(0, t), data.duration - 1 / 30));
      })
      .catch((err) => setError(String(err)));
  }, [id, revision]);
  function seek(t: number) {
    if (!e) return;
    const v = Math.max(0, Math.min(e.duration - 1 / 30, t));
    setTime(v);
    videos.current.forEach((video, i) => {
      if (video) video.currentTime = e.cameras[i].offset + v;
    });
    const q = new URLSearchParams(location.search);
    q.set("time", v.toFixed(3));
    history.replaceState({}, "", "?" + q);
  }
  useEffect(() => {
    if (!e) return;
    videos.current.forEach((v, i) => {
      if (v) {
        v.playbackRate = speed;
        if (playing && !decoded) {
          v.currentTime = e.cameras[i].offset + time;
          v.play().catch(() => setPlaying(false));
        } else v.pause();
      }
    });
  }, [playing, speed, decoded, e]);
  useEffect(() => {
    if (!playing || !e) return;
    let frame: number;
    function tick() {
      const v = videos.current[0];
      if (v && e) {
        const t = v.currentTime - e.cameras[0].offset;
        if (t >= e.duration - 1 / 30) {
          setPlaying(false);
          seek(e.duration - 1 / 30);
          return;
        }
        setTime(Math.max(0, t));
        const second = videos.current[1];
        if (
          second &&
          Math.abs(second.currentTime - e.cameras[1].offset - t) > 0.08
        )
          second.currentTime = e.cameras[1].offset + t;
      }
      frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, e]);
  async function save(fn: () => Promise<any>, msg: string) {
    setBusy(true);
    await action(fn, msg);
    setBusy(false);
  }
  if (error) return <p role="alert">{error}</p>;
  if (!e) return <p role="status">Loading episode and source signals…</p>;
  const sample = e.samples.reduce(
    (best, s) =>
      Math.abs(s.timestamp - time) < Math.abs(best.timestamp - time) ? s : best,
    e.samples[0],
  );
  const names = e.info.features["observation.state"].names;
  return (
    <>
      <button className="text-button" onClick={back}>
        ← Episode catalog
      </button>
      <div className="heading">
        <div>
          <div className="eyebrow">
            EPISODE INSPECTOR / {String(id).padStart(3, "0")}
          </div>
          <h1>{e.task}</h1>
          <p>
            {f(e.duration)} seconds · {e.samples.length} samples ·{" "}
            {e.reviews[0]?.status || "Unreviewed"} · Outcome:{" "}
            {e.reviews[0]?.outcome || "unknown"}
          </p>
        </div>
        <span className="badge">Preserved source</span>
      </div>
      <div className="inspector-grid">
        <section
          className="inspection"
          aria-label="Video and signal inspection"
        >
          <div className="cameras">
            {e.cameras.map((c, i) => (
              <div className="camera" key={c.key}>
                <div className="camera-label">
                  <strong>{c.label.toUpperCase()}</strong>
                  <span>
                    {e.info.features[c.key].shape[1]} ×{" "}
                    {e.info.features[c.key].shape[0]} / {e.info.fps} FPS nominal
                  </span>
                </div>
                {decoded ? (
                  <img
                    alt={`${c.label} decoded source frame near ${f(time)} seconds`}
                    src={`/api/episodes/${id}/frame/${c.key}?time=${time.toFixed(5)}`}
                  />
                ) : (
                  <video
                    ref={(v) => {
                      videos.current[i] = v;
                    }}
                    src={c.url}
                    onError={() => {
                      setPlaying(false);
                      setMediaError(
                        "Preview unavailable. Check mounted storage and the import job; source signals remain available.",
                      );
                    }}
                    muted
                    playsInline
                    preload="auto"
                    aria-label={`${c.label} camera preview`}
                    onLoadedMetadata={() => {
                      if (videos.current[i])
                        videos.current[i]!.currentTime = c.offset + time;
                    }}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="transport">
            {mediaError && <p role="alert">{mediaError}</p>}
            <button
              disabled={!!mediaError}
              onClick={() => {
                setDecoded(false);
                setPlaying((p) => !p);
              }}
            >
              {playing ? "Pause" : "Play"}
            </button>
            <button
              aria-label="Previous sample"
              onClick={() => {
                setPlaying(false);
                seek(time - 1 / 30);
              }}
            >
              −1 sample
            </button>
            <button
              aria-label="Next sample"
              onClick={() => {
                setPlaying(false);
                seek(time + 1 / 30);
              }}
            >
              +1 sample
            </button>
            <label>
              Speed
              <select
                aria-label="Playback speed"
                value={speed}
                onChange={(ev) => setSpeed(Number(ev.target.value))}
              >
                <option value={0.25}>0.25×</option>
                <option value={0.5}>0.5×</option>
                <option value={1}>1×</option>
                <option value={2}>2×</option>
              </select>
            </label>
            <span className="time mono">
              {f(time)} / {f(e.duration)} s
            </span>
          </div>
          <label className="timeline">
            Episode time
            <input
              aria-label="Episode time"
              type="range"
              min="0"
              max={e.duration - 1 / 30}
              step={1 / 30}
              value={time}
              onChange={(ev) => {
                setPlaying(false);
                seek(Number(ev.target.value));
              }}
            />
          </label>
          <div className="finding-marks">
            {e.findings.map((f) => (
              <button
                key={f.id}
                style={{
                  marginLeft: Math.min(80, (f.start / e.duration) * 100) + "%",
                }}
                onClick={() => {
                  setIssue(f);
                  seek(f.start);
                }}
              >
                {f.rule} at {f.start.toFixed(2)} s
              </button>
            ))}
          </div>
          <div className="inspection-options">
            <label>
              <input
                type="checkbox"
                checked={decoded}
                onChange={(ev) => {
                  setPlaying(false);
                  setDecoded(ev.target.checked);
                }}
              />{" "}
              Decode original frame near cursor
            </label>
            <span>
              Preview seeks are approximate. Physical synchronization is
              unknown.
            </span>
          </div>
          <div className="section-heading">
            <h2>Robot signals</h2>
            <label>
              Dimension
              <select
                value={dimension}
                onChange={(ev) => setDimension(Number(ev.target.value))}
              >
                {names.map((n: string, i: number) => (
                  <option key={n} value={i}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Plot
            samples={e.samples}
            field="observation.state"
            dimension={dimension}
            time={time}
            duration={e.duration}
            onSeek={seek}
          />
          <Plot
            samples={e.samples}
            field="action"
            dimension={dimension}
            time={time}
            duration={e.duration}
            onSeek={seek}
          />
          <details>
            <summary>
              Numeric sample at {f(sample.timestamp)} s · frame{" "}
              {sample.frame_index}
            </summary>
            <table>
              <thead>
                <tr>
                  <th scope="col">Feature</th>
                  <th scope="col">State</th>
                  <th scope="col">Action</th>
                </tr>
              </thead>
              <tbody>
                {names.map((n: string, i: number) => (
                  <tr key={n}>
                    <th scope="col">{n}</th>
                    <td>{f(sample["observation.state"][i])}</td>
                    <td>{f(sample.action[i])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </section>
        <aside className="detail-panel">
          <h2>Quality findings</h2>
          {e.findings.length === 0 ? (
            <p>
              No findings under the implemented rules. This does not establish
              task success or physical synchronization.
            </p>
          ) : (
            e.findings.map((f) => (
              <button
                className="issue"
                key={f.id}
                onClick={() => {
                  setIssue(f);
                  seek(f.start);
                }}
              >
                {f.severity}: {f.rule}
              </button>
            ))
          )}
          {issue && (
            <div className="issue-detail">
              <h3>{issue.rule}</h3>
              <p>{issue.explanation}</p>
              <p>Observed: {issue.observed}</p>
              <p>Threshold: {issue.threshold}</p>
            </div>
          )}
          <h2>Episode review</h2>
          <form
            onSubmit={(ev) => {
              ev.preventDefault();
              save(
                () =>
                  api(`/episodes/${id}/review`, { status, outcome, reason }),
                "Review recorded with history.",
              );
            }}
          >
            <label>
              Review decision
              <select
                value={status}
                onChange={(ev) => setStatus(ev.target.value)}
              >
                <option value="accepted">Accept</option>
                <option value="excluded">Exclude</option>
                <option value="unreviewed">Unreviewed</option>
              </select>
            </label>
            <label>
              Task outcome
              <select
                value={outcome}
                onChange={(ev) => setOutcome(ev.target.value)}
              >
                <option value="unknown">Unknown</option>
                <option value="success">Success</option>
                <option value="failure">Failure</option>
              </select>
            </label>
            <label>
              Review reason
              <textarea
                required
                value={reason}
                onChange={(ev) => setReason(ev.target.value)}
              />
            </label>
            <button className="primary" disabled={busy}>
              Save review
            </button>
          </form>
          <h2>Interval annotation</h2>
          <form
            onSubmit={(ev) => {
              ev.preventDefault();
              save(
                () =>
                  api(`/episodes/${id}/annotations`, {
                    start: Number(start),
                    end: Number(end),
                    label,
                    note,
                  }),
                "Interval annotation saved.",
              );
            }}
          >
            <div className="pair">
              <label>
                Start (s)
                <input
                  type="number"
                  step=".01"
                  min="0"
                  max={e.duration}
                  value={start}
                  onChange={(ev) => setStart(ev.target.value)}
                />
              </label>
              <label>
                End (s)
                <input
                  type="number"
                  step=".01"
                  min="0"
                  max={e.duration}
                  value={end}
                  onChange={(ev) => setEnd(ev.target.value)}
                />
              </label>
            </div>
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setStart(time.toFixed(2));
                setEnd(Math.min(time + 1, e.duration).toFixed(2));
              }}
            >
              Use cursor to cursor + 1 s
            </button>
            <label>
              Interval label
              <input
                required
                value={label}
                onChange={(ev) => setLabel(ev.target.value)}
                placeholder="e.g. grasp approach"
              />
            </label>
            <label>
              Notes
              <textarea
                value={note}
                onChange={(ev) => setNote(ev.target.value)}
              />
            </label>
            <button disabled={busy}>Save annotation</button>
          </form>
          {e.annotations.map((a) => (
            <p className="annotation" key={a.id}>
              <strong>{a.label}</strong> {f(a.start)} to {f(a.end)} s<br />
              {a.note}
            </p>
          ))}
          <details>
            <summary>Review history ({e.reviews.length})</summary>
            {e.reviews.map((r) => (
              <p key={r.id}>
                {r.status}: {r.reason}
                <br />
                <small>{r.created}</small>
              </p>
            ))}
          </details>
          <details>
            <summary>Source provenance and features</summary>
            <p>{e.info.robot_type}; declared source type retained.</p>
            <p>
              Revision <code>f641879e22172be7e8161d5e6c1503c2d2feb657</code>
            </p>
            <p>
              State/action: float32, six dimensions each. Units, coordinate
              frames and physical action semantics: unknown.
            </p>
            <p>
              Source rows [{e.metadata.dataset_from_index},{" "}
              {e.metadata.dataset_to_index}).
            </p>
            {e.cameras.map((c) => (
              <p key={c.key}>
                {c.label} video offset: {f(c.offset)} s
              </p>
            ))}
          </details>
        </aside>
      </div>
    </>
  );
}
function useData(path: string, revision: number) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api(path)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [path, revision]);
  return { data, error };
}
function useSelectionPreview(criteria: any, revision: number) {
  const [data, setData] = useState<any>(null);
  const key = JSON.stringify(criteria);
  useEffect(() => {
    let live = true;
    api("/selections/preview", JSON.parse(key)).then((v) => {
      if (live) setData(v);
    });
    return () => {
      live = false;
    };
  }, [key, revision]);
  return { data };
}
function Selections({
  revision,
  action,
}: {
  revision: number;
  action: Action;
}) {
  const { data, error } = useData("/selections", revision);
  const [name, setName] = useState("");
  const [review, setReview] = useState("");
  const preview = useSelectionPreview({ review, valid_only: true }, revision);
  return (
    <>
      <div className="eyebrow">CURATION</div>
      <h1>Saved selections</h1>
      <p>
        Save criteria for later evaluation. A saved query is separate from
        immutable version membership.
      </p>
      <form
        className="form-row"
        onSubmit={(e) => {
          e.preventDefault();
          action(
            () =>
              api("/selections", {
                name,
                criteria: { review, valid_only: true },
              }),
            "Selection saved.",
          );
        }}
      >
        <label>
          Selection name
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          Review filter
          <select value={review} onChange={(e) => setReview(e.target.value)}>
            <option value="">All reviews</option>
            <option value="accepted">Accepted</option>
            <option value="unreviewed">Unreviewed</option>
          </select>
        </label>
        <button>Save criteria</button>
      </form>
      <p>
        {preview.data
          ? `${preview.data.selected} selected; ${preview.data.excluded} excluded. Structural errors and excluded reviews cannot enter a version.`
          : "Loading selection preview…"}
      </p>
      {error && <p role="alert">{error}</p>}
      {data?.map((s: any) => (
        <article className="record" key={s.id}>
          <h2>{s.name}</h2>
          <code>{s.criteria}</code>
          <p>{s.created}</p>
        </article>
      ))}
    </>
  );
}
function Versions({ revision, action }: { revision: number; action: Action }) {
  const { data, error } = useData("/versions", revision);
  const selections = useData("/selections", revision);
  const [name, setName] = useState("");
  const [selection, setSelection] = useState("");
  const [selected, setSelected] = useState<any>(null);
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [comparison, setComparison] = useState<any>(null);
  return (
    <>
      <div className="eyebrow">REPRODUCIBLE DATASETS</div>
      <h1>Dataset versions</h1>
      <p>
        Freeze source membership, review history, split assignments and
        training-only statistics.
      </p>
      <form
        className="form-row"
        onSubmit={(e) => {
          e.preventDefault();
          const criteria = selection
            ? JSON.parse(
                selections.data.find((x: any) => String(x.id) === selection)
                  .criteria,
              )
            : { valid_only: true };
          action(async () => {
            const v = await api("/versions", { name, criteria, seed: 17 });
            setSelected({ ...(await api("/versions/" + v.id)), id: v.id });
          }, "Immutable version published.");
        }}
      >
        <label>
          Version name
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          Selection
          <select
            aria-label="Selection"
            value={selection}
            onChange={(e) => setSelection(e.target.value)}
          >
            <option value="">All usable, non-excluded episodes</option>
            {selections.data?.map((s: any) => (
              <option value={s.id} key={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <button className="primary">Create version</button>
      </form>
      {error && <p role="alert">{error}</p>}
      <div className="version-grid">
        <section>
          {data?.length === 0 && (
            <p>
              No versions yet. Import at least three independent episode groups.
            </p>
          )}
          {data?.map((v: any) => (
            <button
              className="version-record"
              key={v.id}
              onClick={() =>
                action(
                  async () =>
                    setSelected({
                      ...(await api("/versions/" + v.id)),
                      id: v.id,
                    }),
                  "Version loaded.",
                )
              }
            >
              <strong>{v.name}</strong>
              <code>{v.id.slice(0, 12)}</code>
              <span>{v.created}</span>
            </button>
          ))}
        </section>
        {selected && (
          <section className="panel">
            <h2>{selected.name}</h2>
            <p>
              {selected.episodes.length} episodes · seed {selected.split.seed}
            </p>
            <div className="split-bar">
              {Object.entries(selected.split.membership).map(([k, v]: any) => (
                <span key={k} style={{ flex: v.length }}>
                  {k}: {v.length}
                </span>
              ))}
            </div>
            <p>Whole-episode groups. Session identity is unknown.</p>
            <button
              onClick={() =>
                action(
                  () =>
                    api("/jobs", {
                      kind: "verify",
                      version: selected.id || data[0].id,
                    }),
                  "Consumer verification queued. Inspect Jobs for progress.",
                )
              }
            >
              Verify consumer
            </button>
            <details>
              <summary>Split membership</summary>
              {Object.entries(selected.split.membership).map(([k, v]: any) => (
                <p key={k}>
                  <strong>{k}</strong>: {v.join(", ")}
                </p>
              ))}
            </details>
            <details>
              <summary>Manifest and provenance</summary>
              <pre tabIndex={0} aria-label="Recorded JSON data">
                {JSON.stringify(selected, null, 2)}
              </pre>
            </details>
          </section>
        )}
      </div>
      <h2>Compare versions</h2>
      <div className="form-row">
        {[
          ["Earlier version", left, setLeft],
          ["Later version", right, setRight],
        ].map(([label, value, set]: any) => (
          <label key={label}>
            {label}
            <select
              aria-label={label}
              value={value}
              onChange={(e) => set(e.target.value)}
            >
              <option value="">Choose version</option>
              {data?.map((v: any) => (
                <option key={v.id} value={v.id}>
                  {v.name} ({v.id.slice(0, 8)})
                </option>
              ))}
            </select>
          </label>
        ))}
        <button
          disabled={!left || !right}
          onClick={() =>
            action(
              async () =>
                setComparison(
                  await api(`/compare?left=${left}&right=${right}`),
                ),
              "Comparison ready.",
            )
          }
        >
          Compare
        </button>
      </div>
      {comparison && (
        <div className="panel">
          <p>Added: {comparison.added.join(", ") || "none"}</p>
          <p>Removed: {comparison.removed.join(", ") || "none"}</p>
          <p>
            Changed configuration:{" "}
            {comparison.configuration_changed.join(", ") || "none"}
          </p>
        </div>
      )}
    </>
  );
}
function Jobs({ revision, action }: { revision: number; action: Action }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 2000);
    return () => clearInterval(timer);
  }, []);
  const { data, error } = useData("/jobs", revision + tick);
  return (
    <>
      <div className="eyebrow">LOCAL WORKER</div>
      <h1>Job history</h1>
      <p>
        One worker processes one job at a time. Queueing does not start a
        worker.
      </p>
      {error && <p role="alert">{error}</p>}
      {data?.map((j: any) => (
        <article className="record" key={j.id}>
          <div className="section-heading">
            <h2>
              {j.kind} <code>{j.id.slice(0, 8)}</code>
            </h2>
            <span className={"badge " + (j.state === "failed" ? "bad" : "")}>
              {j.state}
            </span>
          </div>
          <p>
            Stage: {j.stage} · Completed units: {j.completed} / {j.total}
          </p>
          {j.error && <p className="error">{j.error}</p>}
          <small>{j.updated}</small>
          {["running", "queued"].includes(j.state) ? (
            <button
              onClick={() =>
                action(
                  () => api(`/jobs/${j.id}/cancel`, {}),
                  "Cancellation requested at the next safe boundary.",
                )
              }
            >
              Cancel
            </button>
          ) : ["failed", "interrupted", "cancelled"].includes(j.state) ? (
            <button
              onClick={() =>
                action(() => api(`/jobs/${j.id}/retry`, {}), "Retry queued.")
              }
            >
              Retry
            </button>
          ) : null}
        </article>
      ))}
    </>
  );
}
function Verification({ revision }: { revision: number }) {
  const { data, error } = useData("/verifications", revision);
  return (
    <>
      <div className="eyebrow">CONSUMER EVIDENCE</div>
      <h1>Verification results</h1>
      <p>
        Actual signal windows and original RGB decoding. Custom consumer results
        do not establish LeRobot reader compatibility.
      </p>
      {error && <p role="alert">{error}</p>}
      {data?.length === 0 && (
        <p>
          No completed verification. Select a dataset version and run its
          consumer check.
        </p>
      )}
      {data?.map((v: any) => {
        const r = JSON.parse(v.result);
        return (
          <article className="record" key={v.id}>
            <h2>
              {r.status} · version {v.version.slice(0, 12)}
            </h2>
            <p>
              {r.episodes} episodes · {r.validated_signal_windows} signal
              windows · {r.decoded_images} decoded images
            </p>
            <p>
              Elapsed {r.seconds.toFixed(2)} s · {r.cache_condition}
            </p>
            <pre tabIndex={0} aria-label="Recorded JSON data">
              {JSON.stringify(r.batch_shapes, null, 2)}
            </pre>
            <p>{r.decoded_window_policy}</p>
            <small>{v.created}</small>
          </article>
        );
      })}
    </>
  );
}
function Faults() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  return (
    <section className="panel">
      <h2>Controlled fault laboratory</h2>
      <p>
        Deterministic injected faults in memory. These are not defects
        discovered in the preserved recordings.
      </p>
      <button
        onClick={() =>
          api("/fixtures")
            .then(setData)
            .catch((e) => setError(String(e)))
        }
      >
        Run labelled fault checks
      </button>
      {error && <p role="alert">{error}</p>}
      {data?.map((x: any) => (
        <article className="record" key={x.name}>
          <h3>Injected: {x.name}</h3>
          <p>Detected: {x.rules.join(", ")}</p>
          {x.findings.map((f: any, i: number) => (
            <p key={i}>
              {f.rule} at {f.start.toFixed(2)} s: {f.explanation}
            </p>
          ))}
        </article>
      ))}
    </section>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
