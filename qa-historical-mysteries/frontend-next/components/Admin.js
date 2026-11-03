"use client";

import { useState } from "react";
import CorpusMap from "@/components/CorpusMap";
import { api } from "@/lib/api";
import { download } from "@/lib/export";
import { shortDate } from "@/lib/text";
import { useEffect } from "react";

export default function Admin() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api(`/admin/summary?days=${days}`)
      .then((d) => !cancelled && (setData(d), setError("")))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [days]);

  function exportCsv() {
    const rows = [["question", "times_asked"], ...data.unanswered.map((u) => [u.question, u.count])];
    download("unanswered-questions.csv", rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n") + "\n", "text/csv");
  }

  const feedbackTotal = data ? data.feedback.up + data.feedback.down : 0;

  return (
    <section className="panel">
      <h2 className="panel-h">Administration</h2>
      <div className="filters">
        <label>
          Period{" "}
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </label>
      </div>
      {error && <p className="erreur">{error}</p>}
      {data && (
        <>
          <div className="stat-grid">
            <div className="stat">
              <strong>{data.total}</strong>
              <span>Questions</span>
            </div>
            <div className="stat">
              <strong>{data.total ? Math.round((100 * data.refused) / data.total) : 0}%</strong>
              <span>Refused or unanswered</span>
            </div>
            <div className="stat">
              <strong>{data.low_confidence}</strong>
              <span>Low confidence</span>
            </div>
            <div className="stat">
              <strong>{data.avg_distance ?? "–"}</strong>
              <span>Mean distance</span>
            </div>
            <div className="stat">
              <strong>{feedbackTotal ? `${Math.round((100 * data.feedback.up) / feedbackTotal)}%` : "–"}</strong>
              <span>
                Helpful: {data.feedback.up} · Not helpful: {data.feedback.down}
              </span>
            </div>
            <div className="stat">
              <strong>{data.users ?? "–"}</strong>
              <span>Registered users</span>
            </div>
          </div>
          <p className="muted">
            By section:{" "}
            {Object.entries(data.by_mode)
              .map(([m, n]) => `${m} ${n}`)
              .join(" · ") || "none yet"}
          </p>

          <h3>Questions the corpus could not answer</h3>
          {data.unanswered.length === 0 ? (
            <p className="vide">None in this period.</p>
          ) : (
            <>
              <div className="table-wrap">
                <table className="compare-table">
                  <thead>
                    <tr>
                      <th>Question</th>
                      <th>Times asked</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.unanswered.map((u) => (
                      <tr key={u.question}>
                        <td>{u.question}</td>
                        <td>{u.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button type="button" className="secondaire" onClick={exportCsv}>
                Export CSV
              </button>
              <p className="muted">These topics are good candidates for the next articles to add to the corpus.</p>
            </>
          )}

          <h3>Corpus map</h3>
          <CorpusMap />

          <h3>Latest comments</h3>
          {data.comments.length === 0 ? (
            <p className="vide">No comments yet.</p>
          ) : (
            <ul className="nb-list">
              {data.comments.map((c, i) => (
                <li key={i} className="nb-item">
                  <div className="nb-row">
                    <span>{c.rating > 0 ? "Helpful" : "Not helpful"}</span>
                    <span className="nb-title static">
                      “{c.comment}” <span className="muted">— on “{c.question}” ({c.mode})</span>
                    </span>
                    <span className="muted">{shortDate(c.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
