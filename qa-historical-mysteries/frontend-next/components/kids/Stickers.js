"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Stickers({ refresh }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/stats?scope=kids")
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  if (error) return <p className="erreur">⚠️ {error}</p>;
  if (!data) return <p className="chargement">Opening your sticker book… 📒</p>;
  const s = data.stats;
  const earned = data.badges.filter((b) => b.earned).length;

  return (
    <div className="kid-card">
      <h2>🏅 My Sticker Book</h2>
      <div className="kid-stats">
        <div>
          <strong>⭐ {s.stars}</strong>
          <span>stars</span>
        </div>
        <div>
          <strong>🔥 {s.best_streak}</strong>
          <span>best streak</span>
        </div>
        <div>
          <strong>🎯 {s.quiz_correct}</strong>
          <span>right answers</span>
        </div>
        <div>
          <strong>💬 {s.questions}</strong>
          <span>questions</span>
        </div>
      </div>
      <p>
        You found <strong>{earned}</strong> of {data.badges.length} stickers!
      </p>
      <div className="sticker-grid">
        {data.badges.map((b) => (
          <div key={b.id} className={"sticker" + (b.earned ? " earned" : "")}>
            <span className="sticker-emoji">{b.earned ? b.emoji : "❔"}</span>
            <strong>{b.name}</strong>
            <span>{b.desc}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
