"""One-shot initialisation for docker compose: waits for MySQL, creates the auth tables and loads the corpus when the
database is empty (set FORCE_INIT=1 to reload it). Safe to run on every start."""
import os
import runpy
import sys
import time

import mysql.connector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)


def connect():
    return mysql.connector.connect(host=os.getenv("DB_HOST", "db"), user=os.getenv("DB_USER", "root"),
                                   password=os.getenv("DB_PASSWORD", ""), database=os.getenv("DB_NAME", "llm"))


def wait_for_db(connect_fn, tries=60, delay=2.0, sleep=time.sleep):
    last = None
    for i in range(tries):
        try:
            return connect_fn()
        except Exception as e:
            last = e
            print(f"waiting for MySQL ({i + 1}/{tries})...", flush=True)
            sleep(delay)
    raise RuntimeError(f"MySQL is not reachable: {last!r}")


def needs_corpus(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM chunks")
        n = cur.fetchone()[0]
        cur.close()
        return n == 0
    except Exception:
        return True   # the table does not exist yet


def main():
    conn = wait_for_db(connect)
    runpy.run_path(os.path.join(ROOT, "init_auth.py"), run_name="__main__")
    if os.getenv("FORCE_INIT") == "1" or needs_corpus(conn):
        print("loading the corpus into MySQL...", flush=True)
        runpy.run_path(os.path.join(ROOT, "init_db.py"), run_name="__main__")
    else:
        print("the corpus is already loaded: nothing to do.", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
