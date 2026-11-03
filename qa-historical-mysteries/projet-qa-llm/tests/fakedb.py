"""SQLite adapter that accepts the MySQL-flavoured SQL used by store.py (for offline tests)."""
import datetime
import os
import re
import sqlite3
import tempfile

sqlite3.register_adapter(datetime.datetime, lambda d: d.strftime("%Y-%m-%d %H:%M:%S.%f"))


def adapt(sql):
    sql = sql.replace("%s", "?")
    sql = sql.replace("INSERT IGNORE", "INSERT OR IGNORE")
    sql = re.sub(r"INT\s+AUTO_INCREMENT\s+PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT", sql)
    sql = sql.replace("LONGTEXT", "TEXT")
    return sql


class FakeCursor:
    def __init__(self, conn, dictionary):
        self._c = conn.cursor()
        self._dict = dictionary

    def execute(self, sql, params=()):
        self._c.execute(adapt(sql), tuple(params))
        return self

    def _row(self, r):
        if r is None or not self._dict:
            return r
        return {d[0]: v for d, v in zip(self._c.description, r)}

    def fetchone(self):
        return self._row(self._c.fetchone())

    def fetchall(self):
        return [self._row(r) for r in self._c.fetchall()]

    @property
    def lastrowid(self):
        return self._c.lastrowid

    @property
    def rowcount(self):
        return self._c.rowcount

    def close(self):
        self._c.close()


class FakeConn:
    def __init__(self, path):
        self._conn = sqlite3.connect(path)

    def cursor(self, dictionary=False):
        return FakeCursor(self._conn, dictionary)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def make_connect():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return lambda: FakeConn(path)
