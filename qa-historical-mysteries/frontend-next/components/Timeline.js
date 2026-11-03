"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function Timeline({ events, kids = false }) {
  if (!events || !events.length) return <p className="vide">No dated events were found in these passages.</p>;
  return (
    <ol className={"timeline" + (kids ? " kids-timeline" : "")}>
      {events.map((e, i) => (
        <li key={`${e.year}-${i}`}>
          <span className="tl-year">{e.year_label}</span>
          <span className="tl-label">
            {e.label}
            {e.source ? <sup className="tl-src">[{e.source}]</sup> : null}
            {!kids && e.verified === true && (
              <span className="tl-ok" title="This date appears in the cited passage">
                ✓
              </span>
            )}
            {!kids && e.verified === false && (
              <span className="tl-warn" title="This date was not found in the passages: check it before using it">
                unverified
              </span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}

// Button + result: builds a timeline from the passages used for an answer.
export function TimelinePanel({ passages, audience = "standard", label = "Timeline", initial = null }) {
  const [events, setEvents] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function build() {
    setBusy(true);
    setError("");
    try {
      const d = await api("/timeline", { method: "POST", body: { passages, audience } });
      setEvents(d.events);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="timeline-panel">
      {events === null ? (
        <button type="button" className="secondaire" onClick={build} disabled={busy || !passages?.length}>
          {busy ? "Building…" : label}
        </button>
      ) : (
        <>
          <strong className="panel-title">{audience === "kids" ? "⏳ Hanni's time machine" : "Timeline"}</strong>
          <Timeline events={events} kids={audience === "kids"} />
        </>
      )}
      {error && <p className="erreur">{error}</p>}
    </div>
  );
}
