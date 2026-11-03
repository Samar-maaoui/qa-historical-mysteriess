"use client";

import { useId, useState } from "react";
import { api } from "@/lib/api";

export default function Quiz({ extraits, onResultat }) {
  const nom = useId();
  const [q, setQ] = useState(null);
  const [choix, setChoix] = useState(null);
  const [valide, setValide] = useState(false);
  const [charge, setCharge] = useState(false);
  const [erreur, setErreur] = useState("");
  const [carte, setCarte] = useState(false);

  async function demarrer() {
    setCharge(true);
    setErreur("");
    setQ(null);
    setChoix(null);
    setValide(false);
    setCarte(false);
    try {
      setQ(await api("/quiz", { method: "POST", body: { extraits } }));
    } catch (e) {
      setErreur(e.message);
    } finally {
      setCharge(false);
    }
  }

  function valider() {
    if (choix === null) return;
    setValide(true);
    onResultat(choix === q.index_correct);
  }

  async function sauver() {
    try {
      await api("/cards", { method: "POST", body: { front: q.question, back: `${q.options[q.index_correct]}. ${q.explication}`, source: q.source, mode: "standard" } });
      setCarte(true);
    } catch (e) {
      setErreur(e.message);
    }
  }

  return (
    <div className="quiz">
      {!q && (
        <button className="secondaire" onClick={demarrer} disabled={charge}>
          {charge ? "Generating..." : "Quiz on this topic"}
        </button>
      )}
      {erreur && <p className="erreur">{erreur}</p>}
      {q && (
        <div className="quiz-carte">
          <p>
            <strong>{q.question}</strong>
          </p>
          {q.options.map((o, i) => {
            let etat = "";
            if (valide && i === q.index_correct) etat = " bonne";
            else if (valide && i === choix) etat = " mauvaise";
            return (
              <label key={i} className={"option" + etat}>
                <input type="radio" name={nom} checked={choix === i} disabled={valide} onChange={() => setChoix(i)} /> {o}
              </label>
            );
          })}
          {!valide ? (
            <button onClick={valider} disabled={choix === null}>
              Submit
            </button>
          ) : (
            <>
              <p className="explication">
                {choix === q.index_correct ? "Correct! " : "Wrong. "}
                {q.explication} <em>(source: {q.source})</em>
              </p>
              <div className="outils">
                <button className="secondaire" onClick={demarrer}>
                  New question
                </button>
                <button className="secondaire" onClick={sauver} disabled={carte}>
                  {carte ? "Saved" : "Save as flashcard"}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
