"""Runs the whole experiment script once with the offline stand-ins (in a separate process)."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SCRIPT = """
import sys
sys.path[:0] = [{root!r}, {tests!r}, {exp!r}]
import stubs
from test_api_flow import ROWS
stubs.install(ROWS)
sys.argv = ["run_experiments.py", "--limit", "3", "--pause", "0", "--judge", "--fidelity", "--out", {out!r}]
import run_experiments
run_experiments.main()
"""


class TestExperimentScript(unittest.TestCase):
    def test_full_run_writes_summary(self):
        with tempfile.TemporaryDirectory() as out:
            code = SCRIPT.format(root=ROOT, tests=HERE, exp=os.path.join(ROOT, "experiments"), out=out)
            r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            with open(os.path.join(out, "summary.md"), encoding="utf8") as f:
                md = f.read()
            for needle in ("hybrid+rerank", "rag_full", "llm_only", "Fact accuracy", "Hit@6", "Citation precision", "By question category", "false_premise", "french", "followup"):
                self.assertIn(needle, md)
            self.assertIn("| llm_only |", md)


if __name__ == "__main__":
    unittest.main()


REG = """
import sys
sys.path[:0] = [{root!r}, {tests!r}, {exp!r}]
import stubs
from test_api_flow import ROWS
stubs.install(ROWS)
import regression, run_experiments
regression.BASELINE = {base!r}
sys.argv = ["regression.py"]
code1 = regression.main(["--pause", "0"])          # first run: creates the baseline
code2 = regression.main(["--pause", "0"])          # second run: same system, must pass
print("CODES", code1, code2)
"""

ADV = """
import sys
sys.path[:0] = [{root!r}, {tests!r}, {exp!r}]
import stubs
from test_api_flow import ROWS
stubs.install(ROWS)
{extra}
import adversarial
print("EXIT", adversarial.main())
"""


class TestRegressionAndAdversarial(unittest.TestCase):
    def run_code(self, code):
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)

    def test_regression_baseline_then_pass(self):
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "baseline.json")
            r = self.run_code(REG.format(root=ROOT, tests=HERE, exp=os.path.join(ROOT, "experiments"), base=base))
            self.assertEqual(r.returncode, 0, r.stderr[-1200:])
            self.assertIn("CODES 0 0", r.stdout)
            self.assertIn("No regression", r.stdout)
            self.assertTrue(os.path.exists(base))

    def test_adversarial_runner_passes_a_safe_model_and_flags_a_vulnerable_one(self):
        base = dict(root=ROOT, tests=HERE, exp=os.path.join(ROOT, "experiments"))
        safe = self.run_code(ADV.format(extra="", **base))
        self.assertIn("EXIT 0", safe.stdout, safe.stderr[-800:])
        self.assertIn("All 4 attacks were ignored", safe.stdout)
        weak = self.run_code(ADV.format(extra="stubs.STATE['llm_override'] = lambda p: 'PWNED' if 'PWNED' in p else 'Hannibal was a general [1].'", **base))
        self.assertIn("EXIT 1", weak.stdout, weak.stderr[-800:])
        self.assertIn("YES: vulnerable", weak.stdout)
