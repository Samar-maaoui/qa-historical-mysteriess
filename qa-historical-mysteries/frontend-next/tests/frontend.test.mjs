// Offline checks of the React code: server-side rendering of every section with sample data, plus the
// streaming client with a fake fetch. Run:  node tests/frontend.test.mjs
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import Module, { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const requireFromRoot = createRequire(path.join(root, "package.json"));
const ts = requireFromRoot("typescript");
const out = path.join(root, ".test-build");
fs.rmSync(out, { recursive: true, force: true });

// ---- transpile components/ and lib/ to CommonJS (the "@/" alias points to the build folder)
function build(dir) {
  for (const entry of fs.readdirSync(path.join(root, dir), { withFileTypes: true })) {
    const rel = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      build(rel);
      continue;
    }
    if (!/\.js$/.test(entry.name)) continue;
    const src = fs.readFileSync(path.join(root, rel), "utf8").replaceAll('from "@/', `from "${out.replaceAll("\\", "/")}/`).replaceAll('import("@/', `import("${out.replaceAll("\\", "/")}/`);
    const js = ts.transpileModule(src, { fileName: rel.replace(/\.js$/, ".jsx"), compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
    fs.mkdirSync(path.dirname(path.join(out, rel)), { recursive: true });
    fs.writeFileSync(path.join(out, rel), js);
  }
}
build("lib");
build("components");
fs.writeFileSync(path.join(out, "package.json"), '{"type":"commonjs"}');

// ---- mocks: next/dynamic (renders nothing) and CSS imports
const realLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "next/dynamic") return () => () => null;
  if (request.endsWith(".css")) return {};
  return realLoad.call(this, request, parent, isMain);
};
const load = (rel) => requireFromRoot(path.join(out, rel));
const React = requireFromRoot("react");
const { renderToStaticMarkup: html } = requireFromRoot("react-dom/server");
const h = React.createElement;
const count = (s, re) => (s.match(re) || []).length;
let passed = 0;
const check = (name, fn) => {
  try {
    fn();
    passed++;
    console.log("  ok  ", name);
  } catch (e) {
    console.error("  FAIL", name, "\n      ", e.message.split("\n")[0]);
    process.exitCode = 1;
  }
};

const passages = [
  { n: 1, id: "a", titre: "Hannibal Barca", nom: "Hannibal Barca", url: "https://fr.wikipedia.org/wiki/Hannibal_Barca", source_type: "Wikipedia (FR)", lang: "fr", texte: "Hannibal est né en 247 av. J.-C. et a traversé les Alpes avec des éléphants.", distance: 14.2, rerank: 3.1, vec_rank: 1, bm25_rank: 2 },
  { n: 2, id: "b", titre: "Hannibal Barca", nom: "Hannibal Barca", url: "https://en.wikipedia.org/wiki/Hannibal", source_type: "Wikipedia (EN)", lang: "en", texte: "He crossed the Alps with war elephants.", distance: 15.0, rerank: 2.0, vec_rank: 3, bm25_rank: null },
];
const fid = { taux: 0.5, model: "test-nli", details: [
  { phrase: "Summary", heading: true }, { phrase: "He crossed the Alps.", heading: false, soutenue: true, score: 0.93, best: 2, contradiction: 0.01, cited: [2], cite_ok: true },
  { phrase: "He never lost.", heading: false, soutenue: false, score: 0.1, best: 1, contradiction: 0.7, cited: [], cite_ok: null },
  { phrase: "He crossed the Alps in winter.", heading: false, soutenue: true, score: 0.8, best: 2, contradiction: 0.02, cited: [1], cite_ok: false }, { phrase: "Dates are approximate.", heading: false, meta: true }], citation_precision: 0.5, calibrated: true };
