"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { compact } from "@/lib/format";

const trust = [
  {
    title: "No Sign-Up",
    body: "No account needed. Save or take your plan with you later.",
    icon: "zap",
  },
  {
    title: "Stay Private",
    body: "No Social Security number, bank details, or medical information needed.",
    icon: "shield",
  },
  {
    title: "Clear Numbers",
    body: "See what you told us, what we assumed, and how the estimate was worked out.",
    icon: "list",
  },
  {
    title: "Trusted Sources",
    body: "Insurance explanations link to public, reputable pages.",
    icon: "book",
  },
];

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
    <main className="home">
      <header className="home-bar">
        <strong className="home-wordmark">LincolnLens</strong>
        <small>Your life insurance, explained</small>
      </header>

      <section className="home-hero">
        <div>
          <p className="kicker">A conversation, then a clear picture</p>
          <h1>
            How much life insurance could <em>your family</em> need?
          </h1>
          <p className="lede">
            You don’t need to know anything about life insurance. A few questions about your family,
            income, and responsibilities, then a clear picture of where the estimate comes from.
          </p>
          <p className="hint">Takes about 3 minutes</p>
          <button className="btn large" onClick={() => start("guided")}>Start my estimate</button>
          <p className="alt-start">
            <button className="why" type="button" onClick={() => start("quick")}>
              Already know your numbers? Tell me everything at once
            </button>
          </p>
          <p className="hint">No account · No Social Security number · No medical information</p>
        </div>

        <div className="trust">
          {trust.map((item, index) => (
            <article key={item.title} className={index % 2 === 0 ? "trust-card primary" : "trust-card accent"}>
              <div className="trust-head">
                <span className="trust-icon" aria-hidden><Icon name={item.icon} /></span>
                <p>{item.title}</p>
              </div>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      {(sessions.length > 0 || error) && (
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
      )}

      <p className="home-disclaimer">
        Planning estimate, not a quote. LincolnLens does not determine eligibility, premiums,
        underwriting, or a policy.
      </p>
    </main>
  );
}

function Icon({ name }: { name: string }) {
  const common = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const paths: Record<string, ReactNode> = {
    zap: <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />,
    shield: <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />,
    list: (
      <>
        <path d="M10 6h11" /><path d="M10 12h11" /><path d="M10 18h11" />
        <path d="m3 6 1 1 2-2" /><path d="m3 12 1 1 2-2" /><path d="m3 18 1 1 2-2" />
      </>
    ),
    book: (
      <>
        <path d="M12 7v14" />
        <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" />
      </>
    ),
  };
  return <svg {...common}>{paths[name]}</svg>;
}
