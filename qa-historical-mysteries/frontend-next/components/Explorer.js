"use client";

import { useEffect, useImperativeHandle, useRef, useState } from "react";
import Answer from "@/components/Answer";
import Echange from "@/components/Echange";
import VoiceInput from "@/components/VoiceInput";
import { api, ask } from "@/lib/api";

const IDEAS = ["Who was Hannibal Barca?", "How was the Great Pyramid of Giza built?", "What happened to Pompeii?", "Why is Kairouan important in Tunisian history?"];

export default function Explorer({ ref, sujets }) {
  const [question, setQuestion] = useState("");
  const [historique, setHistorique] = useState([]);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState("");
  const [anecdote, setAnecdote] = useState(null);
  const [score, setScore] = useState(0);
  const [total, setTotal] = useState(0);
  const [live, setLive] = useState(null);
  const fin = useRef(null);

  useEffect(() => {
    fin.current?.scrollIntoView({ behavior: "smooth" });
  }, [historique.length, chargement]);

  async function poser(texte) {
    const text = (texte ?? question).trim();
    if (!text || chargement) return;
    setQuestion("");
    setErreur("");
    setChargement(true);
    setLive({ question: text, text: "", meta: null });
    const contexte = historique.slice(-3).map((h) => ({ question: h.question, reponse: h.reponse }));
    try {
      const data = await ask(
        { texte: text, historique: contexte, mode: "standard" },
        {
          onMeta: (m) => setLive((l) => (l ? { ...l, meta: m } : l)),
          onToken: (t) => setLive((l) => (l ? { ...l, text: l.text + t } : l)),
        }
      );
      setHistorique((prev) => [...prev, { question: text, ...data }]);
    } catch (e) {
      setErreur(e.message);
    } finally {
      setLive(null);
      setChargement(false);
    }
  }

  useImperativeHandle(ref, () => ({ ask: poser }));

  async function tirerAnecdote() {
    try {
      setAnecdote(await api("/anecdote"));
    } catch (e) {
      setErreur(e.message);
    }
  }

  function enregistrerResultat(bonne) {
    setTotal((t) => t + 1);
    if (bonne) setScore((s) => s + 1);
    api("/stats/quiz", { method: "POST", body: { scope: "main", correct: bonne } }).catch(() => {});
  }

  return (
    <>
      <header className="entete">
        <h1 className="titre">QA System — Historical Mysteries</h1>
        <p className="sous-titre">Ask a question, or a follow-up such as “and what about Machu Picchu?”</p>
        <p className="ornement">· · ·</p>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <h2>
            Score: {score}/{total}
          </h2>
          <button onClick={tirerAnecdote}>Random anecdote</button>
          {anecdote && (
            <div className="fait">
              <strong>Did you know?</strong>
              <p>{anecdote.extrait}</p>
              <span>— {anecdote.titre}</span>
            </div>
          )}
          <h2 style={{ marginTop: "1.2rem" }}>Topics ({sujets.length})</h2>
          <ul>
            {sujets.map((s) => (
              <li key={s.titre}>
                <button type="button" className="topic-btn" onClick={() => poser(`Tell me about ${s.nom}`)} disabled={chargement} title="Ask about this topic">
                  {s.nom}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main>
          <div className="chat">
            {historique.length === 0 && !live && (
              <div className="vide">
                <p>No questions yet. Try one of these:</p>
                <div className="ideas">
                  {IDEAS.map((q) => (
                    <button key={q} type="button" className="secondaire" onClick={() => poser(q)}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {historique.map((h, i) => (
              <div key={i}>
                <div className="bulle user">{h.question}</div>
                <Echange h={h} onResultat={enregistrerResultat} />
              </div>
            ))}
            {live && (
              <div>
                <div className="bulle user">{live.question}</div>
                <div className="bulle bot">
                  {live.text ? <Answer text={live.text} passages={live.meta?.passages || []} /> : <p className="chargement">Searching the sources…</p>}
                  {live.meta && live.meta.sources && (
                    <div className="sources">
                      {live.meta.sources.map((s) => (
                        <span key={s.titre} className="badge">
                          {s.nom}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
            {erreur && <p className="erreur">{erreur}</p>}
            <div ref={fin} />
          </div>

          <form
            className="saisie"
            onSubmit={(e) => {
              e.preventDefault();
              poser();
            }}
          >
            <input type="text" placeholder="Ask your question here..." value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={600} />
            <VoiceInput onText={(t) => setQuestion(t)} />
            <button type="submit" disabled={chargement}>
              Send
            </button>
          </form>
        </main>
      </div>
    </>
  );
}
