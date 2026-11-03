"""Step 8 (advanced, optional). RAFT fine-tuning of a small open model with LoRA, to learn the BEHAVIOUR the assistant needs:
cite the passages, ignore distractors, and say "I do not know" when the right passage is missing. Facts stay in the corpus.

    python training/lora_raft.py prepare --teacher-pause 1.0      # on your PC: the strong LLM writes the target answers
    python training/lora_raft.py train --base Qwen/Qwen2.5-3B-Instruct   # on a GPU (Google Colab T4 is enough for 1.5B-3B)
Needs:  pip install transformers peft accelerate torch   (UNTESTED on a GPU here: treat it as a starting point.)
A model this size will probably NOT beat the large hosted model; the point is to measure the gain and get a free local option."""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, MODELS, groq, llm, load_chunks, read_jsonl, write_jsonl  # noqa: E402

from ml import pairs, raft, sft  # noqa: E402
from sites_data import nom_en  # noqa: E402


def to_passage(chunk):
    return {"nom": nom_en(chunk["titre_article"]), "source_type": chunk.get("source_type", "Wikipedia"), "texte": chunk["texte"]}


def prepare_rows(train_pairs, chunks, rng, answer_fn, n_distractors=3, p_gold=0.8):
    by_id = {c["id"]: c for c in chunks}
    rows = []
    for p in train_pairs:
        gold_chunk = by_id.get(p["chunk_id"])
        if gold_chunk is None:
            continue
        others = [c for c in chunks if c["titre_article"] != gold_chunk["titre_article"]]
        distractors = [to_passage(c) for c in rng.sample(others, n_distractors)]
        rows.append(raft.build_raft_example(p["question"], to_passage(gold_chunk), distractors, rng, answer_fn, p_gold))
    return rows


def cmd_prepare(args):
    client = groq()

    def teacher(prompt):
        time.sleep(args.teacher_pause)
        return llm(client, prompt, 500, temperature=0)

    rows = prepare_rows(read_jsonl(os.path.join(DATA, "train.jsonl")), load_chunks(), random.Random(0), teacher)
    write_jsonl(os.path.join(DATA, "raft.jsonl"), rows)
    print(f"✅ {len(rows)} RAFT examples ({sum(r['has_gold'] for r in rows)} with the right passage) -> training/data/raft.jsonl")


def cmd_train(args):
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

    rows = [r for r in read_jsonl(os.path.join(DATA, "raft.jsonl")) if r["completion"]]
    tok = AutoTokenizer.from_pretrained(args.base)
    model = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32)
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))
    examples = [sft.tokenize_example(tok, r["prompt"], r["completion"], args.max_len) for r in rows]
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id

    class Data(torch.utils.data.Dataset):
        def __len__(self):
            return len(examples)

        def __getitem__(self, i):
            return examples[i]

    def collate(batch):
        return {k: torch.tensor(v) for k, v in sft.pad_batch(batch, pad).items()}

    out = os.path.join(MODELS, "llm-lora")
    Trainer(model=model, train_dataset=Data(), data_collator=collate,
            args=TrainingArguments(output_dir=out, per_device_train_batch_size=2, gradient_accumulation_steps=8, num_train_epochs=args.epochs,
                                   learning_rate=2e-4, logging_steps=10, save_strategy="epoch", report_to=[], bf16=torch.cuda.is_available())).train()
    model.save_pretrained(out)
    tok.save_pretrained(out)
    print("✅ LoRA adapter saved to", out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--teacher-pause", type=float, default=1.0)
    t = sub.add_parser("train")
    t.add_argument("--base", default="Qwen/Qwen2.5-3B-Instruct")
    t.add_argument("--epochs", type=int, default=2)
    t.add_argument("--max-len", type=int, default=2048)
    args = ap.parse_args(argv)
    (cmd_prepare if args.cmd == "prepare" else cmd_train)(args)


if __name__ == "__main__":
    main()
