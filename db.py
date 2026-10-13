import sqlite3
from datetime import datetime

DB_PATH = "jobs.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT, company TEXT, location TEXT, url TEXT,
            posted TEXT, homeoffice INTEGER,
            score INTEGER, reason TEXT,
            status TEXT DEFAULT 'new',
            first_seen TEXT
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")
    conn.commit()
    return conn


def exists(conn, job):
    """True if this job id, or the same company+title+location, is stored."""
    row = conn.execute(
        "SELECT 1 FROM jobs WHERE id=? OR (company=? AND title=? AND location=?)",
        (job["id"], job["company"], job["title"], job["location"]),
    ).fetchone()
    return row is not None


def save(conn, job, score, reason, status):
    conn.execute(
        """INSERT OR REPLACE INTO jobs
           (id, title, company, location, url, posted, homeoffice,
            score, reason, status, first_seen)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (job["id"], job["title"], job["company"], job["location"],
         job["url"], job["posted"], int(job.get("homeoffice", False)),
         score, reason, status, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()


def pending(conn, limit):
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status='pending' ORDER BY score DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def mark(conn, job_id, status):
    conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    conn.commit()


def get_job(conn, job_id):
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_by_status(conn, status, limit):
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status=? ORDER BY first_seen DESC LIMIT ?",
        (status, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def status_counts(conn):
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"
    ).fetchall()
    return {r["status"]: r["n"] for r in rows}


def scored_since(conn, days):
    row = conn.execute(
        """SELECT COUNT(*) FROM jobs
           WHERE status IN ('pending','seen','notified','saved','skipped')
           AND first_seen >= date('now', ?)""",
        (f"-{int(days)} days",),
    ).fetchone()
    return row[0]


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()