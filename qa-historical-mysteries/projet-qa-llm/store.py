"""Persistence layer (MySQL, portable SQL): history, study cards, stats, feedback, query log.
`connect` is any callable returning a DB-API connection that supports cursor(dictionary=True)
and %s placeholders (mysql.connector). The tests plug in an SQLite adapter."""
import json
from datetime import timedelta

import core

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS members (
            email VARCHAR(255) PRIMARY KEY,
            name VARCHAR(80) NOT NULL,
            verified TINYINT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL
        )""",
    """CREATE TABLE IF NOT EXISTS history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        mode VARCHAR(20) NOT NULL,
        question TEXT NOT NULL,
        answer LONGTEXT NOT NULL,
        payload LONGTEXT,
        confidence VARCHAR(10),
        distance FLOAT,
        refused INT DEFAULT 0,
        starred INT DEFAULT 0,
        created_at DATETIME NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS user_stats (
        email VARCHAR(255) NOT NULL,
        scope VARCHAR(10) NOT NULL,
        questions INT DEFAULT 0,
        quiz_total INT DEFAULT 0,
        quiz_correct INT DEFAULT 0,
        streak INT DEFAULT 0,
        best_streak INT DEFAULT 0,
        stars INT DEFAULT 0,
        games INT DEFAULT 0,
        stories INT DEFAULT 0,
        updated_at DATETIME,
        PRIMARY KEY (email, scope)
    )""",
    """CREATE TABLE IF NOT EXISTS cards (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        front TEXT NOT NULL,
        back TEXT NOT NULL,
        source VARCHAR(255),
        mode VARCHAR(20),
        box INT DEFAULT 1,
        reviews INT DEFAULT 0,
        due_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS feedback (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_hash VARCHAR(64),
        history_id INT,
        rating INT NOT NULL,
        comment TEXT,
        question TEXT,
        mode VARCHAR(20),
        created_at DATETIME NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS query_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        mode VARCHAR(20),
        question TEXT,
        confidence VARCHAR(10),
        distance FLOAT,
        refused INT DEFAULT 0,
        created_at DATETIME NOT NULL
    )""",
]

STAT_FIELDS = ("questions", "quiz_total", "quiz_correct", "streak", "best_streak", "stars", "games", "stories")


def iso(v):
    return v.isoformat(sep=" ", timespec="seconds") if hasattr(v, "isoformat") else (str(v)[:19] if v else None)


class Store:
    def __init__(self, connect):
        self.connect = connect

    # ---- low level
    def _run(self, sql, params=(), fetch=None, commit=False):
        conn = self.connect()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(sql, params)
            if fetch == "all":
                out = cur.fetchall()
            elif fetch == "one":
                out = cur.fetchone()
            else:
                out = {"id": getattr(cur, "lastrowid", None), "rows": cur.rowcount}
            if commit:
                conn.commit()
            cur.close()
            return out
        finally:
            conn.close()

    def ensure_tables(self):
        for stmt in SCHEMA:
            self._run(stmt, commit=True)

    # ---- members (sign up with a name; the e-mail link confirms it)
    def get_member(self, email):
        return self._run("SELECT email, name, verified FROM members WHERE email = %s", (email,), fetch="one")

    def save_member(self, email, name, now):
        """Create the membership, or update the name of an UNCONFIRMED one (a confirmed one is never touched)."""
        if self.get_member(email):
            self._run("UPDATE members SET name = %s WHERE email = %s AND verified = 0", (name, email), commit=True)
        else:
            self._run("INSERT INTO members (email, name, verified, created_at) VALUES (%s, %s, 0, %s)", (email, name, now), commit=True)

    def confirm_member(self, email):
        self._run("UPDATE members SET verified = 1 WHERE email = %s", (email,), commit=True)

    # ---- history
    def add_history(self, email, mode, question, answer, payload, confidence, distance, refused, now):
        r = self._run(
            "INSERT INTO history (email, mode, question, answer, payload, confidence, distance, refused, starred, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s)",
            (email, mode, question, answer, json.dumps(payload, ensure_ascii=False), confidence, distance, 1 if refused else 0, now),
            commit=True)
        return r["id"]

    def list_history(self, email, mode=None, starred=False, limit=50):
        sql = "SELECT id, mode, question, answer, confidence, distance, refused, starred, created_at FROM history WHERE email = %s"
        params = [email]
        if mode:
            sql += " AND mode = %s"
            params.append(mode)
        if starred:
            sql += " AND starred = 1"
        sql += " ORDER BY id DESC LIMIT %s"
        params.append(int(limit))
        rows = self._run(sql, tuple(params), fetch="all")
        return [{"id": r["id"], "mode": r["mode"], "question": r["question"], "answer": core.truncate(r["answer"], 600),
                 "confidence": r["confidence"], "distance": r["distance"], "refused": bool(r["refused"]),
                 "starred": bool(r["starred"]), "created_at": iso(r["created_at"])} for r in rows]

    def get_history(self, email, hid):
        r = self._run("SELECT * FROM history WHERE id = %s AND email = %s", (hid, email), fetch="one")
        if not r:
            return None
        try:
            payload = json.loads(r["payload"]) if r.get("payload") else {}
        except Exception:
            payload = {}
        return {"id": r["id"], "mode": r["mode"], "question": r["question"], "answer": r["answer"], "payload": payload,
                "starred": bool(r["starred"]), "created_at": iso(r["created_at"])}

    def star_history(self, email, hid, starred):
        return self._run("UPDATE history SET starred = %s WHERE id = %s AND email = %s",
                         (1 if starred else 0, hid, email), commit=True)["rows"] > 0

    def delete_history(self, email, hid):
        return self._run("DELETE FROM history WHERE id = %s AND email = %s", (hid, email), commit=True)["rows"] > 0

    # ---- stats
    def get_stats(self, email, scope):
        r = self._run("SELECT * FROM user_stats WHERE email = %s AND scope = %s", (email, scope), fetch="one")
        return {k: int((r or {}).get(k) or 0) for k in STAT_FIELDS}

    def _save_stats(self, email, scope, stats, now):
        exists = self._run("SELECT email FROM user_stats WHERE email = %s AND scope = %s", (email, scope), fetch="one")
        vals = [int(stats[k]) for k in STAT_FIELDS]
        if exists:
            sets = ", ".join(f"{k} = %s" for k in STAT_FIELDS)
            self._run(f"UPDATE user_stats SET {sets}, updated_at = %s WHERE email = %s AND scope = %s",
                      tuple(vals) + (now, email, scope), commit=True)
        else:
            cols = ", ".join(STAT_FIELDS)
            marks = ", ".join(["%s"] * (len(STAT_FIELDS) + 3))
            self._run(f"INSERT INTO user_stats (email, scope, {cols}, updated_at) VALUES ({marks})",
                      (email, scope, *vals, now), commit=True)

    def bump(self, email, scope, now, **inc):
        s = self.get_stats(email, scope)
        for k, v in inc.items():
            if k in s:
                s[k] += int(v)
        self._save_stats(email, scope, s, now)
        return s

    def record_quiz(self, email, scope, correct, now):
        s = self.get_stats(email, scope)
        s["quiz_total"] += 1
        s["quiz_correct"] += 1 if correct else 0
        s["streak"], s["best_streak"] = core.update_streak(s["streak"], s["best_streak"], correct)
        self._save_stats(email, scope, s, now)
        return s

    # ---- study cards (Leitner boxes)
    def add_card(self, email, front, back, source, mode, now):
        old = self._run("SELECT id FROM cards WHERE email = %s AND front = %s", (email, front), fetch="one")
        if old:
            return old["id"], False
        r = self._run("INSERT INTO cards (email, front, back, source, mode, box, reviews, due_at, created_at) "
                      "VALUES (%s, %s, %s, %s, %s, 1, 0, %s, %s)", (email, front, back, source, mode, now, now), commit=True)
        return r["id"], True

    def _card(self, r):
        return {"id": r["id"], "front": r["front"], "back": r["back"], "source": r["source"], "mode": r["mode"],
                "box": int(r["box"] or 1), "reviews": int(r["reviews"] or 0), "due_at": iso(r["due_at"])}

    def list_cards(self, email, due_only=False, now=None, limit=200):
        if due_only:
            rows = self._run("SELECT * FROM cards WHERE email = %s AND due_at <= %s ORDER BY due_at LIMIT %s",
                             (email, now, int(limit)), fetch="all")
        else:
            rows = self._run("SELECT * FROM cards WHERE email = %s ORDER BY id DESC LIMIT %s", (email, int(limit)), fetch="all")
        return [self._card(r) for r in rows]

    def review_card(self, email, cid, correct, now):
        r = self._run("SELECT * FROM cards WHERE id = %s AND email = %s", (cid, email), fetch="one")
        if not r:
            return None
        box = core.next_box(r["box"], correct)
        due = core.due_date(now, box)
        self._run("UPDATE cards SET box = %s, due_at = %s, reviews = %s WHERE id = %s AND email = %s",
                  (box, due, int(r["reviews"] or 0) + 1, cid, email), commit=True)
        return {"id": cid, "box": box, "due_at": iso(due)}

    def delete_card(self, email, cid):
        return self._run("DELETE FROM cards WHERE id = %s AND email = %s", (cid, email), commit=True)["rows"] > 0

    # ---- feedback and query log (no e-mail stored in the log)
    def add_feedback(self, user_hash, history_id, rating, comment, question, mode, now):
        return self._run("INSERT INTO feedback (user_hash, history_id, rating, comment, question, mode, created_at) "
                         "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                         (user_hash, history_id, 1 if rating > 0 else -1, (comment or "")[:1000], (question or "")[:1000], mode, now),
                         commit=True)["id"]

    def log_query(self, mode, question, confidence, distance, refused, now):
        self._run("INSERT INTO query_log (mode, question, confidence, distance, refused, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                  (mode, (question or "")[:500], confidence, distance, 1 if refused else 0, now), commit=True)

    def admin_summary(self, now, days=30):
        since = now - timedelta(days=days)
        by_mode = self._run("SELECT mode, COUNT(*) AS n FROM query_log WHERE created_at >= %s GROUP BY mode", (since,), fetch="all")
        total = sum(r["n"] for r in by_mode)
        refused = self._run("SELECT COUNT(*) AS n FROM query_log WHERE created_at >= %s AND refused = 1", (since,), fetch="one")["n"]
        low = self._run("SELECT COUNT(*) AS n FROM query_log WHERE created_at >= %s AND confidence = 'Low'", (since,), fetch="one")["n"]
        avg = self._run("SELECT AVG(distance) AS d FROM query_log WHERE created_at >= %s", (since,), fetch="one")["d"]
        fb = self._run("SELECT rating, COUNT(*) AS n FROM feedback WHERE created_at >= %s GROUP BY rating", (since,), fetch="all")
        up = sum(r["n"] for r in fb if r["rating"] > 0)
        down = sum(r["n"] for r in fb if r["rating"] < 0)
        unanswered = self._run("SELECT question, COUNT(*) AS n FROM query_log WHERE created_at >= %s "
                               "AND (refused = 1 OR confidence = 'Low') GROUP BY question ORDER BY n DESC LIMIT 20",
                               (since,), fetch="all")
        comments = self._run("SELECT comment, rating, question, mode, created_at FROM feedback "
                             "WHERE comment IS NOT NULL AND comment <> '' ORDER BY id DESC LIMIT 15", fetch="all")
        users = self._run("SELECT COUNT(*) AS n FROM users", fetch="one") if self._has_users() else {"n": None}
        return {
            "days": days, "total": total, "by_mode": {r["mode"]: r["n"] for r in by_mode},
            "refused": refused, "low_confidence": low, "avg_distance": round(float(avg), 2) if avg is not None else None,
            "feedback": {"up": up, "down": down},
            "unanswered": [{"question": r["question"], "count": r["n"]} for r in unanswered],
            "comments": [{"comment": r["comment"], "rating": r["rating"], "question": r["question"], "mode": r["mode"],
                          "created_at": iso(r["created_at"])} for r in comments],
            "users": users["n"],
        }

    def _has_users(self):
        try:
            self._run("SELECT 1 FROM users LIMIT 1", fetch="one")
            return True
        except Exception:
            return False
