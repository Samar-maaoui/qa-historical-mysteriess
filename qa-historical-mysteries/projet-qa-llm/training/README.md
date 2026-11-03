# Training and calibration

Everything here is optional: the application works without any of it. Each step produces a number you can put in the report,
and a model is only used if it improves that number.

| Step | Script | Needs | Produces |
|---|---|---|---|
| 1 | `make_pairs.py` | Groq key | `data/pairs.jsonl`: questions written by the LLM for real passages |
| 2 | `split_data.py` | | `train/val/test.jsonl`, split **by article** (no leakage) |
| 3a | `finetune_embeddings.py` | GPU recommended | `models/embeddings-ft` |
| 3b | `finetune_reranker.py` | GPU recommended | `models/reranker-ft` |
| 4 | `eval_retrieval.py` | | Recall@k and MRR table, base model vs fine-tuned, on the **test** split |
| 5 | `train_confidence.py` | models + MySQL | `models/confidence.json` and its calibration report |
| 6 | `label_nli.py`, `train_nli_calibrator.py` | 40+ labels by hand | `models/nli_calibrator.json` |
| 7 | `build_topic_map.py` | index built | `models/topic_map.json` (map of the corpus in Admin) |
| 8 | `lora_raft.py` | GPU, advanced | `models/llm-lora` (small local model taught to cite and to refuse) |
| – | `train_intent.py` | | `models/intent.json` (already trained and shipped) |

## Order and rules

1. Enlarge the corpus first (`collect_data.py --extended`, `collect_extra_sources.py`, `collect_sources.py`), then `chunking.py`, `build_index.py`, `init_db.py`.
2. `make_pairs.py` then `split_data.py`. **Never evaluate on a split that was used for training.**
3. Fine-tune (3a/3b), then evaluate (4). If the fine-tuned model is better on the test split: set `EMBED_MODEL` (and `RERANKER_MODEL`) in `.env`,
   run `build_index.py` and `init_db.py` again. The API warns if the index and `EMBED_MODEL` do not match.
4. **Retrain the confidence model (5) after any change of embedding or reranker model** (it ignores itself if the model names differ).
5. Keep the numbers before and after each change. A change that does not improve the test numbers is not kept.

## What to say in the report (honest limits)

- Pairs are written by an LLM: they are easier than real user questions, so absolute scores are optimistic; the **difference** between models is what counts.
- 31 articles are a small world: a model can over-fit to it. That is why the split is by article.
- The confidence model estimates "the sources contain the answer", not "the answer is correct". Say which label you used (`--answers` or not).
- Fine-tuning a small LLM teaches behaviour (citations, refusal), not facts. Facts stay in the corpus.
- `ml/intent.py` reports two numbers on purpose: unseen phrasing patterns (pessimistic) and hand-written questions (optimistic, because the templates were written knowing them).
