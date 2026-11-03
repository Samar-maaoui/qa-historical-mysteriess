"use client";

import { useEffect, useState } from "react";
import Answer from "@/components/Answer";
import { api } from "@/lib/api";
import { shortDate } from "@/lib/text";

const MODE_LABEL = { standard: "Explorer", kids: "Kids" };

function useLoad(path, deps) {
  const [state, setState] = useState({ data: null, error: "", path: null });
  const key = deps.join("|");
  useEffect(() => {
    let cancelled = false;
    api(path)
      .then((d) => !cancelled && setState({ data: d, error: "", path: key }))
      .catch((e) => !cancelled && setState({ data: null, error: e.message, path: key }));
    return () => {
      cancelled = true;
    };
  }, [path, key]);
  return { ...state, loading: state.path !== key };
}

// ------------------------------------------------------------ history
function HistoryTab() {
  const [mode, setMode] = useState("");
  const [starred, setStarred] = useState(false);
  const [reload, setReload] = useState(0);
  const [open, setOpen] = useState(null);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const { data, error: loadError, loading } = useLoad(`/history?limit=100${mode ? `&mode=${mode}` : ""}${starred ? "&starred=true" : ""}`, [mode, starred, reload]);

  async function show(id) {
    if (open === id) {
      setOpen(null);
      return;
    }
    setOpen(id);
    setDetail(null);
    try {
      setDetail(await api(`/history/${id}`));
    } catch (e) {
      setError(e.message);
    }
  }

  async function star(item) {
    try {
      await api(`/history/${item.id}/star`, { method: "POST", body: { starred: !item.starred } });
      setReload((n) => n + 1);
    } catch (e) {
      setError(e.message);
    }
  }

  async function remove(id) {
    try {
      await api(`/history/${id}`, { method: "DELETE" });
      setOpen(null);
      setReload((n) => n + 1);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div>
      <div className="filters">
        <select value={mode} onChange={(e) => setMode(e.target.value)} aria-label="Filter by section">
          <option value="">All sections</option>
          <option value="standard">Explorer</option>
          <option value="kids">Kids</option>
        </select>
        <label className="check">
          <input type="checkbox" checked={starred} onChange={(e) => setStarred(e.target.checked)} /> Starred only
        </label>
      </div>
      {(error || loadError) && <p className="erreur">{error || loadError}</p>}
      {loading && <p className="chargement">Loading…</p>}
      {data && data.items.length === 0 && <p className="vide">Nothing here yet. Your questions are saved automatically.</p>}
      <ul className="nb-list">
        {data?.items.map((it) => (
          <li key={it.id} className={it.refused ? "nb-item refused" : "nb-item"}>
            <div className="nb-row">
              <button type="button" className="nb-title" onClick={() => show(it.id)} aria-expanded={open === it.id}>
                <span className="mode-tag">{MODE_LABEL[it.mode] || "Explorer"}</span> {it.question}
              </button>
              <span className="muted">{shortDate(it.created_at)}</span>
              <button type="button" className="secondaire mini" onClick={() => star(it)} aria-label={it.starred ? "Remove star" : "Star"}>
                {it.starred ? "Starred" : "Star"}
              </button>
              <button type="button" className="secondaire mini" onClick={() => remove(it.id)} aria-label="Delete">Delete</button>
            </div>
            {open === it.id && (
              <div className="nb-detail">
                {!detail && <p className="chargement">Loading…</p>}
                {detail && <Answer text={detail.answer} passages={detail.payload?.passages || []} />}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ------------------------------------------------------------ flashcards (Leitner boxes)
function CardsTab() {
  const [reload, setReload] = useState(0);
  const [flip, setFlip] = useState(false);
  const [error, setError] = useState("");
  const { data, error: loadError } = useLoad("/cards", [reload]);
  const { data: dueData } = useLoad("/cards?due=true", [reload]);
  const due = dueData?.cards || [];
  const current = due[0];

  async function review(correct) {
    try {
      await api(`/cards/${current.id}/review`, { method: "POST", body: { correct } });
      setFlip(false);
      setReload((n) => n + 1);
    } catch (e) {
      setError(e.message);
    }
  }

  async function remove(id) {
    try {
      await api(`/cards/${id}`, { method: "DELETE" });
      setReload((n) => n + 1);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div>
      {(error || loadError) && <p className="erreur">{error || loadError}</p>}
      {data && (
        <>
          <p className="muted">
            {data.cards.length} card{data.cards.length === 1 ? "" : "s"} · {due.length} to review now. Right answers move a card up one box (seen less often); a miss sends it back to box 1.
          </p>
          {current ? (
            <div className="flash">
              <div className="flash-face">
                <span className="tag">Box {current.box}</span>
                <p className="flash-front">{current.front}</p>
                {flip ? <p className="flash-back">{current.back}</p> : null}
                {current.source && <p className="muted">Source: {current.source}</p>}
              </div>
              {!flip ? (
                <button type="button" onClick={() => setFlip(true)}>
                  Show the answer
                </button>
              ) : (
                <div className="outils">
                  <button type="button" onClick={() => review(true)}>
                    I knew it
                  </button>
                  <button type="button" className="secondaire" onClick={() => review(false)}>
                    Not yet
                  </button>
                </div>
              )}
            </div>
          ) : (
            <p className="vide">{data.cards.length ? "All caught up! Come back later for the next review." : "No cards yet. Use “Flashcard” under an answer or a quiz."}</p>
          )}
          <ul className="nb-list">
            {data.cards.map((c) => (
              <li key={c.id} className="nb-item">
                <div className="nb-row">
                  <span className="nb-title static">{c.front}</span>
                  <span className="tag">Box {c.box}</span>
                  <button type="button" className="secondaire mini" onClick={() => remove(c.id)} aria-label="Delete card">Delete</button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------ progress
export function StatsGrid({ stats }) {
  const items = [
    ["Questions asked", stats.questions],
    ["Quiz answers", `${stats.quiz_correct}/${stats.quiz_total}`],
    ["Accuracy", stats.accuracy == null ? "–" : `${stats.accuracy}%`],
    ["Best streak", stats.best_streak],
    ["Stars", stats.stars],
  ];
  return (
    <div className="stat-grid">
      {items.map(([label, value]) => (
        <div key={label} className="stat">
          <strong>{value}</strong>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

function ProgressTab() {
  const { data, error } = useLoad("/stats?scope=main", []);
  return (
    <div>
      {error && <p className="erreur">{error}</p>}
      {data && (
        <>
          <StatsGrid stats={data.stats} />
          <h3>Badges</h3>
          <div className="badge-grid">
            {data.badges.map((b) => (
              <div key={b.id} className={"badge-card" + (b.earned ? " earned" : "")} title={b.desc}>
                <span className="badge-state">{b.earned ? "Earned" : "Locked"}</span>
                <strong>{b.name}</strong>
                <span className="muted">{b.desc}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function Notebook() {
  const [tab, setTab] = useState("history");
  return (
    <section className="panel">
      <h2 className="panel-h">My notebook</h2>
      <div className="subtabs" role="tablist">
        {[
          ["history", "History"],
          ["cards", "Flashcards"],
          ["progress", "Progress"],
        ].map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className={"subtab" + (tab === id ? " on" : "")} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "history" && <HistoryTab />}
      {tab === "cards" && <CardsTab />}
      {tab === "progress" && <ProgressTab />}
    </section>
  );
}
