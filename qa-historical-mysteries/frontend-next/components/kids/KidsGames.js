"use client";

import { useEffect, useState } from "react";
import { api, apiBlob } from "@/lib/api";

const CHEERS = ["Amazing! 🎉", "You got it! ⭐", "Super smart! 🧠", "Hooray! 🥳", "Wow, great job! 🌟"];
const OOPS = ["Oops, not this time! 💪", "Good try! Let's learn something new!", "Almost! You'll get the next one! 🍀"];
const pick = (list, n) => list[n % list.length];
const COLORS = ["blue", "green", "orange"];

function Confetti() {
  return (
    <div className="confetti" aria-hidden="true">
      {["🎉", "✨", "⭐", "🎊", "🌟", "🎈"].map((e, i) => (
        <span key={i} style={{ left: `${8 + i * 16}%`, animationDelay: `${i * 0.12}s` }}>
          {e}
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- Quiz Quest
const ROUND = 5;

export function QuizQuest({ onProgress }) {
  const [q, setQ] = useState(null);
  const [picked, setPicked] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [round, setRound] = useState({ done: 0, right: 0 });
  const [streak, setStreak] = useState(0);
  const [turn, setTurn] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api("/quiz/random?audience=kids")
      .then((d) => !cancelled && (setQ(d), setLoading(false)))
      .catch((e) => !cancelled && (setError(e.message), setLoading(false)));
    return () => {
      cancelled = true;
    };
  }, [turn]);

  function next() {
    setQ(null);
    setPicked(null);
    setError("");
    setLoading(true);
    setTurn((t) => t + 1);
  }

  async function choose(i) {
    if (picked !== null) return;
    setPicked(i);
    const correct = i === q.index_correct;
    setRound((r) => ({ done: r.done + 1, right: r.right + (correct ? 1 : 0) }));
    try {
      const res = await api("/stats/quiz", { method: "POST", body: { scope: "kids", correct } });
      setStreak(res.stats.streak);
      onProgress(res.new_badges);
    } catch (e) {
      setError(e.message);
    }
  }

  function again() {
    setRound({ done: 0, right: 0 });
    next();
  }

  if (round.done >= ROUND && picked !== null) {
    return (
      <div className="kid-card center">
        <Confetti />
        <h2>Round complete! 🏆</h2>
        <p className="big-score">
          {round.right} / {ROUND}
        </p>
        <p>{"⭐".repeat(Math.max(1, Math.round((round.right / ROUND) * 3)))}</p>
        <p>{round.right === ROUND ? "Perfect! You are a history champion!" : round.right >= 3 ? "Great job, explorer!" : "Every try makes you smarter!"}</p>
        <button type="button" className="kid-btn orange big" onClick={again}>
          Play again 🔁
        </button>
      </div>
    );
  }

  return (
    <div className="kid-card">
      <div className="quest-top">
        <span>
          Question {Math.min(round.done + (picked === null ? 1 : 0), ROUND)} of {ROUND}
        </span>
        <span>🔥 Streak: {streak}</span>
      </div>
      {loading && <p className="chargement">Hanni is writing a question… ✏️</p>}
      {error && <p className="erreur">⚠️ {error}</p>}
      {q && (
        <>
          <h2 className="kid-q">
            {q.emoji} {q.question}
          </h2>
          <div className="kid-options">
            {q.options.map((o, i) => {
              let state = "";
              if (picked !== null && i === q.index_correct) state = " right";
              else if (picked === i) state = " wrong";
              return (
                <button key={i} type="button" className={`kid-option ${COLORS[i % 3]}${state}`} onClick={() => choose(i)} disabled={picked !== null}>
                  {o}
                </button>
              );
            })}
          </div>
          {picked !== null && (
            <div className={"kid-feedback " + (picked === q.index_correct ? "good" : "try")}>
              {picked === q.index_correct && <Confetti />}
              <strong>{picked === q.index_correct ? pick(CHEERS, round.done) : pick(OOPS, round.done)}</strong>
              <p>{q.explication}</p>
              <button type="button" className="kid-btn orange" onClick={next}>
                {round.done >= ROUND ? "See my score 🏆" : "Next question ➡️"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- True or False
export function TrueFalse({ onProgress }) {
  const [t, setT] = useState(null);
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [turn, setTurn] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api("/kids/truefalse")
      .then((d) => !cancelled && (setT(d), setLoading(false)))
      .catch((e) => !cancelled && (setError(e.message), setLoading(false)));
    return () => {
      cancelled = true;
    };
  }, [turn]);

  function next() {
    setT(null);
    setAnswer(null);
    setError("");
    setLoading(true);
    setTurn((n) => n + 1);
  }

  async function choose(value) {
    if (answer !== null) return;
    setAnswer(value);
    try {
      const res = await api("/stats/quiz", { method: "POST", body: { scope: "kids", correct: value === t.answer } });
      onProgress(res.new_badges);
    } catch (e) {
      setError(e.message);
    }
  }

  const correct = answer !== null && answer === t?.answer;
  return (
    <div className="kid-card center">
      <h2>👍 True or False? 👎</h2>
      {loading && <p className="chargement">Hanni is thinking of a fact… 💭</p>}
      {error && <p className="erreur">⚠️ {error}</p>}
      {t && (
        <>
          <p className="kid-q">
            {t.emoji} {t.statement}
          </p>
          <div className="tf-buttons">
            <button type="button" className={"kid-option green" + (answer !== null && t.answer === true ? " right" : answer === true ? " wrong" : "")} onClick={() => choose(true)} disabled={answer !== null}>
              ✅ True
            </button>
            <button type="button" className={"kid-option orange" + (answer !== null && t.answer === false ? " right" : answer === false ? " wrong" : "")} onClick={() => choose(false)} disabled={answer !== null}>
              ❌ False
            </button>
          </div>
          {answer !== null && (
            <div className={"kid-feedback " + (correct ? "good" : "try")}>
              {correct && <Confetti />}
              <strong>{correct ? "You got it! 🎉" : "Good try! 💪"}</strong>
              <p>{t.explanation}</p>
              <button type="button" className="kid-btn orange" onClick={next}>
                Another one ➡️
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Story Time
export function StoryTime({ sujets, onProgress }) {
  const [topic, setTopic] = useState("");
  const [story, setStory] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [audio, setAudio] = useState(null);
  const topics = sujets.filter((s) => s.kids_ok);

  useEffect(() => {
    return () => {
      if (audio) URL.revokeObjectURL(audio);
    };
  }, [audio]);

  async function tell(subject) {
    const s = (subject ?? topic).trim();
    if (!s || busy) return;
    setBusy(true);
    setError("");
    setAudio(null);
    setStory(null);
    try {
      const d = await api("/kids/story", { method: "POST", body: { topic: s } });
      setStory(d);
      onProgress(d.new_badges);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function readAloud() {
    try {
      setAudio(URL.createObjectURL(await apiBlob("/audio", { texte: `${story.title}. ${story.story}`, langue: "en", voix: "kids" })));
    } catch (e) {
      setError("Hanni lost her voice for a moment. Try again!");
      console.warn(e);
    }
  }

  return (
    <div className="kid-card">
      <h2>📖 Story Time with Hanni</h2>
      <p>Pick a place or write your own idea, and Hanni will tell you a story!</p>
      <div className="kid-topics">
        {topics.slice(0, 12).map((t) => (
          <button key={t.titre} type="button" className="kid-topic" onClick={() => tell(t.nom)} disabled={busy}>
            <span className="kid-topic-emoji">{t.emoji}</span>
            {t.nom}
          </button>
        ))}
      </div>
      <form
        className="kid-form"
        onSubmit={(e) => {
          e.preventDefault();
          tell();
        }}
      >
        <input type="text" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="A story about… 🐘" maxLength={120} aria-label="Story topic" />
        <button type="submit" className="kid-btn orange big" disabled={busy || !topic.trim()}>
          Tell me! ✨
        </button>
      </form>
      {busy && <p className="chargement">Hanni is writing your story… ✍️</p>}
      {error && <p className="erreur">⚠️ {error}</p>}
      {story && (
        <article className="story">
          <h3>{story.title}</h3>
          <p className="kid-text">{story.story}</p>
          <div className="kid-actions">
            <button type="button" className="kid-btn blue" onClick={readAloud}>
              🔊 Read to me
            </button>
            <button type="button" className="kid-btn green" onClick={() => tell(topic || story.title)}>
              🔁 Another story
            </button>
          </div>
          {audio && <audio controls autoPlay src={audio} />}
        </article>
      )}
    </div>
  );
}
