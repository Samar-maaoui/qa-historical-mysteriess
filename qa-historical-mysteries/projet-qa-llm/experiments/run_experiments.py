"""Experiments for the report (run from the project folder, with MySQL started and .env filled):

    python experiments/run_experiments.py                 # everything (about 25-40 minutes with --judge --fidelity)
    python experiments/run_experiments.py --only ablation # retrieval ablation only (no LLM calls, fast)
    python experiments/run_experiments.py --only eval --limit 5 --pause 1.5   # quick trial run

1. ABLATION   : which retrieval component helps? (Hit@k and MRR on the expected article, no LLM needed)
2. RAG vs LLM : the same questions to an LLM alone and to the RAG variants: fact accuracy, refusal of out-of-corpus questions,
                rejection of false premises, citations, optional judge score and faithfulness (incl. citation precision).
Questions: experiments/questions_en.json (88: factual, French, Arabic, follow-ups, false premises, out-of-corpus).
Results go to experiments/results/ (JSON for every question + summary.md ready to paste in the report)."""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import json
import os
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import metrics  # noqa: E402

CONFIGS = {
    "vector": {"retrieval": "vector", "rerank": False},
    "vector+rerank": {"retrieval": "vector", "rerank": True},
    "hybrid": {"retrieval": "hybrid", "rerank": False},
    "hybrid+rerank": {"retrieval": "hybrid", "rerank": True},
}
SYSTEMS = {
    "llm_only": None,
    "rag_vector": {"retrieval": "vector", "rerank": False},
    "rag_hybrid": {"retrieval": "hybrid", "rerank": False},
    "rag_full": {"retrieval": "hybrid", "rerank": True},
}