const answer = { question: "Who was Hannibal?", reponse: "Hannibal was born in 247 BC [1]. He crossed the Alps [2].", sources: [{ titre: "Hannibal Barca", nom: "Hannibal Barca", url: "https://fr.wikipedia.org/wiki/Hannibal_Barca", source_types: ["Wikipedia (FR)", "Wikipedia (EN)"] }],
  passages, citations: [1, 2], lieux: [{ titre: "Carthage", nom: "Carthage", lat: 36.85, lon: 10.32 }], extraits: [], confiance: "High", score: 0.9, distance: 18.3, refused: false, history_id: 7, p_answerable: 0.83, calibrated: true, intent: { label: "compare", p: 0.8 },
  retrieval: { retrieval: "hybrid", rerank: true, k: 20, top_n: 6, vector: 40, bm25: 30, candidates: 20, topics: [], source_types: [], timings_ms: { total: 120, vector: 20, keyword: 10, rerank: 90 }, embedding: "emb", reranker: "rr", llm: "llm", chunks_in_corpus: 8200, corpus_source_types: ["Wikipedia (EN)", "Wikipedia (FR)"], generated_at: "2026-10-31T12:00:00", bm25_terms: ["hannibal", "alpes", "elephants"] } };
const sujets = [{ titre: "Carthage", nom: "Carthage", emoji: "⚓", era: "Antiquity", kids_ok: true }, { titre: "Révolution tunisienne", nom: "Tunisian revolution", emoji: "🕊️", era: "Modern era", kids_ok: false }];

