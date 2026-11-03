"""Supervised fine-tuning helpers: the loss is computed on the ANSWER only, never on the prompt."""


def tokenize_example(tokenizer, prompt, completion, max_len=2048):
    p = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    c = tokenizer(completion + (tokenizer.eos_token or ""), add_special_tokens=False)["input_ids"]
    ids = (p + c)[:max_len]
    labels = ([-100] * len(p) + c)[:max_len]
    return {"input_ids": ids, "labels": labels, "attention_mask": [1] * len(ids)}


def pad_batch(batch, pad_id):
    n = max(len(b["input_ids"]) for b in batch)
    return {
        "input_ids": [b["input_ids"] + [pad_id] * (n - len(b["input_ids"])) for b in batch],
        "labels": [b["labels"] + [-100] * (n - len(b["labels"])) for b in batch],
        "attention_mask": [b["attention_mask"] + [0] * (n - len(b["attention_mask"])) for b in batch],
    }
