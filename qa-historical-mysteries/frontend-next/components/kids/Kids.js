"use client";

import { useEffect, useState } from "react";
import KidsChat from "@/components/kids/KidsChat";
import { QuizQuest, StoryTime, TrueFalse } from "@/components/kids/KidsGames";
import Stickers from "@/components/kids/Stickers";
import WhereGame from "@/components/kids/WhereGame";
import { api } from "@/lib/api";

const TABS = [
  ["ask", "💬", "Ask Hanni"],
  ["quiz", "🎯", "Quiz Quest"],
  ["map", "🗺️", "Treasure Map"],
  ["tf", "👍", "True or False?"],
  ["story", "📖", "Story Time"],
  ["stickers", "🏅", "My Stickers"],
];

export default function Kids({ sujets }) {
  const [tab, setTab] = useState("ask");
  const [toast, setToast] = useState(null);
  const [stars, setStars] = useState(0);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api("/stats?scope=kids")
      .then((d) => !cancelled && setStars(d.stats.stars))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  // called by every activity: refreshes the star counter and celebrates new stickers
  function onProgress(badges) {
    setRefresh((n) => n + 1);
    if (badges && badges.length) {
      setToast(badges);
      setTimeout(() => setToast(null), 6000);
    }
  }

  return (
    <div className="kids">
      <header className="kids-head">
        <div className="mascot" aria-hidden="true">
          🐘
        </div>
        <div className="kids-title">
          <h1>Hanni&apos;s Time Machine</h1>
          <p>Hop in and ask me anything about the past!</p>
        </div>
        <div className="star-count" title="Your stars">
          ⭐ {stars}
        </div>
      </header>

      <nav className="kids-tabs" aria-label="Kids activities">
        {TABS.map(([id, emoji, label]) => (
          <button key={id} type="button" className={"kids-tab" + (tab === id ? " on" : "")} onClick={() => setTab(id)} aria-current={tab === id ? "page" : undefined}>
            <span className="kt-emoji">{emoji}</span> {label}
          </button>
        ))}
      </nav>

      {toast && (
        <div className="toast" role="status">
          🎉 New sticker{toast.length > 1 ? "s" : ""}: {toast.map((b) => `${b.emoji} ${b.name}`).join(", ")}!
        </div>
      )}

      <div className="kids-body">
        <div style={{ display: tab === "ask" ? "block" : "none" }}>
          <KidsChat sujets={sujets} onProgress={onProgress} />
        </div>
        {tab === "quiz" && <QuizQuest onProgress={onProgress} />}
        {tab === "map" && <WhereGame onProgress={onProgress} />}
        {tab === "tf" && <TrueFalse onProgress={onProgress} />}
        {tab === "story" && <StoryTime sujets={sujets} onProgress={onProgress} />}
        {tab === "stickers" && <Stickers refresh={refresh} />}
      </div>
    </div>
  );
}
