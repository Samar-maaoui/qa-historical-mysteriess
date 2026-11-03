"""RAFT-style training examples (Retrieval-Augmented Fine-Tuning): the model sees the gold passage MIXED WITH distractors,
and when the gold passage is missing it is taught to say it does not know. Used by training/lora_raft.py."""
import prompts

REFUSAL = "I do not know based on these sources."


def build_raft_example(question, gold, distractors, rng, answer_fn, p_gold=0.8):
    """gold / distractors: {"nom", "source_type", "texte"}. answer_fn(prompt) returns the teacher answer (with [n] citations)."""
    use_gold = rng.random() < p_gold
    chosen = ([gold] if use_gold else []) + list(distractors)
    rng.shuffle(chosen)
    numbered = [{"n": i + 1, "nom": p["nom"], "source_type": p.get("source_type", "Wikipedia"), "texte": p["texte"]} for i, p in enumerate(chosen)]
    prompt = prompts.standard(question, numbered, [])
    gold_n = next((i + 1 for i, p in enumerate(chosen) if p is gold), None)
    completion = answer_fn(prompt) if use_gold else REFUSAL
    return {"prompt": prompt, "completion": completion, "has_gold": use_gold, "gold_n": gold_n}
