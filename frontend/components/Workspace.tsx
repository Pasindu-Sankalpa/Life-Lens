"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { EVENTS, SAMPLE, WHAT_IFS, compact, money } from "@/lib/format";
import type { AppState, Calculation, Fact, Health, Question, StressSample, TimelinePoint } from "@/lib/types";

export default function Workspace({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [state, setState] = useState<AppState | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [exactStress, setExactStress] = useState<StressSample | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [keptGoing, setKeptGoing] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [childCount, setChildCount] = useState(false);
  const [composerOpen, setComposerOpen] = useState(true);
  const [composerHeight, setComposerHeight] = useState(220);
  const composerRef = useRef<HTMLFormElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get(sessionId).then(setState).catch((reason) => setError(String(reason.message || reason)));
    api.health().then(setHealth).catch(() => undefined);
  }, [sessionId]);

  useEffect(() => {
    const thread = threadRef.current;
    if (!thread) return;
    thread.scrollTo({ top: thread.scrollHeight, behavior: "smooth" });
  }, [state?.messages.length, busy]);

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
      setChildCount(false);
    }
  }

  if (!state) {
    return (
      <main className="landing">
        <div className="bubble assistant waiting" role="status">
          <span className="lens-loader" aria-hidden="true" />
          <span>{error || "Opening your plan"}</span>
        </div>
      </main>
    );
  }

  const calc = state.calculation;

  return (
    <div className="app-shell">
      <header className="topbar no-print">
        <Link href="/" className="brand">
          <div>
            <strong>LincolnLens</strong>
            <small style={{ display: "block" }}>Private session</small>
          </div>
        </Link>
        <div className="top-actions">
          <span className="pill" title="Your household details stay on this computer. They are not sent to an outside AI service. This is not a login, and it is not a promise that every part of the computer is secure.">
            Kept on this computer
          </span>
          <button className="ghost" onClick={() => run(() => api.mode(sessionId, state.session.mode === "quick" ? "guided" : "quick"))}>
            {state.session.mode === "quick" ? "Guide me instead" : "Tell me everything at once"}
          </button>
          <button className="ghost" type="button" onClick={() => { setSaveOpen(true); setKeptGoing(false); }}>Sign in</button>
          {calc.ready && <button className="ghost" onClick={() => window.print()}>Take this plan with you</button>}
          {calc.ready && (
            <button className="ghost" type="button" onClick={() => setMoreOpen((open) => !open)}>Privacy & data</button>
          )}
          {calc.ready && moreOpen && (
            <button
              className="ghost"
              onClick={() => {
                if (!window.confirm("Delete this plan from this computer?")) return;
                void api.remove(sessionId).then(() => router.push("/"));
              }}
            >
              Delete this plan
            </button>
          )}
        </div>
      </header>
      <main className="workspace">
        <section className="conversation no-print">
          <Progress calc={calc} />
          <div className="thread" ref={threadRef}>
            {state.messages.map((message) => (
              <article key={message.id} className={`bubble ${message.role}`}>
                {message.content}
                {message.role === "assistant" && <WhyList questions={message.payload.questions || []} />}
                {message.role === "assistant" && <NoteList notes={message.payload.notes || []} />}
              </article>
            ))}
            {busy && (
              <div className="bubble assistant waiting" role="status">
                <span className="lens-loader" aria-hidden="true" />
                <span>Reading what you wrote</span>
              </div>
            )}
          </div>
          <form
            className={`composer${composerOpen ? "" : " collapsed"}`}
            ref={composerRef}
            style={composerOpen ? { height: composerHeight } : undefined}
            onSubmit={(event) => {
              event.preventDefault();
              if (!draft.trim()) return;
              const content = draft;
              setDraft("");
              void run(() => api.message(sessionId, content));
            }}
          >
            <div className="composer-handle">
              <button
                className="why"
                type="button"
                onPointerDown={(event) => {
                  if (!composerOpen) return;
                  event.preventDefault();
                  const startY = event.clientY;
                  const startH = composerRef.current?.offsetHeight ?? composerHeight;
                  const move = (ev: PointerEvent) => {
                    const next = Math.min(460, Math.max(140, startH - (ev.clientY - startY)));
                    setComposerHeight(next);
                  };
                  const up = () => {
                    window.removeEventListener("pointermove", move);
                    window.removeEventListener("pointerup", up);
                  };
                  window.addEventListener("pointermove", move);
                  window.addEventListener("pointerup", up);
                }}
              >
                Drag to resize
              </button>
              <button className="ghost" type="button" onClick={() => setComposerOpen((open) => !open)}>
                {composerOpen ? "Hide typing" : "Show typing"}
              </button>
            </div>
            {composerOpen && (
            <>
            <p className="hint">Prefer to type? Tell me in your own words.</p>
            <textarea
              value={draft}
              placeholder="For example: two kids, ages 3 and 7"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <div className="cluster">
              {(childCount ? countChips() : answerChips(state.session.last_question_key)).map((choice) => (
                <button
                  key={choice.label}
                  className="chip"
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    if (choice.message === "__children__") {
                      setChildCount(true);
                      return;
                    }
                    setChildCount(false);
                    void run(() => api.message(sessionId, choice.message));
                  }}
                >
                  {choice.label}
                </button>
              ))}
            </div>
            <div className="row">
              <button className="btn" disabled={busy} type="submit">{busy ? "Working…" : "Send"}</button>
              <button className="why" type="button" onClick={() => setDraft(SAMPLE)}>Not sure what to say? Try an example</button>
            </div>
            {error && <p className="banner warn">{error}</p>}
            <p className="hint">No account. No Social Security number, bank details, or medical information. What you type stays on this computer.</p>
            </>
            )}
          </form>
        </section>
        <section className="map">
          {state.active_scenario && (
            <div className="banner warn">
              <strong>{changeSentence(state.active_scenario.base_gap, state.active_scenario.scenario_gap)}</strong>
              <p>{compact(state.active_scenario.base_gap)} → {compact(state.active_scenario.scenario_gap)}. The saved plan is unchanged.</p>
              {state.active_scenario.note && <p>Why? {state.active_scenario.note}</p>}
              <div className="row" style={{ marginTop: 8 }}>
                <button className="btn" disabled={busy} onClick={() => run(() => api.apply(sessionId, state.active_scenario!.id))}>Keep this change</button>
                <button className="ghost" disabled={busy} onClick={() => run(() => api.discard(sessionId, state.active_scenario!.id))}>Discard</button>
              </div>
            </div>
          )}
          {saveOpen && (
            <SavePlan
              copied={linkCopied}
              onSave={() => {
                const link = window.location.href;
                void navigator.clipboard?.writeText(link).then(() => setLinkCopied(true)).catch(() => setLinkCopied(false));
                setLinkCopied(true);
              }}
              onContinue={() => { setSaveOpen(false); setKeptGoing(true); }}
            />
          )}
          {!calc.ready ? <GrowingMap profile={state.profile} /> : (
            <Plan
              calc={calc}
              state={state}
              sessionId={sessionId}
              busy={busy}
              run={run}
              exactStress={exactStress}
              setExactStress={setExactStress}
              showSave={!saveOpen && !keptGoing}
              onSave={() => setSaveOpen(true)}
              onContinue={() => setKeptGoing(true)}
            />
          )}
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
  calc, state, sessionId, busy, run, exactStress, setExactStress, showSave, onSave, onContinue,
}: {
  calc: Calculation;
  state: AppState;
  sessionId: string;
  busy: boolean;
  run: (action: () => Promise<AppState>) => Promise<void>;
  exactStress: StressSample | null;
  setExactStress: (sample: StressSample | null) => void;
  showSave: boolean;
  onSave: () => void;
  onContinue: () => void;
}) {
  const horizon = calc.timeline.horizon || 1;
  const [offset, setOffset] = useState(0);
  const point = calc.timeline.points[Math.min(offset, calc.timeline.points.length - 1)] || calc.timeline.points[0];
  const samples = calc.stress_samples;
  const initialIndex = useMemo(() => closestIndex(samples, calc.gap), [samples, calc.gap]);
  const [stressIndex, setStressIndex] = useState(initialIndex);
  const [view, setView] = useState<"number" | "why" | "time" | "explore" | "learn">("number");
  useEffect(() => setStressIndex(initialIndex), [initialIndex]);
  const stress = exactStress || samples[stressIndex];
  const widthBase = Math.max(calc.gross_need, 1);

  return (
    <>
      <section className="hero-gap card" id="result-top">
        <div>
          <p className="kicker">Additional protection to consider</p>
          <p className="gap-num">{compact(calc.gap)}</p>
          <p className="hint">Sometimes called a coverage gap.</p>
          <p>Estimated need {compact(calc.gross_need)}. Coverage you already mentioned {compact(calc.total_resources)}.</p>
          <p className="result-note"><strong>Planning estimate, not a quote.</strong> LincolnLens explores a need from the information and assumptions shown. It does not determine eligibility, premiums, underwriting, or a policy.</p>
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
      {showSave && (
        <section className="panel save-plan">
          <h2 className="section-title">Want to come back to this later?</h2>
          <p>This estimate is a guest plan. It has a random ID, not your name, and you can delete it. An account is optional.</p>
          <div className="row">
            <button className="btn" type="button" onClick={onSave}>Save my plan</button>
            <button className="ghost" type="button" onClick={onContinue}>Continue without an account</button>
          </div>
        </section>
      )}
      <div className="cluster">
        <button className={view === "why" ? "btn" : "chip"} type="button" onClick={() => setView(view === "why" ? "number" : "why")}>Show me where this comes from</button>
        <button className={view === "time" ? "btn" : "chip"} type="button" onClick={() => setView(view === "time" ? "number" : "time")}>See how this changes over time</button>
        <button className={view === "explore" ? "btn" : "chip"} type="button" onClick={() => setView(view === "explore" ? "number" : "explore")}>Try a different situation</button>
        <button className={view === "learn" ? "btn" : "chip"} type="button" onClick={() => setView(view === "learn" ? "number" : "learn")}>Learn about coverage types</button>
      </div>

      {view === "why" && calc.levers && calc.levers.length > 0 && (
        <section className="panel">
          <h2 className="section-title">Your biggest levers</h2>
          <p>These are the choices that move the estimate the most.</p>
          <ol>
            {calc.levers.map((lever) => (
              <li key={lever.title}><strong>{lever.title}.</strong> {lever.explanation}</li>
            ))}
          </ol>
        </section>
      )}

      {view === "why" && calc.income_assumption && (
        <section className="panel" id="income-assumption">
          <h2 className="section-title">Income-support assumption</h2>
          <p>{calc.income_assumption.headline}</p>
          <table className="ledger">
            <tbody>
              <tr><td>Annual income</td><td>{money(calc.income_assumption.annual_income)}</td></tr>
              <tr><td>Portion selected</td><td>{calc.income_assumption.percent}% · {sourceLabel(calc.income_assumption.percent_source)}</td></tr>
              <tr><td>Support period</td><td>{calc.income_assumption.years} yr · {sourceLabel(calc.income_assumption.years_source)}</td></tr>
              <tr><td>Income-support amount</td><td>{money(calc.income_assumption.amount)}</td></tr>
            </tbody>
          </table>
          <div className="row">
            <UpdateField
              label="Portion"
              aria="Change replacement percent"
              initial={calc.income_assumption.percent}
              disabled={busy}
              onUpdate={(value) => saveAndShow(run, () => api.profile(sessionId, { income_replacement_percent: Number(value) }))}
            />
            <UpdateField
              label="Years"
              aria="Change support years"
              initial={calc.income_assumption.years}
              disabled={busy}
              onUpdate={(value) => saveAndShow(run, () => api.profile(sessionId, { income_replacement_years: Number(value) }))}
            />
          </div>
        </section>
      )}

      {view === "why" && calc.provenance && calc.provenance.length > 0 && (
        <section className="panel" id="provenance">
          <h2 className="section-title">How LincolnLens built this estimate</h2>
          <p className="hint">● You told us &nbsp; ▲ A starting assumption &nbsp; ■ Worked out from those &nbsp; ◆ From Lincoln’s public pages</p>
          {calc.provenance.map((item) => (
            <div className="prov" key={`${item.mark}-${item.label}`}>
              <span>{markGlyph(item.mark)}</span>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
          <p className="hint">This plan is saved, so you can come back to the same estimate and the choices behind it.</p>
        </section>
      )}

      {view === "why" && <section className="panel" id="why">
        <h2 className="section-title">Why this number?</h2>
        {calc.build_steps && calc.build_steps.length > 0 && (
          <ul>{calc.build_steps.map((step) => <li key={step}>✓ {step}</li>)}</ul>
        )}
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
          <summary>How this adds up</summary>
          <p>{calc.formula}</p>
        </details>
        <CoverageBar existing={calc.total_resources} need={calc.gross_need} />
      </section>}

      {view === "time" && <section className="panel" id="map">
        <h2 className="section-title">Your coverage timeline</h2>
        <p>Each line is how long that part of the plan lasts. Drag the dot. The orange mark moves through the years, and anything already behind that year fades.</p>
        <div className="year-readout">
          <span>{calc.timeline.start_year}</span>
          <strong>{point ? `${point.calendar_year}` : ""}</strong>
          <span>{calc.timeline.start_year + horizon}</span>
        </div>
        <input className="scrub" type="range" min={0} max={horizon} value={offset} aria-label="Move forward in time" onChange={(event) => setOffset(Number(event.target.value))} />
        <div className="gantt">
          {calc.timeline.rows.map((row) => (
            <div className="gantt-row" key={row.key}>
              <span>{timelineLabel(row.label, row.tone)}</span>
              <div className="gantt-line">
                {barParts(row.start, row.end, offset, horizon).map((part) => (
                  <i key={`${part.left}-${part.faded}`} className={`${row.tone}${part.faded ? " faded" : ""}`} style={{ left: `${part.left}%`, width: `${Math.max(part.width, 1.2)}%` }} />
                ))}
                <span className="playhead" style={{ left: `${(offset / horizon) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
        {point && <PointDetail point={point} />}
      </section>}

      {view === "why" && <section className="panel">
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
      </section>}

      {view === "why" && <section className="panel" id="assumptions">
        <h2 className="section-title">Assumptions I’m currently making</h2>
        {[...calc.facts, ...calc.assumptions].map((fact) => (
          <Assumption key={`${fact.key}-${fact.source}-${fact.value}`} fact={fact} profile={state.profile} disabled={busy} onSave={(patch) => saveAndShow(run, () => api.profile(sessionId, patch))} />
        ))}
        <div className="row">
          <UpdateField
            label="Monthly budget preference"
            aria="Monthly budget preference"
            initial={state.profile.monthly_budget_preference ?? ""}
            disabled={busy}
            onUpdate={(value) => saveAndShow(run, () => api.profile(sessionId, { monthly_budget_preference: Number(value) }))}
          />
          <span className="hint">Recorded for a professional. Not turned into a premium.</span>
        </div>
        {state.profile.dependents.length > 0 && (
          <div>
            <h3>People on the plan</h3>
            {state.profile.dependents.map((dependent, index) => (
              <div className="row" key={dependent.id || index}>
                <span>{dependent.label}</span>
                <UpdateField
                  label="Age"
                  aria={`${dependent.label} age`}
                  initial={dependent.age ?? ""}
                  disabled={busy}
                  onUpdate={(value) => saveDependents(state, index, { age: value === "" ? null : Number(value) }, run, sessionId)}
                />
                <UpdateField
                  label="Education"
                  aria={`${dependent.label} education`}
                  initial={dependent.education_goal ?? ""}
                  disabled={busy}
                  onUpdate={(value) => saveDependents(state, index, { education_goal: value === "" ? null : Number(value), education_is_estimate: false }, run, sessionId)}
                />
              </div>
            ))}
          </div>
        )}
      </section>}

      {view === "explore" && <section className="panel" id="stress">
        <h2 className="section-title">Coverage stress test</h2>
        <p>Move the amount and see what it would cover first: the mortgage, other debt, income support, education, then any lifelong goal.</p>
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
      </section>}

      {view === "explore" && <section className="panel no-print" id="what-if">
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
      </section>}

      {view === "learn" && <section className="panel compare" id="options">
        <h2 className="section-title">Coverage options for this timeline</h2>
        <p className="quote" style={{ fontSize: 26 }}>{calc.comparison.headline}</p>
        <p>{calc.comparison.summary}</p>
        {calc.comparison.periods && (
          <div className="periods">
            {calc.comparison.periods.map((period) => (
              <article className="period" key={period.years}>
                <strong>{period.years} years</strong>
                <div className="hint">{period.relation}</div>
              </article>
            ))}
          </div>
        )}
        {calc.comparison.whole_life && (
          <article className="whole-card">
            <p className="kicker">{calc.comparison.whole_life.kicker}</p>
            <h3>{calc.comparison.whole_life.title}</h3>
            <p>{calc.comparison.whole_life.statement}</p>
          </article>
        )}
        {calc.comparison.lincoln_categories && (
          <div className="columns">
            <article>
              <h3>Term</h3>
              <ul>{calc.comparison.lincoln_categories.term.map((item) => <li key={item}>{item}</li>)}</ul>
            </article>
            <article>
              <h3>Permanent</h3>
              <ul>{calc.comparison.lincoln_categories.permanent.map((item) => <li key={item}>{item}</li>)}</ul>
            </article>
          </div>
        )}
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
      </section>}

      {view === "learn" && <section className="panel" id="summary">
        <h2 className="section-title">Questions for a financial professional</h2>
        <ol className="questions">
          {calc.professional_questions.map((question) => <li key={question}>{question}</li>)}
        </ol>
        <p className="hint">Lincoln’s public pages send this conversation toward a financial professional. This summary is the handoff. It is not an application.</p>
      </section>}
    </>
  );
}

function SavePlan({ copied, onSave, onContinue }: { copied: boolean; onSave: () => void; onContinue: () => void }) {
  const [link, setLink] = useState("");
  useEffect(() => setLink(window.location.href), []);
  return (
    <section className="panel save-plan">
      <p className="kicker">Optional · not required</p>
      <h2 className="section-title">Save my plan</h2>
      <p>
        This is a guest plan with a random ID. LincolnLens did not ask for your name, a password, a Social Security number, or medical information.
        You can keep using it, copy the link to open it again on this computer, or delete it.
      </p>
      <p>
        A future version could connect Save to an established sign-in service. This prototype does not store passwords.
      </p>
      {link && <p className="hint">{link}</p>}
      <div className="row">
        <button className="btn" type="button" onClick={onSave}>{copied ? "Link copied" : "Copy my plan link"}</button>
        <button className="ghost" type="button" onClick={onContinue}>Continue without an account</button>
      </div>
    </section>
  );
}

function GrowingMap({ profile }: { profile: AppState["profile"] }) {
  const kids = profile.dependents;
  const started = profile.dependents_confirmed || kids.length > 0 || profile.partner != null || profile.annual_income != null || profile.mortgage_balance != null;
  return (
    <section className="panel life-map">
      <p className="kicker">Your life map</p>
      <h2 className="section-title">{started ? "Your picture so far" : "Your picture starts with one simple answer."}</h2>
      {!started && (
        <>
          <div className="stations">
            {["Family", "Home", "Income", "Future"].map((name) => <span key={name}>{name}</span>)}
          </div>
          <p>As you answer, your life map will build here.</p>
        </>
      )}
      {started && (
        <ul className="life-list">
          <li><strong>You</strong>{profile.age ? `, ${profile.age}` : ""}{profile.partner ? " · partner in the household" : ""}</li>
          {kids.map((child) => (
            <li key={child.id || child.label}>
              {child.label}{child.age != null ? `, ${child.age}` : ""}
              {child.age != null ? ` · relies on you for about ${Math.max(0, 22 - child.age)} years` : " · age still needed"}
            </li>
          ))}
          {profile.annual_income != null && <li>Income · {money(profile.annual_income)} a year</li>}
          {profile.mortgage_balance != null && <li>Home · {profile.mortgage_balance === 0 ? "no mortgage" : `${money(profile.mortgage_balance)} still owed`}</li>}
          {profile.existing_employer_coverage != null && <li>Coverage through work · {money(profile.existing_employer_coverage)}</li>}
        </ul>
      )}
    </section>
  );
}

function WhyList({ questions, open = false }: { questions: Question[]; open?: boolean }) {
  if (!questions.length) return null;
  return (
    <div>
      {questions.map((question) => (
        <div key={question.key}>
          {question.hint && <p className="hint example">{question.hint}</p>}
          <details open={open}>
            <summary className="why">Why this matters</summary>
            <p className="why-card">{question.why}</p>
          </details>
        </div>
      ))}
    </div>
  );
}

function NoteList({ notes }: { notes: { title: string; source_name?: string; source_url: string; content: string; retrieved_at?: string }[] }) {
  if (!notes.length) return null;
  return (
    <div>
      {notes.map((note) => (
        <details key={note.title}>
          <summary>Source: {note.source_name} — {note.title}</summary>
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
  const pieces = [
    point.income ? `${money(point.income)} of income support` : "",
    point.mortgage ? `${money(point.mortgage)} still on the mortgage` : "",
    point.education ? `${money(point.education)} for education` : "",
    point.debt ? `${money(point.debt)} of other debt` : "",
    point.existing ? `${money(point.existing)} of coverage already in place` : "",
  ].filter(Boolean);
  return (
    <p>
      In {point.calendar_year}, the estimate is {money(point.need)}
      {point.gap !== point.need ? `, with ${money(point.gap)} still uncovered` : ""}.
      {pieces.length ? ` Still in the picture: ${pieces.join(", ")}.` : " The needs on this timeline have ended."}
    </p>
  );
}

function timelineLabel(label: string, tone: string) {
  if (tone === "income") return "Income support";
  if (tone === "mortgage") return "Mortgage";
  if (tone === "existing") return "Coverage you already have";
  if (tone === "child") return label.replace(/ dependent$/, " depends on you");
  if (tone === "college") return label.replace(/ college$/, " in college");
  return label;
}

function barParts(start: number, end: number, cursor: number, horizon: number) {
  const pct = (year: number) => (year / horizon) * 100;
  if (end <= start) return [];
  if (cursor <= start) return [{ left: pct(start), width: pct(end - start), faded: false }];
  if (cursor >= end) return [{ left: pct(start), width: pct(end - start), faded: true }];
  return [
    { left: pct(start), width: pct(cursor - start), faded: true },
    { left: pct(cursor), width: pct(end - cursor), faded: false },
  ];
}

function Assumption({ fact, profile, disabled, onSave }: { fact: Fact; profile: AppState["profile"]; disabled: boolean; onSave: (patch: Record<string, unknown>) => void }) {
  const raw = (profile as unknown as Record<string, unknown>)[fact.key];
  const numeric = typeof raw === "number";
  const editableNumber = fact.editable && fact.key !== "include_education" && fact.key !== "dependents" && fact.key !== "dependent_ages" && (numeric || raw == null);
  const initial = fact.key === "income_replacement_percent" && typeof raw === "number" ? Math.round(raw * 100) : (typeof raw === "number" ? raw : "");
  return (
    <div className="assumption">
      <span>{fact.label} · {fact.value}</span>
      <span className="pill">{fact.source}</span>
      {editableNumber && (
        <UpdateField
          aria={fact.label}
          initial={initial}
          disabled={disabled}
          onUpdate={(value) => onSave({ [fact.key]: Number(value) })}
        />
      )}
      {fact.key === "include_education" && (
        <button className="btn update" type="button" disabled={disabled} onClick={() => onSave({ include_education: profile.include_education === false })}>
          {profile.include_education === false ? "Include education" : "Leave education out"}
        </button>
      )}
    </div>
  );
}

function UpdateField({
  label,
  aria,
  initial,
  disabled,
  onUpdate,
}: {
  label?: string;
  aria: string;
  initial: string | number;
  disabled: boolean;
  onUpdate: (value: string) => void;
}) {
  const [value, setValue] = useState(String(initial ?? ""));
  useEffect(() => setValue(String(initial ?? "")), [initial]);
  return (
    <span className="update-field">
      {label && <span>{label}</span>}
      <input type="number" aria-label={aria} value={value} disabled={disabled} onChange={(event) => setValue(event.target.value)} />
      <button className="btn update" type="button" disabled={disabled || value.trim() === ""} onClick={() => onUpdate(value)}>
        Update
      </button>
    </span>
  );
}

async function saveAndShow(run: (action: () => Promise<AppState>) => Promise<void>, action: () => Promise<AppState>) {
  await run(action);
  document.getElementById("result-top")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function Progress({ calc }: { calc: Calculation }) {
  const missing = new Set(calc.missing.map((item) => item.key));
  const groups = [
    { label: "Family", keys: ["dependents", "dependent_ages"] },
    { label: "Income", keys: ["annual_income", "income_replacement_years"] },
    { label: "Home & debt", keys: ["mortgage_balance", "other_debt"] },
    { label: "Current coverage", keys: ["existing_employer_coverage"] },
    { label: "Future goals", keys: ["include_education"] },
  ];
  const index = groups.findIndex((group) => group.keys.some((key) => missing.has(key)));
  const step = index === -1 ? groups.length + 1 : index + 1;
  const names = [...groups.map((group) => group.label), "Your result"];
  return (
    <div className="progress" aria-label={`Step ${step} of ${names.length}`}>
      <div className="stepper">
        {names.map((name, item) => (
          <span key={name} className={item + 1 < step ? "done" : item + 1 === step ? "now" : ""}>{name}</span>
        ))}
      </div>
      <p>Step {step} of {names.length} · about 3 minutes</p>
    </div>
  );
}

function answerChips(key: string | null) {
  const unsure = { label: "I’m not sure", message: "I don't know" };
  if (key === "income_replacement_years") {
    return [
      { label: "3 years", message: "3 years of income support" },
      { label: "5 years", message: "5 years of income support" },
      { label: "10 years", message: "10 years of income support" },
      unsure,
    ];
  }
  if (key === "partner") return [{ label: "Yes", message: "Yes" }, { label: "No", message: "No" }, unsure];
  if (key === "mortgage_balance") return [{ label: "No mortgage", message: "No mortgage" }, unsure];
  if (key === "existing_employer_coverage" || key === "existing_personal_coverage" || key === "other_debt") {
    return [{ label: "None", message: "none" }, unsure];
  }
  if (key === "include_education") return [{ label: "Yes", message: "Yes, include education" }, { label: "No", message: "Leave education out" }, unsure];
  if (key === "dependents") {
    return [
      { label: "Spouse / partner", message: "My partner relies on me and I have no children" },
      { label: "Children", message: "__children__" },
      { label: "Parent / relative", message: "A parent relies on me" },
      { label: "Someone else", message: "Someone else relies on me" },
      { label: "No one", message: "No one else relies on me" },
      unsure,
    ];
  }
  return [unsure];
}

function countChips() {
  return [1, 2, 3, 4].map((count) => ({
    label: String(count),
    message: `${["one", "two", "three", "four"][count - 1]} children`,
  }));
}

function changeSentence(before: number, after: number) {
  const delta = after - before;
  if (delta < 0) return `Your estimate decreased by ${compact(-delta)}.`;
  if (delta > 0) return `Your estimate increased by ${compact(delta)}.`;
  return "Your estimate stays the same.";
}

function sourceLabel(source: string) {
  if (source === "user") return "you selected this";
  if (source === "assumption") return "starting assumption";
  if (source === "estimated") return "estimate";
  return source;
}

function markGlyph(mark: string) {
  if (mark === "user") return "●";
  if (mark === "assumption") return "▲";
  if (mark === "calculated") return "■";
  if (mark === "source") return "◆";
  return "○";
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
  void saveAndShow(run, () => api.profile(sessionId, body));
}
