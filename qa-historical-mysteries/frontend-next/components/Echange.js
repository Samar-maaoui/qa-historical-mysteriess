"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Answer from "@/components/Answer";
import Feedback from "@/components/Feedback";
import Quiz from "@/components/Quiz";
import { TimelinePanel } from "@/components/Timeline";
import { api, apiBlob } from "@/lib/api";
import { plainText, sourceTag } from "@/lib/text";

const Carte = dynamic(() => import("@/components/Carte"), { ssr: false });

const LANGUES = { en: "English (original)", fr: "Français", ar: "العربية", es: "Español" };
const INTENT_HINT = {
  compare: "This looks like a comparison: the Compare tab puts two subjects side by side.",
  timeline: "This looks like a chronology question: click Timeline below.",
  off_topic: "This does not look like a history question, so the answer may not be relevant.",
};

function Images({ sources }) {
  const [images, setImages] = useState([]);
  useEffect(() => {
    let annule = false;
    Promise.all(
      sources.map((s) =>
        fetch(`/api/image?titre=${encodeURIComponent(s.titre)}`)
          .then((r) => r.json())
          .then((d) => ({ titre: s.titre, nom: s.nom, url: d.url }))
          .catch(() => ({ titre: s.titre, nom: s.nom, url: null }))
      )
    ).then((res) => {
      if (!annule) setImages(res.filter((x) => x.url));
    });
    return () => {
      annule = true;
    };
  }, [sources]);
  if (!images.length) return null;
  return (
    <div className="images">
      {images.map((im) => (
        <figure key={im.titre}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={im.url} alt={im.nom} loading="lazy" />
          <figcaption>{im.nom}</figcaption>
        </figure>
      ))}
    </div>
  );
}

