"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";

const WhereMap = dynamic(() => import("@/components/kids/WhereMap"), { ssr: false, loading: () => <p className="chargement">Unrolling the map… 🗺️</p> });

export default function WhereGame({ onProgress }) {
  const [round, setRound] = useState(null);
  const [seen, setSeen] = useState([]);
  const [guess, setGuess] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [turn, setTurn] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api(`/kids/where?exclude=${encodeURIComponent(seen.join("|"))}`)
      .then((d) => {
        if (cancelled) return;
        setRound(d);
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e.message);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // `seen` only changes together with `turn`, so the effect must follow `turn` alone
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turn]);

  function next() {
    setSeen((s) => (round ? [...s, round.site].slice(-12) : s));
    setRound(null);
    setGuess(null);
    setResult(null);
    setError("");
    setLoading(true);
    setTurn((t) => t + 1);
  }

  async function check() {
    try {
      const res = await api("/kids/where/score", { method: "POST", body: { site: round.site, lat: guess[0], lon: guess[1] } });
      setResult(res);
      onProgress(res.new_badges);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="kid-card">
      <h2>🗺️ Treasure Map</h2>
      <p>Read the clue, then click on the map where you think the place is!</p>
      {loading && <p className="chargement">Hanni is hiding a treasure… 🏴‍☠️</p>}
      {error && <p className="erreur">⚠️ {error}</p>}
      {round && (
        <>
          <div className="clue">
            <span className="clue-emoji" aria-hidden="true">
              🧩
            </span>
            <div>
              <strong>Clue:</strong> {round.clue}
              <div className="kid-chips">
                {round.era && <span className="kid-chip">⏳ {round.era}</span>}
                {round.region && <span className="kid-chip">🌍 {round.region}</span>}
              </div>
            </div>
          </div>
          <div className="kid-map">
            <WhereMap guess={guess} answer={result?.answer || null} onGuess={setGuess} />
          </div>
          {!result ? (
            <button type="button" className="kid-btn orange big" onClick={check} disabled={!guess}>
              {guess ? "Check my guess! 📍" : "Click on the map first 👆"}
            </button>
          ) : (
            <div className="kid-feedback good">
              <strong>{result.message}</strong>
              <p>
                {"⭐".repeat(result.stars)} You were {result.distance_km.toLocaleString("en-US")} km away. It was <strong>{result.answer.emoji} {result.answer.nom}</strong> ({result.answer.year}).
              </p>
              <button type="button" className="kid-btn orange" onClick={next}>
                Next treasure ➡️
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
