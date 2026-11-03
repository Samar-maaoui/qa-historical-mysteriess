"""Re-train the question-intent router (numpy only, takes seconds). A trained version is already in models/intent.json.
Add your own phrasing to ml/intent.py (TEMPLATES / REAL_STYLE) and run:  python training/train_intent.py"""


import sys
# Windows consoles use cp1252: emoji and Arabic would crash a redirected output (python script.py > file.txt)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MODELS  # noqa: E402

from ml import intent  # noqa: E402


def main():
    d, m = intent.train()
    intent.save(d, os.path.join(MODELS, "intent.json"))
    print(f"unseen phrasing patterns: {m['held_out_templates_accuracy']:.0%} | {m['n_hand_written']} hand-written questions: {m['hand_written_accuracy']:.0%}")
    print("per class:", {k: f"{v:.0%}" for k, v in m["hand_written_per_class"].items()})


if __name__ == "__main__":
    main()
