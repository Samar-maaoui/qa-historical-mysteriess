"""Step 2. Train / validation / test split BY ARTICLE: a test question never comes from an article seen in training,
so the scores measure generalisation instead of memory."""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, read_jsonl, write_jsonl  # noqa: E402

from ml import splits  # noqa: E402


def main():
    rows = read_jsonl(os.path.join(DATA, "pairs.jsonl"))
    if not rows:
        sys.exit("No pairs yet: run training/make_pairs.py first.")
    parts = splits.split_by_group(rows, lambda r: r["article"], seed=0)
    splits.assert_no_leak(parts, lambda r: r["article"])
    for name, items in parts.items():
        write_jsonl(os.path.join(DATA, f"{name}.jsonl"), items)
        print(f"{name}: {len(items)} questions from {len({r['article'] for r in items})} articles")
    print("✅ no article appears in two splits")


if __name__ == "__main__":
    main()
