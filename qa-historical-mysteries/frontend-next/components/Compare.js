"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { sourceTag } from "@/lib/text";

const PAIRS = [
  ["Carthage", "Kairouan"],
  ["Great Pyramid of Giza", "Machu Picchu"],
  ["Dougga", "El Jem"],
  ["Hannibal Barca", "Habib Bourguiba"],
];

// "[1]" markers become small superscripts
function Cited({ text }) {
  return (
    <>
      {String(text || "")
        .split(/(\[\d{1,2}(?:\s*[,;]\s*\d{1,2})*\])/g)
        .map((part, i) =>
          part.startsWith("[") ? (
            <sup key={i} className="tl-src">
              {part}
            </sup>
          ) : (
            part
          )
        )}
    </>
  );
}

export default function Compare() {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [audience, setAudience] = useState("standard");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(x = a, y = b) {
    if (!x.trim() || !y.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      setData(await api("/compare", { method: "POST", body: { a: x, b: y, audience } }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const kids = data && audience === "kids";

  return (
    <section className="panel">
      <h2 className="panel-h">Compare two subjects</h2>
      <p className="muted">Pick any two topics, people or places of the corpus. The comparison is built only from the retrieved passages.</p>
      <form
        className="compare-form"
        onSubmit={(e) => {
          e.preventDefault();
          run();
        }}
      >
        <input type="text" value={a} onChange={(e) => setA(e.target.value)} placeholder="First subject (e.g. Carthage)" maxLength={120} aria-label="First subject" />
        <span className="vs">vs</span>
        <input type="text" value={b} onChange={(e) => setB(e.target.value)} placeholder="Second subject (e.g. Kairouan)" maxLength={120} aria-label="Second subject" />
        <select value={audience} onChange={(e) => setAudience(e.target.value)} aria-label="Level of explanation">
          <option value="standard">Standard</option>
          <option value="kids">Kids (simple words)</option>
        </select>
        <button type="submit" disabled={busy || !a.trim() || !b.trim()}>
          {busy ? "Comparing…" : "Compare"}
        </button>
      </form>
      <div className="ideas">
        {PAIRS.map(([x, y]) => (
          <button
            key={x + y}
            type="button"
            className="secondaire"
            onClick={() => {
              setA(x);
              setB(y);
              run(x, y);
            }}
          >
            {x} vs {y}
          </button>
        ))}
      </div>
      {error && <p className="erreur">{error}</p>}

      {data && (
        <div className={"compare-result" + (kids ? " kidsy" : "")}>
          <p className="compare-summary">
            <Cited text={data.summary} />
          </p>
          {data.similarities.length > 0 && (
            <>
              <h3>What they share</h3>
              <ul>
                {data.similarities.map((s, i) => (
                  <li key={i}>
                    <Cited text={s} />
                  </li>
                ))}
              </ul>
            </>
          )}
          {data.differences.length > 0 && (
            <div className="table-wrap">
              <table className="compare-table">
                <thead>
                  <tr>
                    <th>Aspect</th>
                    <th>{data.a}</th>
                    <th>{data.b}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.differences.map((d, i) => (
                    <tr key={i}>
                      <th scope="row">{d.aspect}</th>
                      <td>
                        <Cited text={d.a} />
                      </td>
                      <td>
                        <Cited text={d.b} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {data.caveats.length > 0 && (
            <p className="muted">
              <strong>Caveats:</strong> {data.caveats.join(" ")}
            </p>
          )}
          <div className="sources">
            {data.sources.map((s) => (
              <a key={s.titre} className="badge" href={s.url} target="_blank" rel="noopener noreferrer">
                {s.nom}
              </a>
            ))}
          </div>
          {!kids && (
            <details className="passages-used">
              <summary>Passages used ({data.passages.length})</summary>
              {data.passages.map((p) => (
                <p key={p.n}>
                  <strong>
                    [{p.n}] {p.nom}
                  </strong>{" "}
                  <span className="tag">{sourceTag(p.source_type)}</span> {p.texte.slice(0, 320)}…
                </p>
              ))}
            </details>
          )}
        </div>
      )}
    </section>
  );
}
