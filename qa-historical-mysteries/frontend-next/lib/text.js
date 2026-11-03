const CITE = /\[(\d{1,2}(?:\s*[,;]\s*\d{1,2})*)\]/g;

// "... in 247 BC [1][2]"  ->  markdown links that the Answer component turns into clickable chips
export function linkifyCitations(md) {
  return (md || "").replace(CITE, (_, group) =>
    group
      .split(/[,;]/)
      .map((n) => `[${n.trim()}](#cite-${n.trim()})`)
      .join("")
  );
}

export function stripCitations(text) {
  return (text || "").replace(/\s*\[(\d{1,2}(?:\s*[,;]\s*\d{1,2})*)\]/g, "");
}

// plain text for translation and speech
export function plainText(md) {
  return stripCitations(md).replace(/[*_`#]/g, "").replace(/^\s*[-•]\s+/gm, "").trim();
}

const strip = (s) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

// split a passage into pieces and flag the words that matched the search (accent-insensitive)
export function highlightParts(text, terms) {
  const set = new Set(terms || []);
  return (text || "")
    .split(/([\p{L}\p{N}]+)/u)
    .filter(Boolean)
    .map((p) => ({ t: p, hit: set.has(strip(p)) }));
}

export function sourceTag(type) {
  if (!type) return "";
  if (type.startsWith("Wikisource")) return "WS";
  if (type.includes("EN")) return "EN";
  if (type.includes("FR")) return "FR";
  return type;
}

export function shortDate(iso) {
  if (!iso) return "";
  return String(iso).slice(0, 16).replace("T", " ");
}
