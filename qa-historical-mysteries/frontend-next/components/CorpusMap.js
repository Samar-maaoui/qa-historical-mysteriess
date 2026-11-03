"use client";

import { useState } from "react";
import { api } from "@/lib/api";

const PALETTE = ["#6b4423", "#c08a2b", "#4d6b2a", "#a8442a", "#3a86a8", "#8e5cf5", "#b08d57", "#2e7d6b", "#c2185b", "#5d4037", "#7b8f3a", "#455a64"];

// Every passage of the corpus is a dot (2-D projection of its embedding), coloured by cluster.
export default function CorpusMap() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [hover, setHover] = useState(null);
  const [only, setOnly] = useState(null);

  async function load() {
    setBusy(true);
    setError("");
    try {
      setData(await api("/corpus/map"));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return (
      <div>
        <button type="button" className="secondaire" onClick={load} disabled={busy}>
          {busy ? "Loading…" : "Show the corpus map"}
        </button>
        {error && <p className="muted">{error}</p>}
      </div>
    );
  }
  return (
    <div className="corpus-map">
      <svg viewBox="-1.1 -1.1 2.2 2.2" role="img" aria-label="Map of the passages of the corpus, coloured by cluster">
        {data.points.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={-p.y}
            r={hover === i ? 0.03 : 0.013}
            fill={PALETTE[p.cluster % PALETTE.length]}
            opacity={only === null || only === p.cluster ? 0.8 : 0.08}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
      </svg>
      <div>
        <p className="muted">{hover !== null ? data.points[hover].nom : "Hover a dot to see its topic. Click a cluster to isolate it."}</p>
        <ul className="legend">
          {data.clusters.map((c) => (
            <li key={c.id}>
              <button type="button" className={"chip" + (only === c.id ? " on" : "")} onClick={() => setOnly(only === c.id ? null : c.id)} style={{ borderColor: PALETTE[c.id % PALETTE.length] }}>
                <span className="dot-inline" style={{ background: PALETTE[c.id % PALETTE.length] }} /> {c.label} ({c.size})
              </button>
            </li>
          ))}
        </ul>
        <p className="muted">Clusters that mix unrelated topics, or sparse regions, show where the corpus needs more articles.</p>
      </div>
    </div>
  );
}
