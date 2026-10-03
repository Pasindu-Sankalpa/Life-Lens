"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { EVENTS, SAMPLE, WHAT_IFS, compact, money } from "@/lib/format";
import type { AppState, Calculation, Fact, Health, Question, StressSample, TimelinePoint } from "@/lib/types";

export default function Workspace({ sessionId }: { sessionId: string }) {
  const [state, setState] = useState<AppState | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [exactStress, setExactStress] = useState<StressSample | null>(null);

  useEffect(() => {
    api.get(sessionId).then(setState).catch((reason) => setError(String(reason.message || reason)));
    api.health().then(setHealth).catch(() => undefined);
  }, [sessionId]);

  async function run(action: () => Promise<AppState>) {
    setBusy(true);
    setError("");
    try {
      const next = await action();
      setState(next);
      setExactStress(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (!state) {
    return <main className="landing"><p>{error || "Opening your plan…"}</p></main>;
  }

  const calc = state.calculation;
  const questions = state.questions.length ? state.questions : state.messages.at(-1)?.payload.questions || [];

  return (
    <div className="app-shell">
      <header className="topbar no-print">
        <Link href="/" className="brand">
          <div className="mark" aria-hidden><span /></div>
          <div>
            <strong>LifeLens</strong>
            <small style={{ display: "block" }}>{state.session.mode === "guided" ? "Guided" : "Quick estimate"} · {state.session.title}</small>
          </div>
        </Link>
        <div className="top-actions">
          <span className="pill">{health?.llm.reachable ? "Qwen on GPU 0" : "Model warming up"}</span>
          <button className="ghost" onClick={() => run(() => api.mode(sessionId, state.session.mode === "quick" ? "guided" : "quick"))}>
            Switch to {state.session.mode === "quick" ? "guided" : "quick"}
          </button>
          <button className="ghost" onClick={() => window.print()}>Take this plan with you</button>
        </div>
      </header>
      <main className="workspace">
        <section className="conversation no-print">
          <div className="thread">
            {state.messages.map((message) => (
              <article key={message.id} className={`bubble ${message.role}`}>
                {message.content}
                {message.role === "assistant" && <WhyList questions={message.payload.questions || []} />}
                {message.role === "assistant" && <NoteList notes={message.payload.notes || []} />}
                {message.role === "assistant" && message.payload.tools && message.payload.tools.length > 0 && (
                  <details className="tools">
                    <summary>Tools this turn</summary>
                    {message.payload.tools.map((tool, index) => (
                      <div key={`${tool.name}-${index}`}>{tool.name} · {tool.status}{tool.source ? ` · ${tool.source}` : ""}</div>
                    ))}
                  </details>
                )}
              </article>
            ))}
          </div>
          {questions.length > 0 && (
            <div className="why-card">
              {questions.map((question) => (
                <p key={question.key}><strong>{question.prompt}</strong><br /><span className="hint">{question.hint}</span></p>
              ))}
              <WhyList questions={questions} open />
            </div>
          )}
          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault();
              if (!draft.trim()) return;
              const content = draft;
              setDraft("");
              void run(() => api.message(sessionId, content));
            }}
          >
            <textarea
              value={draft}
              placeholder="Tell me about your household, or ask a what-if."
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <div className="row">
              <button className="btn" disabled={busy} type="submit">{busy ? "Working…" : "Send"}</button>
              <button className="ghost" type="button" onClick={() => setDraft(SAMPLE)}>Use a sample story</button>
            </div>
            {error && <p className="banner warn">{error}</p>}
          </form>
        </section>
        <section className="map">
          {state.active_scenario && (
            <div className="banner warn">
              <strong>Preview · {state.active_scenario.label}.</strong> Gap {compact(state.active_scenario.base_gap)} → {compact(state.active_scenario.scenario_gap)}. The saved plan is unchanged.
              <div className="row" style={{ marginTop: 8 }}>
                <button className="btn" disabled={busy} onClick={() => run(() => api.apply(sessionId, state.active_scenario!.id))}>Keep this change</button>
                <button className="ghost" disabled={busy} onClick={() => run(() => api.discard(sessionId, state.active_scenario!.id))}>Discard</button>
              </div>
              {state.active_scenario.note && <p>{state.active_scenario.note}</p>}
            </div>
          )}
          {!calc.ready ? <EmptyMap /> : <Plan calc={calc} state={state} sessionId={sessionId} busy={busy} run={run} exactStress={exactStress} setExactStress={setExactStress} />}
          <p className="disclaimer">
            {health?.disclaimer || "Educational estimate only. Not a premium, an illustration, or a product recommendation."}
            {state.profile.monthly_budget_preference != null && ` Monthly budget preference on file: ${money(state.profile.monthly_budget_preference)}. That preference is not converted into a premium.`}
          </p>
        </section>
      </main>
    </div>
  );
}

function Plan({
  calc, state, sessionId, busy, run, exactStress, setExactStress,
}: {
  calc: Calculation;
  state: AppState;
  sessionId: string;
  busy: boolean;
  run: (action: () => Promise<AppState>) => Promise<void>;
  exactStress: StressSample | null;
  setExactStress: (sample: StressSample | null) => void;
}) {
  const horizon = calc.timeline.horizon || 1;
  const [offset, setOffset] = useState(0);
  const point = calc.timeline.points[Math.min(offset, calc.timeline.points.length - 1)] || calc.timeline.points[0];
  const samples = calc.stress_samples;
  const initialIndex = useMemo(() => closestIndex(samples, calc.gap), [samples, calc.gap]);
  const [stressIndex, setStressIndex] = useState(initialIndex);
  useEffect(() => setStressIndex(initialIndex), [initialIndex]);
  const stress = exactStress || samples[stressIndex];
  const widthBase = Math.max(calc.gross_need, 1);

  return (
    <>
      <section className="hero-gap card">
        <div>
          <p className="kicker">Estimated protection gap</p>
          <p className="gap-num">{compact(calc.gap)}</p>
          <p>{compact(calc.gap_low)} – {compact(calc.gap_high)}. {calc.band_note}</p>
          {calc.completeness === "partial" && <p className="banner">Still open: {calc.missing.filter((item) => item.essential).map((item) => item.label).join(", ") || "a few details"}.</p>}
        </div>
        <div>
          <p className="kicker">What this amount protects</p>
          {calc.gap_allocation.length === 0 && <p>Existing resources cover the needs currently on the plan.</p>}
          {calc.gap_allocation.map((item) => (
            <div key={item.key} className="alloc">
              <strong>{compact(item.amount)}</strong> {item.label}
              <div className="hint">{item.blurb}</div>
            </div>
          ))}
          <p className="hint">{calc.resource_order_note}</p>
        </div>
      </section>

      <section className="panel" id="why">
        <h2 className="section-title">Why this number?</h2>
        {calc.components.map((row) => (
          <div className="bar-row" key={row.key}>
            <span>{row.label}</span>
            <div className="track"><span className={row.key} style={{ width: `${(row.amount / widthBase) * 100}%` }} /></div>
            <strong>+ {money(row.amount)}</strong>
            <span className="hint" style={{ gridColumn: "1 / -1" }}>{row.detail}</span>
          </div>
        ))}
        <p>Total need {money(calc.gross_need)}</p>
        {calc.resources.map((row) => (
          <div className="bar-row" key={row.key}>
            <span>{row.label}</span>
            <div className="track"><span className="existing" style={{ width: `${(row.amount / widthBase) * 100}%` }} /></div>
            <strong className="negative">− {money(row.amount)}</strong>
          </div>
        ))}
        <p><strong>Estimated coverage gap {money(calc.gap)}</strong></p>
        <details>
          <summary>Formula</summary>
          <p>{calc.formula}</p>
        </details>
        <CoverageBar existing={calc.total_resources} need={calc.gross_need} />
      </section>

      <section className="panel" id="map">
        <h2 className="section-title">Your coverage timeline</h2>
        <div className="year-readout">
          <span>{calc.timeline.start_year}</span>
          <strong>{point ? `${point.calendar_year} · need ${compact(point.need)} · gap ${compact(point.gap)}` : ""}</strong>
          <span>{calc.timeline.start_year + horizon}</span>
        </div>
        <input className="scrub" type="range" min={0} max={horizon} value={offset} aria-label="Move forward in time" onChange={(event) => setOffset(Number(event.target.value))} />
        <div className="gantt">
          {calc.timeline.rows.map((row) => (
            <div className="gantt-row" key={row.key}>
              <span>{row.label}</span>
              <div className="gantt-line">
                <i className={row.tone} style={{ left: `${(row.start / horizon) * 100}%`, width: `${Math.max(((row.end - row.start) / horizon) * 100, 1.5)}%` }} />
              </div>
            </div>
          ))}
        </div>
        {point && <PointDetail point={point} />}
        <p className="hint">{calc.timeline.debt_note} {calc.timeline.existing_note}</p>
      </section>

      <section className="panel">
        <h2 className="section-title">Your need profile</h2>
        <p>{calc.need_profile.headline}</p>
        <div className="meters">
          <div className="meter"><span>Temporary protection</span><b>{calc.need_profile.temporary}</b></div>
          <div className="meter"><span>Lifelong protection</span><b>{calc.need_profile.lifelong}</b></div>
          <div className="meter"><span>Cash-value priority</span><b>{calc.need_profile.cash_value}</b></div>
        </div>
        {calc.need_profile.drivers.map((driver) => (
          <div key={driver.label} className="driver"><strong>{driver.label}</strong> · {driver.detail}</div>
        ))}
      </section>

      <section className="panel" id="assumptions">
        <h2 className="section-title">Assumptions I’m currently making</h2>
        {[...calc.facts, ...calc.assumptions].map((fact) => (
          <Assumption key={`${fact.key}-${fact.source}-${fact.value}`} fact={fact} profile={state.profile} disabled={busy} onSave={(patch) => run(() => api.profile(sessionId, patch))} />
        ))}
        <div className="row">
          <label>Monthly budget preference
            <input
              type="number"
              defaultValue={state.profile.monthly_budget_preference ?? ""}
              onBlur={(event) => {
                if (event.target.value === "") return;
                void run(() => api.profile(sessionId, { monthly_budget_preference: Number(event.target.value) }));
              }}
            />
          </label>
          <span className="hint">Recorded for a professional. Not turned into a premium.</span>
        </div>
        {state.profile.dependents.length > 0 && (
          <div>
            <h3>People on the plan</h3>
            {state.profile.dependents.map((dependent, index) => (
              <div className="row" key={dependent.id || index}>
                <span>{dependent.label}</span>
                <input
                  type="number"
                  aria-label={`${dependent.label} age`}
                  defaultValue={dependent.age ?? ""}
                  onBlur={(event) => saveDependents(state, index, { age: event.target.value === "" ? null : Number(event.target.value) }, run, sessionId)}
                />
                <input
                  type="number"
                  aria-label={`${dependent.label} education`}
                  defaultValue={dependent.education_goal ?? ""}
                  onBlur={(event) => saveDependents(state, index, { education_goal: event.target.value === "" ? null : Number(event.target.value), education_is_estimate: false }, run, sessionId)}
                />
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel" id="stress">
        <h2 className="section-title">Coverage stress test</h2>
        <p>Drag an amount. The checks come from the engine, in this order: mortgage, other debt, income support, education, lifelong goal.</p>
        {samples.length > 0 && (
          <>
            <input className="scrub" type="range" min={0} max={samples.length - 1} value={stressIndex} aria-label="Coverage amount" onChange={(event) => { setExactStress(null); setStressIndex(Number(event.target.value)); }} />
            <div className="row">
              {[500000, 750000, 1000000].map((amount) => (
                <button key={amount} className="chip" type="button" onClick={() => {
                  const index = closestIndex(samples, amount);
                  setStressIndex(index);
                  void api.stress(sessionId, amount).then((result) => setExactStress(result.sample)).catch(() => undefined);
                }}>{compact(amount)}</button>
              ))}
            </div>
          </>
        )}
        {stress && (
          <div>
            <p className="gap-num" style={{ fontSize: 42 }}>{compact(stress.coverage)}</p>
            {stress.items.map((item) => (
              <div className="check" key={item.label}>
                <i className={`dot ${item.status}`} />
                <span><strong>{item.label}</strong> · {item.detail}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel no-print" id="what-if">
        <h2 className="section-title">What-if lab</h2>
        <div className="cluster">
          {WHAT_IFS.map((prompt) => (
            <button key={prompt} className="chip" disabled={busy} onClick={() => run(() => api.message(sessionId, prompt))}>{prompt.replace("What if ", "").replace("?", "")}</button>
          ))}
        </div>
        <h3>Life event simulator</h3>
        <div className="events">
          {EVENTS.map((event) => (
            <button key={event.id} className="event" disabled={busy} onClick={() => run(() => api.event(sessionId, event.id))}>
              <strong>{event.label}</strong>
              <div className="hint">{event.detail}</div>
            </button>
          ))}
        </div>
      </section>

      <section className="panel compare" id="options">
        <h2 className="section-title">Coverage options for this timeline</h2>
        <p className="quote" style={{ fontSize: 26 }}>{calc.comparison.headline}</p>
        <p>{calc.comparison.summary}</p>
        <div className="columns">
          <article>
            <h3>{calc.comparison.term.title}</h3>
            <p>{calc.comparison.term.fit}</p>
            <ul>{calc.comparison.term.points.map((point) => <li key={point}>{point}</li>)}</ul>
          </article>
          <article>
            <h3>{calc.comparison.permanent.title}</h3>
            <p>{calc.comparison.permanent.fit}</p>
            <ul>{calc.comparison.permanent.points.map((point) => <li key={point}>{point}</li>)}</ul>
          </article>
        </div>
        <p>{calc.comparison.lincoln_note}</p>
        <div className="cluster">
          {calc.comparison.sources.map((source) => (
            <a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
          ))}
        </div>
      </section>

      <section className="panel" id="summary">
        <h2 className="section-title">Questions for a financial professional</h2>
        <ol className="questions">
          {calc.professional_questions.map((question) => <li key={question}>{question}</li>)}
        </ol>
        <p className="hint">Lincoln’s public pages send this conversation toward a financial professional. This summary is the handoff. It is not an application.</p>
      </section>
    </>
  );
}

function EmptyMap() {
  return (
    <section className="panel empty">
      <p className="kicker">Your life map</p>
      <h2 className="section-title">The picture starts with one honest sentence.</h2>
      <p>Income, a mortgage, children, debt, or coverage you already have. LifeLens will not invent the rest.</p>
    </section>
  );
}

function WhyList({ questions, open = false }: { questions: Question[]; open?: boolean }) {
  if (!questions.length) return null;
  return (
    <div>
      {questions.map((question) => (
        <details key={question.key} open={open}>
          <summary className="why">Why this matters</summary>
          <p className="why-card">{question.why}</p>
        </details>
      ))}
    </div>
  );
}

function NoteList({ notes }: { notes: { title: string; source_url: string; content: string }[] }) {
  if (!notes.length) return null;
  return (
    <div>
      {notes.map((note) => (
        <details key={note.title}>
          <summary>According to the LifeLens Lincoln notes · {note.title}</summary>
          <p className="note">{note.content}</p>
          <a href={note.source_url} target="_blank" rel="noreferrer">{note.source_url}</a>
        </details>
      ))}
    </div>
  );
}

function CoverageBar({ existing, need }: { existing: number; need: number }) {
  const ratio = need > 0 ? Math.min(existing / need, 1) : 0;
  return (
    <div>
      <div className="track" style={{ height: 18 }}><span className="existing" style={{ width: `${ratio * 100}%` }} /></div>
      <p>{money(existing)} existing resources · {money(need)} estimated need · {Math.round(ratio * 100)}%</p>
    </div>
  );
}

function PointDetail({ point }: { point: TimelinePoint }) {
  return (
    <p>
      In {point.calendar_year}: income support {money(point.income)}, mortgage {money(point.mortgage)}, education {money(point.education)}, other debt {money(point.debt)}, existing resources {money(point.existing)}.
    </p>
  );
}

function Assumption({ fact, profile, disabled, onSave }: { fact: Fact; profile: AppState["profile"]; disabled: boolean; onSave: (patch: Record<string, unknown>) => void }) {
  const raw = (profile as unknown as Record<string, unknown>)[fact.key];
  const numeric = typeof raw === "number";
  return (
    <div className="assumption">
      <span>{fact.label} · {fact.value}</span>
      <span className="pill">{fact.source}</span>
      {fact.editable && fact.key !== "income_replacement_percent" && fact.key !== "include_education" && fact.key !== "dependents" && fact.key !== "dependent_ages" && (numeric || raw == null) && (
        <input
          type="number"
          disabled={disabled}
          defaultValue={typeof raw === "number" ? raw : ""}
          aria-label={fact.label}
          onBlur={(event) => {
            if (event.target.value === "") return;
            onSave({ [fact.key]: Number(event.target.value) });
          }}
        />
      )}
      {fact.editable && fact.key === "income_replacement_percent" && typeof raw === "number" && (
        <input type="number" disabled={disabled} defaultValue={Math.round(raw * 100)} aria-label="Replacement percent" onBlur={(event) => onSave({ income_replacement_percent: Number(event.target.value) })} />
      )}
      {fact.key === "include_education" && (
        <button className="chip" type="button" disabled={disabled} onClick={() => onSave({ include_education: profile.include_education === false })}>
          {profile.include_education === false ? "Include education" : "Leave education out"}
        </button>
      )}
    </div>
  );
}

function closestIndex(samples: StressSample[], amount: number) {
  if (!samples.length) return 0;
  let best = 0;
  let distance = Infinity;
  samples.forEach((sample, index) => {
    const next = Math.abs(sample.coverage - amount);
    if (next < distance) {
      distance = next;
      best = index;
    }
  });
  return best;
}

function saveDependents(
  state: AppState,
  index: number,
  patch: { age?: number | null; education_goal?: number | null; education_is_estimate?: boolean },
  run: (action: () => Promise<AppState>) => Promise<void>,
  sessionId: string,
) {
  const dependents = state.profile.dependents.map((dependent, itemIndex) =>
    itemIndex === index ? { ...dependent, ...patch } : dependent,
  );
  const body: Record<string, unknown> = { dependents };
  if ("education_goal" in patch) body.include_education = true;
  void run(() => api.profile(sessionId, body));
}
