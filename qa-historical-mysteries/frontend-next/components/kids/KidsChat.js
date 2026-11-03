"use client";

import { useEffect, useRef, useState } from "react";
import Feedback from "@/components/Feedback";
import { TimelinePanel } from "@/components/Timeline";
import VoiceInput from "@/components/VoiceInput";
import { api, apiBlob, ask } from "@/lib/api";

function KidAnswer({ item, onProgress }) {
  const [audio, setAudio] = useState(null);
  const [busy, setBusy] = useState(false);
  const [kept, setKept] = useState(false);
  const [error, setError] = useState("");
  const d = item.data;

  useEffect(() => {
    return () => {
      if (audio) URL.revokeObjectURL(audio);
    };
  }, [audio]);

  async function readAloud() {
    setBusy(true);
    setError("");
    try {
      setAudio(URL.createObjectURL(await apiBlob("/audio", { texte: d.reponse, langue: "en", voix: "kids" })));
    } catch (e) {
      setError("Hanni lost her voice for a moment. Try again!");
      console.warn(e);
    } finally {
      setBusy(false);
    }
  }

  async function keep() {
    try {
      await api("/cards", { method: "POST", body: { front: item.question, back: d.reponse, source: d.sources?.[0]?.nom || "", mode: "kids" } });
      setKept(true);
      onProgress([]);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="kid-row hanni">
      <div className="avatar" aria-hidden="true">
        🐘
      </div>
      <div className="kid-bubble hanni">
        <p className="kid-text">{d.reponse}</p>
        {!d.blocked && (
          <>
            <div className="kid-actions">
              <button type="button" className="kid-btn blue" onClick={readAloud} disabled={busy}>
                {busy ? "…" : "🔊 Read to me"}
              </button>
              <button type="button" className="kid-btn green" onClick={keep} disabled={kept}>
                {kept ? "💛 Kept!" : "❤️ Keep this"}
              </button>
            </div>
            {audio && <audio controls autoPlay src={audio} />}
            {d.sources?.length > 0 && !d.refused && (
              <p className="kid-sources">
                Hanni learned this from:{" "}
                {d.sources.map((s) => (
                  <span key={s.titre} className="kid-chip">
                    {s.nom}
                  </span>
                ))}
                <span className="grownups">
                  {" "}
                  Grown-ups can read more:{" "}
                  {d.sources.slice(0, 2).map((s) => (
                    <a key={s.titre} href={s.url} target="_blank" rel="noopener noreferrer">
                      {s.nom} ↗
                    </a>
                  ))}
                </span>
              </p>
            )}
            {!d.refused && d.passages?.length > 0 && <TimelinePanel passages={d.passages} audience="kids" label="⏳ Time machine" />}
            <Feedback historyId={d.history_id} question={item.question} mode="kids" kids />
          </>
        )}
        {error && <p className="erreur">⚠️ {error}</p>}
      </div>
    </div>
  );
}

export default function KidsChat({ sujets, onProgress }) {
  const [question, setQuestion] = useState("");
  const [items, setItems] = useState([]);
  const [live, setLive] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const end = useRef(null);
  const topics = sujets.filter((s) => s.kids_ok);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [items.length, busy]);

  async function send(text) {
    const q = (text ?? question).trim();
    if (!q || busy) return;
    setQuestion("");
    setError("");
    setBusy(true);
    setLive({ question: q, text: "" });
    const history = items.slice(-3).map((i) => ({ question: i.question, reponse: i.data.reponse }));
    try {
      const data = await ask({ texte: q, historique: history, mode: "kids" }, { onToken: (t) => setLive((l) => (l ? { ...l, text: l.text + t } : l)) });
      setItems((prev) => [...prev, { question: q, data }]);
      onProgress(data.new_badges);
    } catch (e) {
      setError("Oh no, Hanni got lost in time! Please try again. (" + e.message + ")");
    } finally {
      setLive(null);
      setBusy(false);
    }
  }

  return (
    <div className="kid-chat">
      {items.length === 0 && !live && (
        <div className="kid-row hanni">
          <div className="avatar" aria-hidden="true">
            🐘
          </div>
          <div className="kid-bubble hanni">
            <p className="kid-text">Hi, explorer! 👋 I&apos;m Hanni. I travel through time and I know lots of stories about pyramids, treasure, brave people and faraway places. Pick a place below, or type your own question!</p>
          </div>
        </div>
      )}
      <div className="kid-topics" aria-label="Pick a place to explore">
        {topics.map((t) => (
          <button key={t.titre} type="button" className="kid-topic" onClick={() => send(`Tell me about ${t.nom}!`)} disabled={busy}>
            <span className="kid-topic-emoji">{t.emoji}</span>
            {t.nom}
          </button>
        ))}
      </div>

      {items.map((it, i) => (
        <div key={i}>
          <div className="kid-row me">
            <div className="kid-bubble me">{it.question}</div>
          </div>
          <KidAnswer item={it} onProgress={onProgress} />
        </div>
      ))}
      {live && (
        <div>
          <div className="kid-row me">
            <div className="kid-bubble me">{live.question}</div>
          </div>
          <div className="kid-row hanni">
            <div className="avatar thinking" aria-hidden="true">
              🐘
            </div>
            <div className="kid-bubble hanni">
              <p className="kid-text">{live.text || "Hanni is thinking… 💭"}</p>
            </div>
          </div>
        </div>
      )}
      {error && <p className="erreur">{error}</p>}
      <div ref={end} />

      <form
        className="kid-form"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input type="text" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask Hanni a question… 🐘" maxLength={300} aria-label="Your question for Hanni" />
        <VoiceInput onText={(t) => setQuestion(t)} className="kid-mic" kids />
        <button type="submit" className="kid-btn orange big" disabled={busy || !question.trim()}>
          Ask! 🚀
        </button>
      </form>
    </div>
  );
}
