import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "docker"), ROOT]
import types  # noqa: E402

import fakedb  # noqa: E402

if "mysql.connector" not in sys.modules:   # the script only needs the module to exist at import time
    _c = types.ModuleType("mysql.connector")
    _m = types.ModuleType("mysql")
    _m.connector = _c
    sys.modules.update({"mysql": _m, "mysql.connector": _c})
import init_all  # noqa: E402


class TestDockerInit(unittest.TestCase):
    def test_waits_until_mysql_answers(self):
        calls = {"n": 0, "slept": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise OSError("not ready")
            return "connection"
        self.assertEqual(init_all.wait_for_db(flaky, tries=5, delay=0, sleep=lambda s: calls.__setitem__("slept", calls["slept"] + 1)), "connection")
        self.assertEqual((calls["n"], calls["slept"]), (3, 2))

    def test_gives_up_with_a_clear_message(self):
        def never():
            raise OSError("down")
        with self.assertRaises(RuntimeError) as e:
            init_all.wait_for_db(never, tries=2, delay=0, sleep=lambda s: None)
        self.assertIn("MySQL is not reachable", str(e.exception))

    def test_corpus_is_loaded_only_when_missing_or_empty(self):
        connect = fakedb.make_connect()
        conn = connect()
        self.assertTrue(init_all.needs_corpus(conn))                   # no table yet
        cur = conn.cursor()
        cur.execute("CREATE TABLE chunks (id VARCHAR(10))")
        conn.commit()
        self.assertTrue(init_all.needs_corpus(conn))                   # empty table
        cur.execute("INSERT INTO chunks (id) VALUES ('a')")
        conn.commit()
        self.assertFalse(init_all.needs_corpus(conn))                  # already loaded: a restart must not wipe it


if __name__ == "__main__":
    unittest.main()
