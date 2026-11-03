"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function Feedback({ historyId, question, mode, kids = false }) {
  const [step, setStep] = useState("ask"); // ask | comment | sent
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");

  async function send(rating, text = "") {
    setError("");
    try {
      await api("/feedback", { method: "POST", body: { rating, comment: text, question, mode, history_id: historyId ?? null } });
      setStep("sent");
    } catch (e) {
      setError(e.message);
    }
  }

  if (step === "sent") return <p className="feedback done">{kids ? "Thank you! 💛" : "Thanks for your feedback."}</p>;
  return (
    <div className="feedback">
      {step === "ask" && (
        <>
          <span>{kids ? "Did you like this?" : "Was this helpful?"}</span>
          <button type="button" className="secondaire mini" onClick={() => send(1)} aria-label="Helpful">
            {kids ? "👍" : "Helpful"}
          </button>
          <button type="button" className="secondaire mini" onClick={() => setStep("comment")} aria-label="Not helpful">
            {kids ? "👎" : "Not helpful"}
          </button>
        </>
      )}
      {step === "comment" && (
        <>
          <input type="text" value={comment} onChange={(e) => setComment(e.target.value)} placeholder={kids ? "What went wrong? (optional)" : "What was wrong? (optional)"} maxLength={300} />
          <button type="button" className="secondaire mini" onClick={() => send(-1, comment)}>
            Send
          </button>
        </>
      )}
      {error && <span className="erreur"> {error}</span>}
    </div>
  );
}
