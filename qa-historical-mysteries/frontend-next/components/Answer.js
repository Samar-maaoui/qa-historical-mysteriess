"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { linkifyCitations, sourceTag } from "@/lib/text";

// Markdown answer whose [1], [2]... markers are clickable and open the exact passage.
export default function Answer({ text, passages = [] }) {
  const [open, setOpen] = useState(null);
  const passage = passages.find((p) => p.n === open);

  const components = {
    a({ href, children }) {
      if (href && href.startsWith("#cite-")) {
        const n = Number(href.slice(6));
        return (
          <button type="button" className={"cite" + (open === n ? " on" : "")} onClick={() => setOpen(open === n ? null : n)} title="Show the passage behind this number">
            {children}
          </button>
        );
      }
      return (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      );
    },
  };

  return (
    <div className="reponse">
      <ReactMarkdown components={components}>{linkifyCitations(text)}</ReactMarkdown>
      {passage && (
        <div className="cite-card">
          <div className="cite-head">
            <strong>
              [{passage.n}] {passage.nom}
            </strong>
            <span className="tag">{sourceTag(passage.source_type)}</span>
            <a href={passage.url} target="_blank" rel="noopener noreferrer">
              Open source
            </a>
            <button type="button" className="secondaire mini" onClick={() => setOpen(null)} aria-label="Close passage">
              ✕
            </button>
          </div>
          <p>{passage.texte.length > 700 ? passage.texte.slice(0, 700) + "…" : passage.texte}</p>
        </div>
      )}
    </div>
  );
}