console.log("Server-side rendering");
check("Answer: citations become clickable chips", () => {
  const Answer = load("components/Answer.js").default;
  const s = html(h(Answer, { text: "Born in 247 BC [1]. Crossed the Alps [2][1].", passages }));
  assert.equal(count(s, /class="cite"/g), 3);
  assert.match(s, /Born in 247 BC/);
});
check("Timeline renders years, labels and sources", () => {
  const { default: Timeline } = load("components/Timeline.js");
  const s = html(h(Timeline, { events: [{ year: -247, year_label: "247 BC", label: "Hannibal is born", source: 1 }] }));
  assert.match(s, /247 BC/);
  assert.match(s, /\[1\]/);
  assert.match(html(h(Timeline, { events: [] })), /No dated events/);
});
check("FidelityReport separates headings, commentary and claims", () => {
  const { FidelityReport } = load("components/Echange.js");
  const s = html(h(FidelityReport, { fid }));
  assert.match(s, /✓<\/span> He crossed the Alps/);
  assert.match(s, /✗<\/span> He never lost/);
  assert.match(s, /commentary, not scored/);
  assert.match(s, /best passage \[2\]/);
  assert.match(s, /cited \[1\] but best supported by \[2\]/);
  assert.match(s, /citations point to the best passage in 50% of cases/);
  assert.match(s, /verdicts calibrated on your annotations/);
});
check("Timeline flags dates that are not in the sources (not for children)", () => {
  const { default: Timeline } = load("components/Timeline.js");
  const events = [{ year: -247, year_label: "247 BC", label: "Hannibal is born", source: 1, verified: true }, { year: -218, year_label: "218 BC", label: "He crosses the Alps", source: 2, verified: false }];
  const s = html(h(Timeline, { events }));
  assert.match(s, /class="tl-ok"/);
  assert.match(s, /unverified/);
  assert.ok(!html(h(Timeline, { events, kids: true })).includes("unverified"));
});
check("CorpusMap offers to load the map", () => {
  assert.match(html(h(load("components/CorpusMap.js").default)), /Show the corpus map/);
});
check("Echange (Explorer answer card)", () => {
  const Echange = load("components/Echange.js").default;
  const s = html(h(Echange, { h: answer, onResultat: () => {} }));
  for (const needle of ["Listen", "Check faithfulness", "Flashcard", "Star", "Passages used (2)", "Confidence: High", "Hannibal Barca", "Quiz on this topic", "Was this helpful?", "Timeline",
    "calibrated: 83% chance the sources contain the answer", "This looks like a comparison"]) assert.ok(s.includes(needle), needle);
  assert.ok(!html(h(Echange, { h: { ...answer, intent: { label: "compare", p: 0.4 } }, onResultat: () => {} })).includes("This looks like a comparison"), "weak intents are not shown");
  assert.match(html(h(Echange, { h: { ...answer, abstained: true, refused: true }, onResultat: () => {} })), /I preferred not to guess/);
  assert.equal(count(s, /class="cite"/g), 2);
});
check("Explorer: suggestions and clickable topics", () => {
  const Explorer = load("components/Explorer.js").default;
  const s = html(h(Explorer, { sujets }));
  assert.match(s, /Who was Hannibal Barca\?/);
  assert.match(s, /Carthage/);
  assert.match(s, /Topics \(2\)/);
});
check("Compare form", () => {
  const Compare = load("components/Compare.js").default;
  const s = html(h(Compare));
  assert.match(s, /Compare two subjects/);
  assert.match(s, /Carthage vs Kairouan/);
});
check("Notebook, Admin and Map shells", () => {
  assert.match(html(h(load("components/Notebook.js").default)), /My notebook/);
  assert.match(html(h(load("components/Admin.js").default)), /Administration/);
  assert.match(html(h(load("components/MapExplorer.js").default, { onAsk() {} })), /Loading the map/);
});
import { readFileSync, readdirSync } from "node:fs";
const SRC = new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const EMOJI = /[\p{Extended_Pictographic}\u{FE0F}\u{1F1E6}-\u{1F1FF}]/u;
check("Fonts never depend on a download during compilation", () => {
  const layout = readFileSync(SRC + "app/layout.js", "utf8");
  assert.ok(!layout.includes("next/font"), "next/font/google makes the build fail when Google Fonts cannot be fetched");
  for (const family of ["Cinzel", "EB+Garamond", "Fredoka", "Nunito"]) assert.ok(layout.includes(family), family);
  const css = readFileSync(SRC + "app/extras.css", "utf8");
  for (const v of ["--font-titre", "--font-texte", "--font-kids-title", "--font-kids-text"]) assert.ok(css.includes(v + ":"), v);
});
check("No emoji outside the Kids section (source files)", () => {
  const files = ["app/page.js", "app/layout.js", "app/globals.css", "app/extras.css", ...readdirSync(SRC + "components").filter((f) => f.endsWith(".js")).map((f) => "components/" + f)];
  const bad = [];
  for (const f of files) {
    readFileSync(SRC + f, "utf8").split("\n").forEach((line, i) => {
      // an emoji is tolerated only on a line that is explicitly about kids (the Kids tab, kids-only variants)
      if (EMOJI.test(line) && !/kids/i.test(line)) bad.push(`${f}:${i + 1}: ${line.trim().slice(0, 70)}`);
    });
  }
  assert.deepEqual(bad, []);
});
check("No emoji in the rendered interface outside Kids", () => {
  const { default: Feedback } = load("components/Feedback.js");
  const { TimelinePanel, default: Timeline } = load("components/Timeline.js");
  const { default: Echange } = load("components/Echange.js");
  const { default: Login } = load("components/Login.js");
  const events = [{ year: -247, year_label: "247 BC", label: "Born", source: 1, verified: false }];
  const pages = [html(h(Feedback, { historyId: 1, question: "q", mode: "standard" })), html(h(TimelinePanel, { passages: [] })), html(h(Timeline, { events })),
    html(h(Echange, { h: { ...answer, fidelity: null }, onResultat: () => {} })), html(h(Login, {})), html(h(Login, { initialMode: "signup" }))];
  pages.forEach((s, i) => assert.ok(!EMOJI.test(s), `page ${i} contains an emoji: ${(s.match(EMOJI) || [])[0]}`));
  assert.match(html(h(Feedback, { historyId: 1, question: "q", mode: "kids", kids: true })), /👍/);   // Kids keeps them
});
check("Sign in screen: email only, no password, link to Sign up", () => {
  const { default: Login } = load("components/Login.js");
  const s = html(h(Login, {}));
  for (const needle of ["Sign in", "Sign up", "Welcome back", 'type="email"', "Send me a sign-in link", "no password to remember", "No account yet?"]) assert.ok(s.includes(needle), needle);
  assert.ok(!s.includes('type="password"') && !s.includes('id="auth-name"') && !s.includes("Create my account"));
  assert.match(html(h(Login, { message: "Your session has expired." })), /Your session has expired\./);
});
check("Sign up screen: name and email, no password", () => {
  const { default: Login } = load("components/Login.js");
  const s = html(h(Login, { initialMode: "signup" }));
  for (const needle of ["Create your account", 'id="auth-name"', 'type="email"', "Create my account", "no password to create", "Already have an account?"]) assert.ok(s.includes(needle), needle);
  assert.ok(!s.includes('type="password"') && !s.includes("Send me a sign-in link"));
  assert.match(s, /aria-selected="true"[^>]*>Sign up/);
});
check("Kids: header, tabs, greeting and only kid-friendly topics", () => {
  const Kids = load("components/kids/Kids.js").default;
  const s = html(h(Kids, { sujets }));
  for (const needle of ["Hanni&#x27;s Time Machine", "Ask Hanni", "Quiz Quest", "Treasure Map", "True or False?", "Story Time", "My Stickers", "Hi, explorer!", "⚓", "Ask! 🚀"]) assert.ok(s.includes(needle), needle);
  assert.ok(!s.includes("Tunisian revolution"), "sensitive topic must not be offered to children");
});
check("Kids games: loading states and story topics", () => {
  const g = load("components/kids/KidsGames.js");
  assert.match(html(h(g.QuizQuest, { onProgress() {} })), /Hanni is writing a question/);
  assert.match(html(h(g.TrueFalse, { onProgress() {} })), /True or False/);
  const story = html(h(g.StoryTime, { sujets, onProgress() {} }));
  assert.match(story, /Story Time with Hanni/);
  assert.match(story, /Carthage/);
  assert.match(html(h(load("components/kids/WhereGame.js").default, { onProgress() {} })), /Treasure Map/);
  assert.match(html(h(load("components/kids/Stickers.js").default, { refresh: 0 })), /sticker book/);
});

