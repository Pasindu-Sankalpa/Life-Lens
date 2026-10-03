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
    api.sessions().then(setSessions).catch(() => setError("The LifeLens service is not running yet."));
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
            <strong>LifeLens</strong>
            <small style={{ display: "block" }}>Your life insurance, explained</small>
          </div>
        </div>
      </header>
      <section className="hero">
        <div>
          <p className="kicker">Private model · deterministic math · Lincoln notes</p>
          <h1>Don’t give me a number. Show me what it protects.</h1>
          <p className="lede">
            LifeLens turns a conversation about your household into a coverage timeline, a protection gap, and a plain-language account of every dollar. The language model listens. The coverage engine does the arithmetic.
          </p>
          <p className="quote">“LLM talks. Code decides. Sources teach.”</p>
        </div>
        <div className="trust">
          <article><span>Private</span>Conversation runs on a self-hosted Qwen model on this machine’s GPU.</article>
          <article><span>Grounded</span>Product education comes from curated notes linked to Lincoln’s public pages.</article>
          <article><span>Deterministic</span>Every coverage figure is reproducible from the formula on the plan.</article>
          <article><span>Transparent</span>Assumptions, skips, and placeholders stay visible and editable.</article>
        </div>
      </section>
      <section className="modes">
        <button className="mode" onClick={() => start("quick")}>
          <span>Quick estimate</span>
          <h2>Tell me in your own words</h2>
          <p>One or two sentences. LifeLens extracts what you actually said and asks only for the gaps.</p>
        </button>
        <button className="mode" onClick={() => start("guided")}>
          <span>Guide me</span>
          <h2>One question at a time</h2>
          <p>Each question explains why it matters. You can still answer in a full sentence.</p>
        </button>
      </section>
      <section className="steps">
        {["Tell me about your life", "Your life map", "Protection gap", "Why this number", "What-if lab", "Coverage options"].map((title, index) => (
          <div key={title}><strong>0{index + 1}</strong>{title}</div>
        ))}
      </section>
      <section className="recent">
        <h2 className="section-title">Recent plans</h2>
        {error && <p className="banner">{error}</p>}
        {sessions.length === 0 && !error && <p className="muted">No saved plans yet.</p>}
        {sessions.map((session) => (
          <Link key={session.id} href={`/workspace/${session.id}`}>
            <span>{session.title}</span>
            <span>{session.gap == null ? session.mode : compact(session.gap)}</span>
          </Link>
        ))}
      </section>
      <p className="disclaimer">
        LifeLens is an educational needs analysis. It does not quote premiums, underwrite, or recommend a product. Talk with a licensed financial professional before acting.
      </p>
    </main>
  );
}