def load_questions(limit=0, core_only=False):
    with open(os.path.join(HERE, "questions_en.json"), encoding="utf8") as f:
        qs = json.load(f)
    if core_only:
        return [q for q in qs if q.get("core")]
    if limit:
        picked = []
        for cat in ("factual", "french", "arabic", "followup", "false_premise", "out_of_corpus"):
            picked += [q for q in qs if q.get("category") == cat][:max(1, limit // 3 if cat in ("factual", "out_of_corpus") else 1)]
        qs = picked
    return qs


def run_ablation(engine, questions):
    ins = [q for q in questions if q["type"] == "in_corpus" and not q.get("history")]
    rows = {}
    for name, extra in CONFIGS.items():
        cfg = engine.make_cfg("standard", {"top_n": 6, "k": 20, **extra})
        h1 = h3 = h6 = 0
        rr, ms = [], []
        for q in ins:
            ret = engine.retrieve(q["question"], cfg)
            titles = [p["titre"] for p in ret["passages"]]
            h1 += metrics.hit_at_k(titles, q["source"], 1)
            h3 += metrics.hit_at_k(titles, q["source"], 3)
            h6 += metrics.hit_at_k(titles, q["source"], 6)
            rr.append(metrics.reciprocal_rank(titles, q["source"]))
            ms.append(ret["timings_ms"]["total"])
        n = len(ins) or 1
        rows[name] = {"hit@1": h1 / n, "hit@3": h3 / n, "hit@6": h6 / n, "mrr": metrics.mean(rr), "ms": metrics.mean(ms), "n": len(ins)}
        print(f"  ablation {name:14s} Hit@1 {metrics.pct(h1 / n)}  Hit@3 {metrics.pct(h3 / n)}  Hit@6 {metrics.pct(h6 / n)}  MRR {rows[name]['mrr']:.2f}")
    return rows


def answer_llm_only(engine, question, history=None):
    convo = "".join(f"Previous question: {h['question']}\nPrevious answer: {h['reponse']}\n" for h in (history or []))
    prompt = ("Answer this history question in English, in two or three sentences. "
              "If you do not know the answer, say that you do not know.\n\n" + convo + "Question: " + question)
    return engine.chat(prompt, 500, temperature=0), None


def answer_rag(engine, prompts, question, extra, history=None):
    cfg = engine.make_cfg("standard", {"top_n": 6, "k": 20, **extra})
    ret = engine.retrieve(engine.rewrite_query(question, history or []), cfg)
    text = engine.chat(prompts.standard(question, ret["passages"], history or []), 700, temperature=0)
    return text, ret


def judge(engine, prompts, q, answer):
    return metrics.parse_note(engine.chat(prompts.judge(q["question"], q["expected"], answer), 1000))


def run_eval(engine, prompts, core, questions, systems, use_judge, use_fidelity, pause):
    results = {s: [] for s in systems}
    for qi, q in enumerate(questions, 1):
        print(f"[{qi}/{len(questions)}] {q['question']}")
        history = q.get("history")
        ref_ret = None
        for s in systems:
            t0 = time.time()
            try:
                answer, ret = answer_llm_only(engine, q["question"], history) if s == "llm_only" else answer_rag(engine, prompts, q["question"], SYSTEMS[s], history)
            except Exception as e:
                print("   error:", repr(e))
                answer, ret = "", None
            latency = time.time() - t0
            row = {"id": q["id"], "type": q["type"], "category": q.get("category", q["type"]), "question": q["question"], "answer": answer, "latency_s": round(latency, 2)}
            if q["type"] == "in_corpus":
                row["fact_hit"] = metrics.fact_hit(answer, q["keys"])
            if q["type"] == "false_premise":
                row["premise_rejected"] = metrics.fact_hit(answer, q["keys"]) or core.is_refusal(answer)
            row["refused"] = core.is_refusal(answer)
            if ret is not None:
                row["cited"] = bool(core.used_citations(answer, len(ret["passages"])))
                row["top_titles"] = [p["titre"] for p in ret["passages"]]
            if use_judge and q["type"] == "in_corpus" and answer:
                row["judge"] = judge(engine, prompts, q, answer)
                time.sleep(pause)
            if use_fidelity and answer and q["type"] == "in_corpus":
                if ret is None:  # LLM alone: check its answer against what the corpus retrieves for the question
                    if ref_ret is None:
                        ref_ret = engine.retrieve(q["question"], engine.make_cfg("standard", {"top_n": 6}))
                    ret_for_check = ref_ret
                else:
                    ret_for_check = ret
                try:
                    fid = engine.check_fidelity(answer, ret_for_check["passages"])
                    row["faithfulness"] = fid["taux"]
                    row["citation_precision"] = fid.get("citation_precision") if ret is not None else None
                except Exception as e:
                    print("   fidelity skipped:", repr(e))
            results[s].append(row)
            print(f"   {s:11s} fact={row.get('fact_hit', row.get('premise_rejected', '-'))!s:5s} refused={row['refused']!s:5s} {latency:4.1f}s")
            time.sleep(pause)
    return results


def aggregate(rows):
    ins = [r for r in rows if r["type"] == "in_corpus"]
    outs = [r for r in rows if r["type"] == "out_of_corpus"]
    prem = [r for r in rows if r["type"] == "false_premise"]
    rag = [r for r in ins if "cited" in r]
    return {
        "fact_accuracy": metrics.mean([1.0 if r["fact_hit"] else 0.0 for r in ins]),
        "refusal_out_of_corpus": metrics.mean([1.0 if r["refused"] else 0.0 for r in outs]),
        "false_refusal_in_corpus": metrics.mean([1.0 if r["refused"] else 0.0 for r in ins]),
        "premise_rejection": metrics.mean([1.0 if r["premise_rejected"] else 0.0 for r in prem]),
        "citation_rate": metrics.mean([1.0 if r["cited"] else 0.0 for r in rag]),
        "citation_precision": metrics.mean([r.get("citation_precision") for r in ins]),
        "judge": metrics.mean([r.get("judge") for r in ins]),
        "faithfulness": metrics.mean([r.get("faithfulness") for r in ins]),
        "latency_s": metrics.mean([r["latency_s"] for r in rows]),
        "n_in": len(ins), "n_out": len(outs), "n_premise": len(prem),
    }


def by_category(rows):
    out = {}
    for cat in sorted({r["category"] for r in rows}):
        sub = [r for r in rows if r["category"] == cat]
        key = "premise_rejected" if cat == "false_premise" else "fact_hit" if cat != "out_of_corpus" else "refused"
        out[cat] = {"n": len(sub), "rate": metrics.mean([1.0 if r[key] else 0.0 for r in sub])}
    return out


def write_summary(path, ablation, results, meta):
    lines = [f"# Experiment results ({meta['date']})", "",
             f"Corpus: {meta['chunks']} passages, {meta['topics']} topics. Models: embeddings `{meta['embedding']}`, reranker `{meta['reranker']}`, LLM `{meta['llm']}`. Prompt version `{meta.get('prompt_version', 'n/a')}`.", ""]
    if ablation:
        lines += ["## 1. Retrieval ablation (does the expected article appear among the retrieved passages?)", "",
                  "| Configuration | Hit@1 | Hit@3 | Hit@6 | MRR | Mean time (ms) |", "|---|---|---|---|---|---|"]
        for name, r in ablation.items():
            lines.append(f"| {name} | {metrics.pct(r['hit@1'])} | {metrics.pct(r['hit@3'])} | {metrics.pct(r['hit@6'])} | {r['mrr']:.2f} | {r['ms']:.0f} |")
        lines += ["", f"Computed on {next(iter(ablation.values()))['n']} single-turn in-corpus questions. Hit@k = the right article is among the first k passages; MRR = mean reciprocal rank of the first right passage.", ""]
    if results:
        lines += ["## 2. LLM alone vs RAG variants", "",
                  "| System | Fact accuracy | Refuses out-of-corpus | Wrong refusals | Rejects false premises | Answers with citations | Citation precision | Judge (0-10) | Faithfulness | Mean time (s) |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for s, rows in results.items():
            a = aggregate(rows)
            j = "n/a" if a["judge"] is None else f"{a['judge']:.1f}"
            lines.append(f"| {s} | {metrics.pct(a['fact_accuracy'])} | {metrics.pct(a['refusal_out_of_corpus'])} | {metrics.pct(a['false_refusal_in_corpus'])} | {metrics.pct(a['premise_rejection'])} | "
                         f"{metrics.pct(a['citation_rate'])} | {metrics.pct(a['citation_precision'])} | {j} | {metrics.pct(a['faithfulness'])} | {a['latency_s']:.1f} |")
        first = next(iter(results.values()))
        a0 = aggregate(first)
        lines += ["", f"{a0['n_in']} answerable questions, {a0['n_premise']} false-premise questions and {a0['n_out']} out-of-corpus questions.", "",
                  "### By question category (the last RAG variant)", "", "| Category | Questions | Success rate |", "|---|---|---|"]
        for cat, v in by_category(list(results.values())[-1]).items():
            lines.append(f"| {cat} | {v['n']} | {metrics.pct(v['rate'])} |")
        lines += ["", "Success = the expected fact is present (factual, French, Arabic, follow-up), the false premise is corrected or refused (false_premise), or the assistant says it does not know (out_of_corpus).", "",
                  "- **Fact accuracy**: the answer contains an expected key fact (automatic check, no LLM judge involved).",
                  "- **Refuses out-of-corpus**: for questions the corpus cannot answer, the assistant says it does not know. An LLM alone is not designed to refuse, so a low value is expected there.",
                  "- **Rejects false premises**: the answer corrects or refuses a question built on a false assumption (keyword check: read the answers to confirm).",
                  "- **Citation precision**: of the cited statements, the share whose cited passage is the one that supports them best (needs `--fidelity`).",
                  "- **Faithfulness**: share of answer sentences supported by the retrieved passages (for the LLM alone, passages retrieved for the same question).", ""]
    with open(path, "w", encoding="utf8") as f:
        f.write("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["all", "ablation", "eval"], default="all")
    ap.add_argument("--systems", default=",".join(SYSTEMS), help="comma separated: " + ", ".join(SYSTEMS))
    ap.add_argument("--limit", type=int, default=0, help="quick trial: a few questions of every category")
    ap.add_argument("--judge", action="store_true", help="also score answers with the LLM judge")
    ap.add_argument("--fidelity", action="store_true", help="also compute the NLI faithfulness and citation precision (slower)")
    ap.add_argument("--pause", type=float, default=1.0, help="seconds between LLM calls (free API rate limit)")
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    args = ap.parse_args(argv)

    import core
    import engine
    import prompts

    questions = load_questions(args.limit)
    os.makedirs(args.out, exist_ok=True)
    ablation = results = None
    if args.only in ("all", "ablation"):
        print("== Retrieval ablation")
        ablation = run_ablation(engine, questions)
    if args.only in ("all", "eval"):
        print("== LLM alone vs RAG")
        systems = [s for s in args.systems.split(",") if s in SYSTEMS]
        results = run_eval(engine, prompts, core, questions, systems, args.judge, args.fidelity, args.pause)
    meta = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "chunks": len(engine.chunks), "topics": len(engine.sujets),
            "embedding": engine.EMBED_MODEL, "reranker": engine.reranker_name, "llm": engine.LLM_MODEL, "prompt_version": prompts.PROMPT_VERSION}
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf8") as f:
        json.dump({"meta": meta, "ablation": ablation, "results": results}, f, ensure_ascii=False, indent=1)
    write_summary(os.path.join(args.out, "summary.md"), ablation, results, meta)
    print("\nSaved:", os.path.join(args.out, "summary.md"))


if __name__ == "__main__":
    main()