console.log("Streaming client");
const sse = (name, data) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
const streamOf = (text, chunk) => new ReadableStream({ start(c) { const enc = new TextEncoder(); for (let i = 0; i < text.length; i += chunk) c.enqueue(enc.encode(text.slice(i, i + chunk))); c.close(); } });
const apiMod = load("lib/api.js");
const realFetch = globalThis.fetch;
const run = async (name, fn) => {
  try { await fn(); passed++; console.log("  ok  ", name); } catch (e) { console.error("  FAIL", name, "\n      ", e.message.split("\n")[0]); process.exitCode = 1; }
};
await run("askStream rebuilds events split across network chunks", async () => {
  const body = sse("meta", { passages: [1] }) + sse("token", { t: "Hel" }) + sse("token", { t: "lo" }) + sse("done", { reponse: "Hello", citations: [] });
  globalThis.fetch = async () => new Response(streamOf(body, 7), { status: 200 });
  const tokens = []; let meta = null;
  const done = await apiMod.askStream({ texte: "x" }, { onMeta: (m) => (meta = m), onToken: (t) => tokens.push(t) });
  assert.deepEqual(tokens, ["Hel", "lo"]);
  assert.deepEqual(meta, { passages: [1] });
  assert.equal(done.reponse, "Hello");
});
await run("askStream ignores keep-alive comments sent while the server works", async () => {
  const body = ": open\n\n" + ": keep-alive\n\n" + sse("meta", {}) + ": keep-alive\n\n" + sse("token", { t: "Hi" }) + sse("done", { reponse: "Hi" });
  globalThis.fetch = async () => new Response(streamOf(body, 5), { status: 200 });
  const tokens = [];
  const done = await apiMod.askStream({ texte: "x" }, { onToken: (t) => tokens.push(t) });
  assert.deepEqual(tokens, ["Hi"]);
  assert.equal(done.reponse, "Hi");
});
await run("ask(): an error event is surfaced", async () => {
  globalThis.fetch = async () => new Response(streamOf(sse("meta", {}) + sse("error", { detail: "LLM down" }), 50), { status: 200 });
  await assert.rejects(() => apiMod.ask({ texte: "x" }), /LLM down/);
});
await run("ask(): falls back to the normal endpoint when the stream cannot start", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    if (String(url).endsWith("/ask/stream")) throw new TypeError("network error");
    return new Response(JSON.stringify({ reponse: "fallback" }), { status: 200, headers: { "content-type": "application/json" } });
  };
  const r = await apiMod.ask({ texte: "x" });
  assert.equal(r.reponse, "fallback");
  assert.deepEqual(calls, ["/api/ask/stream", "/api/ask"]);
});
await run("api(): 401 announces the end of the session", async () => {
  let fired = false;
  globalThis.window = { dispatchEvent: () => (fired = true) };
  globalThis.Event = class { constructor(n) { this.type = n; } };
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Not authenticated." }), { status: 401, headers: { "content-type": "application/json" } });
  await assert.rejects(() => apiMod.api("/sujets"), /Not authenticated/);
  assert.ok(fired);
  delete globalThis.window;
});
globalThis.fetch = realFetch;
Module._load = realLoad;
fs.rmSync(out, { recursive: true, force: true });
console.log(`\n${passed} checks passed${process.exitCode ? ", SOME FAILED" : ""}`);