export function FidelityReport({ fid }) {
  return (
    <div className="fidelite">
      <strong>
        <span className={"dot " + (fid.taux >= 0.8 ? "dot-high" : fid.taux >= 0.5 ? "dot-medium" : "dot-low")} aria-hidden="true" /> Faithfulness to the sources: {Math.round(fid.taux * 100)}%
      </strong>
      {fid.citation_precision != null && <span className="distance"> · citations point to the best passage in {Math.round(fid.citation_precision * 100)}% of cases</span>}
      {fid.calibrated && <span className="distance"> · verdicts calibrated on your annotations</span>}
      <ul>
        {fid.details.map((d, i) => {
          if (d.heading) return <li key={i} className="fid-head">{d.phrase}</li>;
          if (d.meta) return <li key={i} className="fid-meta">{d.phrase} <span className="distance">(commentary, not scored)</span></li>;
          return (
            <li key={i}>
              <span className={d.soutenue ? "mark-ok" : "mark-no"}>{d.soutenue ? "✓" : "✗"}</span> {d.phrase}{" "}
              <span className="distance">
                (score {d.score}
                {d.best ? `, best passage [${d.best}]` : ""})
              </span>
              {d.cite_ok === false && (
                <span className="distance">
                  {" "}
                  — cited [{d.cited.join("][")}] but best supported by [{d.best}]
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function Echange({ h, onResultat }) {
  const [langue, setLangue] = useState("en");
  const [traduction, setTraduction] = useState(null);
  const [occupe, setOccupe] = useState("");
  const [erreur, setErreur] = useState("");
  const [audioUrl, setAudioUrl] = useState(null);
  const [fid, setFid] = useState(h.fidelity || null);
  const [carte, setCarte] = useState(false);
  const [etoile, setEtoile] = useState(false);

  const passages = h.passages || [];
  const affiche = traduction ?? plainText(h.reponse);

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  async function changerLangue(code) {
    setLangue(code);
    setAudioUrl(null);
    setErreur("");
    if (code === "en") {
      setTraduction(null);
      return;
    }
    setOccupe("trad");
    try {
      const d = await api("/traduire", { method: "POST", body: { texte: plainText(h.reponse), langue: code } });
      setTraduction(d.texte);
    } catch (e) {
      setErreur(e.message);
      setTraduction(null);
    } finally {
      setOccupe("");
    }
  }

  async function ecouter() {
    setOccupe("audio");
    setErreur("");
    try {
      setAudioUrl(URL.createObjectURL(await apiBlob("/audio", { texte: affiche, langue })));
    } catch (e) {
      setErreur(e.message);
    } finally {
      setOccupe("");
    }
  }

  async function verifier() {
    setOccupe("fid");
    setErreur("");
    try {
      setFid(await api("/fidelite", { method: "POST", body: { reponse: h.reponse, passages } }));
    } catch (e) {
      setErreur(e.message);
    } finally {
      setOccupe("");
    }
  }

  async function sauverCarte() {
    try {
      await api("/cards", { method: "POST", body: { front: h.question, back: plainText(h.reponse), source: h.sources?.[0]?.nom || "", mode: "standard" } });
      setCarte(true);
    } catch (e) {
      setErreur(e.message);
    }
  }

  async function etoiler() {
    if (!h.history_id) return;
    try {
      await api(`/history/${h.history_id}/star`, { method: "POST", body: { starred: !etoile } });
      setEtoile(!etoile);
    } catch (e) {
      setErreur(e.message);
    }
  }

  const fiable = h.score >= 0.6 && !h.refused;

  return (
    <div className="bulle bot">
      <Answer text={h.reponse} passages={passages} />
      {h.abstained && <p className="note-refus">I preferred not to guess: the retrieved sources did not look reliable enough for this question.</p>}
      {h.refused && !h.abstained && <p className="note-refus">The sources do not seem to cover this question, so this answer may be incomplete.</p>}
      {h.intent && h.intent.p >= 0.6 && INTENT_HINT[h.intent.label] && <p className="hint">{INTENT_HINT[h.intent.label]}</p>}

      <div className="outils">
        <select value={langue} onChange={(e) => changerLangue(e.target.value)} disabled={occupe === "trad"} aria-label="Language of the answer">
          {Object.entries(LANGUES).map(([code, nom]) => (
            <option key={code} value={code}>
              {nom}
            </option>
          ))}
        </select>
        <button className="secondaire" onClick={ecouter} disabled={occupe === "audio"}>
          {occupe === "audio" ? "Generating..." : "Listen"}
        </button>
        <button className="secondaire" onClick={verifier} disabled={occupe === "fid"}>
          {occupe === "fid" ? "Analyzing..." : "Check faithfulness"}
        </button>
        <button className="secondaire" onClick={sauverCarte} disabled={carte}>
          {carte ? "Saved" : "Flashcard"}
        </button>
        <button className="secondaire" onClick={etoiler} disabled={!h.history_id} title="Keep this answer in your notebook favourites">
          {etoile ? "Starred" : "Star"}
        </button>
      </div>

      {occupe === "trad" && <p className="chargement">Translating…</p>}
      {traduction && (
        <p className="traduction" dir={langue === "ar" ? "rtl" : "ltr"}>
          {traduction}
        </p>
      )}
      {audioUrl && <audio controls autoPlay src={audioUrl} />}
      {erreur && <p className="erreur">{erreur}</p>}
      {fid && <FidelityReport fid={fid} />}

      <div className="confiance">
        <span className={"dot dot-" + String(h.confiance).toLowerCase()} aria-hidden="true" /> Confidence: {h.confiance}{" "}
        <span className="distance">
          ({h.p_answerable != null ? `calibrated: ${Math.round(h.p_answerable * 100)}% chance the sources contain the answer · ` : ""}distance {h.distance})
        </span>
      </div>
      <div className="barre">
        <div style={{ width: `${Math.round((h.score || 0) * 100)}%` }} />
      </div>

      <div className="sources">
        {h.sources.map((s) => (
          <a key={s.titre} className="badge" href={s.url} target="_blank" rel="noopener noreferrer" title={(s.source_types || []).join(" + ")}>
            {s.nom}
          </a>
        ))}
      </div>

      {passages.length > 0 && (
        <details className="passages-used">
          <summary>Passages used ({passages.length})</summary>
          {passages.map((p) => (
            <p key={p.n}>
              <strong>
                [{p.n}] {p.nom}
              </strong>{" "}
              <span className="tag">{sourceTag(p.source_type)}</span> {p.texte.length > 360 ? p.texte.slice(0, 360) + "…" : p.texte}
            </p>
          ))}
        </details>
      )}

      {fiable && <Images sources={h.sources} />}
      {fiable && h.lieux && h.lieux.length > 0 && (
        <div className="carte">
          <Carte lieux={h.lieux} />
        </div>
      )}

      {passages.length > 0 && <TimelinePanel passages={passages} />}
      <Quiz extraits={h.extraits || []} onResultat={onResultat} />
      <Feedback historyId={h.history_id} question={h.question} mode="standard" />
    </div>
  );
}
