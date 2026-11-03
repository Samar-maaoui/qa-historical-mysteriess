"""Regression check: run the 32 'core' questions with the full pipeline and compare with the saved baseline.
Run it before and after every change (prompt, model, chunking, thresholds). It exits with an error if a metric dropped.

    python experiments/regression.py --save-baseline     # once, when you are happy with the system
    python experiments/regression.py                      # afterwards, after each modification"""


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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), HERE]

BASELINE = os.path.join(HERE, "baseline.json")
TOLERANCE = {"fact_accuracy": 0.06, "refusal_out_of_corpus": 0.15, "premise_rejection": 0.25, "false_refusal_in_corpus": 0.06}
HIGHER_IS_BETTER = {"fact_accuracy": True, "refusal_out_of_corpus": True, "premise_rejection": True, "false_refusal_in_corpus": False}


def compare(current, baseline, tolerance=TOLERANCE):
    """List of the metrics that got worse by more than the tolerance (empty list = no regression)."""
    failures = []
    for key, tol in tolerance.items():
        cur, base = current.get(key), baseline.get(key)
        if cur is None or base is None:
            continue
        worse = (base - cur) if HIGHER_IS_BETTER[key] else (cur - base)
        if worse > tol:
            failures.append({"metric": key, "baseline": round(base, 3), "current": round(cur, 3), "tolerance": tol})
    return failures


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args(argv)
    import core
    import engine
    import prompts
    import run_experiments as rx

    questions = rx.load_questions(core_only=True)
    results = rx.run_eval(engine, prompts, core, questions, ["rag_full"], False, False, args.pause)
    agg = rx.aggregate(results["rag_full"])
    agg = {k: v for k, v in agg.items() if v is not None}
    snapshot = {"metrics": agg, "prompt_version": prompts.PROMPT_VERSION, "llm": engine.LLM_MODEL, "reranker": engine.reranker_name,
                "embedding": engine.EMBED_MODEL, "date": time.strftime("%Y-%m-%d %H:%M"), "n_questions": len(questions)}
    print(json.dumps(snapshot["metrics"], indent=1))
    if args.save_baseline or not os.path.exists(BASELINE):
        with open(BASELINE, "w", encoding="utf8") as f:
            json.dump(snapshot, f, indent=1)
        print("baseline saved to", BASELINE)
        return 0
    with open(BASELINE, encoding="utf8") as f:
        base = json.load(f)
    failures = compare(agg, base["metrics"])
    if failures:
        print("\nREGRESSION:")
        for fl in failures:
            print(f"  {fl['metric']}: {fl['baseline']} -> {fl['current']} (tolerance {fl['tolerance']})")
        return 1
    print(f"\nNo regression compared with the baseline of {base['date']} (prompt {base['prompt_version']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
