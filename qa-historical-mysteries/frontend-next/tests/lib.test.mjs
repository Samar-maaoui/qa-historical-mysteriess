// Pure helpers of lib/: SSE parsing, citations, and highlighting.
import assert from "node:assert/strict";
const root = new URL("../lib/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const { parseSse } = await import(root + "api.js");
const t = await import(root + "text.js");

// SSE parsing
assert.deepEqual(parseSse('event: token\ndata: {"t": "Hi"}'), { name: "token", data: { t: "Hi" } });
assert.equal(parseSse("event: x\n"), null);
assert.equal(parseSse("event: token\ndata: {broken"), null);

// citations
assert.equal(t.linkifyCitations("Born in 247 BC [1]. Crossed the Alps [2][3] and [1, 4]."),
  "Born in 247 BC [1](#cite-1). Crossed the Alps [2](#cite-2)[3](#cite-3) and [1](#cite-1)[4](#cite-4).");
assert.equal(t.stripCitations("Fact [1][2]. More [3, 4]."), "Fact. More.");
assert.equal(t.plainText("## Title\n- **Bold** fact [1]."), "Title\nBold fact.");
assert.deepEqual(t.highlightParts("Les éléphants d'Hannibal", ["elephants", "hannibal"]).filter((p) => p.hit).map((p) => p.t), ["éléphants", "Hannibal"]);
assert.equal(t.sourceTag("Wikipedia (EN)"), "EN");
assert.equal(t.sourceTag("Wikisource (FR)"), "WS");

console.log("lib tests passed");
