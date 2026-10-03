"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { compact } from "@/lib/format";

export default function HomePage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<{ id: string; title: string; mode: string; gap: number | null }[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.sessions().then(setSessions).catch(() => setError("The LincolnLens service is not running yet."));
  }, []);

  async function start(mode: "quick" | "guided") {
    const state = await api.create(mode);
    router.push(`/workspace/${state.session.id}`);
  }

  return (
    <main className="landing">
      <header className="landing-bar">
        <div className="brand">
          <div className="mark" aria-hidden><span /></div>
          <div>
            <strong>LincolnLens</strong>
            <small style={{ display: "block" }}>Your life insurance, explained</small>
          </div>
        </div>
      </header>
      <section className="hero">
        <div>
          <p className="kicker">A conversation, then a clear picture</p>
          <h1>How much life insurance could your family need?</h1>
          <p className="lede">
            You don’t need to know anything about life insurance. A few questions about your family, income, and responsibilities, then a clear picture of where the estimate comes from.
          </p>
          <p className="hint">Takes about 3 minutes</p>
          <button className="btn" onClick={() => start("guided")}>Start my estimate</button>
          <p>
            <button className="why" type="button" onClick={() => start("quick")}>Already know your numbers? Tell me everything at once</button>
          </p>
          <p className="hint">No account · No Social Security number · No medical information</p>
        </div>
        <div className="trust">
          <article><span>No account needed</span>Start immediately. Save or take your plan with you later.</article>
          <article><span>Your information stays private</span>No Social Security number, bank details, or medical information needed.</article>
          <article><span>Every number explained</span>See what you told us, what we assumed, and how the estimate was worked out.</article>
          <article><span>Grounded in Lincoln resources</span>Insurance explanations link to Lincoln Financial’s public pages.</article>
        </div>
      </section>
      <section className="steps">
        {["Tell me about your life", "Your life map", "Protection gap", "Why this number", "What-if lab", "Coverage options"].map((title, index) => (
          <div key={title}><strong>0{index + 1}</strong>{title}</div>
        ))}
      </section>
      <section className="recent">
        <div className="row">
          <h2 className="section-title">Recent plans</h2>
          {sessions.length > 0 && (
            <button
              className="ghost"
              type="button"
              onClick={() => {
                if (!window.confirm("Clear every plan on this computer?")) return;
                void api.clear().then(() => setSessions([])).catch(() => setError("Could not clear the plans."));
              }}
            >
              Clear all
            </button>
          )}
        </div>
        {error && <p className="banner">{error}</p>}
        {sessions.length === 0 && !error && <p className="muted">No saved plans yet.</p>}
        {sessions.map((session) => (
          <div className="recent-row" key={session.id}>
            <Link href={`/workspace/${session.id}`}>
              <span>{session.title}</span>
              <span>{session.gap == null ? session.mode : compact(session.gap)}</span>
            </Link>
            <button
              className="ghost"
              type="button"
              aria-label={`Remove ${session.title}`}
              onClick={() => {
                void api.remove(session.id).then(() => setSessions((current) => current.filter((item) => item.id !== session.id)));
              }}
            >
              Remove
            </button>
          </div>
        ))}
      </section>
      <p className="disclaimer">
        Planning estimate, not a quote. LincolnLens does not determine eligibility, premiums, underwriting, or a policy.
      </p>
    </main>
  );
}
