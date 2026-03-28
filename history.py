"""
history.py  –  Persistent screening history with SQLite.

Stores every screening session with all candidate data, scores, agent
evaluations, and verification results so the collective dashboard can show
historical trends sorted by date / month / year.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import CandidateScore, JDCriteria

_DB_PATH = Path(__file__).parent / "data" / "screening_history.db"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    jd_title    TEXT    NOT NULL DEFAULT '',
    jd_role     TEXT    NOT NULL DEFAULT '',
    jd_industry TEXT    NOT NULL DEFAULT '',
    jd_data     TEXT    NOT NULL DEFAULT '{}',
    total_candidates INTEGER NOT NULL DEFAULT 0,
    avg_score   REAL    NOT NULL DEFAULT 0.0,
    top_candidate TEXT  NOT NULL DEFAULT '',
    top_score   REAL    NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS candidates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL DEFAULT '',
    email       TEXT    NOT NULL DEFAULT '',
    phone       TEXT    NOT NULL DEFAULT '',
    location    TEXT    NOT NULL DEFAULT '',
    linkedin    TEXT    NOT NULL DEFAULT '',
    github      TEXT    NOT NULL DEFAULT '',
    experience_years REAL NOT NULL DEFAULT 0.0,
    skills      TEXT    NOT NULL DEFAULT '[]',
    education   TEXT    NOT NULL DEFAULT '[]',
    certifications TEXT NOT NULL DEFAULT '[]',
    source_file TEXT    NOT NULL DEFAULT '',
    overall_score REAL  NOT NULL DEFAULT 0.0,
    grade       TEXT    NOT NULL DEFAULT '',
    rank        INTEGER NOT NULL DEFAULT 0,
    breakdown   TEXT    NOT NULL DEFAULT '{}',
    matched_required TEXT NOT NULL DEFAULT '[]',
    missing_required TEXT NOT NULL DEFAULT '[]',
    matched_preferred TEXT NOT NULL DEFAULT '[]',
    verification TEXT   NOT NULL DEFAULT '{}',
    agent_consensus TEXT NOT NULL DEFAULT '{}',
    scanned_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS saved_jds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    jd_text     TEXT    NOT NULL DEFAULT '',
    jd_data     TEXT    NOT NULL DEFAULT '{}',
    tags        TEXT    NOT NULL DEFAULT '[]',
    use_count   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_candidates_session ON candidates(session_id);
CREATE INDEX IF NOT EXISTS idx_candidates_name ON candidates(name);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_saved_jds_name ON saved_jds(name);
"""


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def save_session(
    jd: JDCriteria,
    scores: list[CandidateScore],
    agent_results: Optional[dict] = None,
) -> int:
    """Save a complete screening session. Returns session_id."""
    conn = _get_conn()
    try:
        avg = sum(s.overall_score for s in scores) / max(len(scores), 1)
        top = max(scores, key=lambda s: s.overall_score) if scores else None

        cur = conn.execute(
            """INSERT INTO sessions
               (jd_title, jd_role, jd_industry, jd_data,
                total_candidates, avg_score, top_candidate, top_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                jd.title,
                jd.role_level,
                jd.industry,
                json.dumps(_safe_asdict(jd), default=str),
                len(scores),
                round(avg, 1),
                top.candidate.name if top else "",
                top.overall_score if top else 0.0,
            ),
        )
        session_id = cur.lastrowid

        for s in scores:
            agent_data = {}
            if agent_results and s.candidate.name in agent_results:
                ar = agent_results[s.candidate.name]
                agent_data = _safe_asdict(ar)

            conn.execute(
                """INSERT INTO candidates
                   (session_id, name, email, phone, location, linkedin, github,
                    experience_years, skills, education, certifications, source_file,
                    overall_score, grade, rank, breakdown,
                    matched_required, missing_required, matched_preferred,
                    verification, agent_consensus)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    s.candidate.name,
                    s.candidate.email or "",
                    s.candidate.phone or "",
                    s.candidate.location or "",
                    s.candidate.linkedin_url or "",
                    s.candidate.github_url or "",
                    s.candidate.total_experience_years,
                    json.dumps(s.candidate.skills, default=str),
                    json.dumps([_safe_asdict(e) for e in s.candidate.education], default=str),
                    json.dumps(s.candidate.certifications, default=str),
                    s.candidate.source_file or "",
                    s.overall_score,
                    s.grade,
                    s.rank,
                    json.dumps(_safe_asdict(s.breakdown), default=str),
                    json.dumps(s.matched_required_skills, default=str),
                    json.dumps(s.missing_required_skills, default=str),
                    json.dumps(s.matched_preferred_skills, default=str),
                    json.dumps(_safe_asdict(s.verification), default=str),
                    json.dumps(agent_data, default=str),
                ),
            )

        conn.commit()
        return session_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get_all_sessions() -> list[dict]:
    """Return all sessions, newest first."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_session(session_id: int) -> Optional[dict]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_candidates_for_session(session_id: int) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM candidates WHERE session_id = ? ORDER BY rank",
            (session_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Parse JSON fields
            for key in ("skills", "education", "certifications", "breakdown",
                        "matched_required", "missing_required", "matched_preferred",
                        "verification", "agent_consensus"):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result
    finally:
        conn.close()


def get_all_candidates() -> list[dict]:
    """Return all candidates across all sessions, newest first."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT c.*, s.jd_title, s.created_at as session_date
               FROM candidates c
               JOIN sessions s ON c.session_id = s.id
               ORDER BY c.scanned_at DESC"""
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for key in ("skills", "education", "certifications", "breakdown",
                        "matched_required", "missing_required", "matched_preferred",
                        "verification", "agent_consensus"):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result
    finally:
        conn.close()


def get_sessions_by_date_range(start: str, end: str) -> list[dict]:
    """Filter sessions by date range (ISO format: YYYY-MM-DD)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM sessions
               WHERE date(created_at) BETWEEN date(?) AND date(?)
               ORDER BY created_at DESC""",
            (start, end),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_sessions_by_month(year: int, month: int) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM sessions
               WHERE strftime('%Y', created_at) = ?
                 AND strftime('%m', created_at) = ?
               ORDER BY created_at DESC""",
            (str(year), f"{month:02d}"),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_sessions_by_year(year: int) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM sessions
               WHERE strftime('%Y', created_at) = ?
               ORDER BY created_at DESC""",
            (str(year),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_candidate_history(name: str) -> list[dict]:
    """All screening records for a specific candidate across sessions."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT c.*, s.jd_title, s.created_at as session_date
               FROM candidates c
               JOIN sessions s ON c.session_id = s.id
               WHERE LOWER(c.name) LIKE LOWER(?)
               ORDER BY c.scanned_at DESC""",
            (f"%{name}%",),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for key in ("skills", "education", "certifications", "breakdown",
                        "matched_required", "missing_required", "matched_preferred",
                        "verification", "agent_consensus"):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result
    finally:
        conn.close()


def get_stats_summary() -> dict:
    """Aggregate statistics for the overview dashboard."""
    conn = _get_conn()
    try:
        sess_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        cand_count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        avg_score = conn.execute("SELECT AVG(overall_score) FROM candidates").fetchone()[0] or 0.0
        top_row = conn.execute(
            "SELECT name, overall_score FROM candidates ORDER BY overall_score DESC LIMIT 1"
        ).fetchone()

        grade_dist = {}
        for row in conn.execute("SELECT grade, COUNT(*) FROM candidates GROUP BY grade").fetchall():
            grade_dist[row[0]] = row[1]

        monthly = []
        for row in conn.execute(
            """SELECT strftime('%Y-%m', created_at) as month,
                      COUNT(*) as sessions,
                      SUM(total_candidates) as candidates,
                      AVG(avg_score) as avg_score
               FROM sessions
               GROUP BY month
               ORDER BY month DESC
               LIMIT 12"""
        ).fetchall():
            monthly.append(dict(row))

        return {
            "total_sessions": sess_count,
            "total_candidates": cand_count,
            "avg_score": round(avg_score, 1),
            "top_candidate": dict(top_row) if top_row else None,
            "grade_distribution": grade_dist,
            "monthly_trend": monthly,
        }
    finally:
        conn.close()


def delete_session(session_id: int) -> bool:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_asdict(obj) -> dict:
    """Convert dataclass or dict-like object to dict safely."""
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        try:
            return asdict(obj)
        except Exception:
            return {k: getattr(obj, k, None) for k in obj.__dataclass_fields__}
    if isinstance(obj, dict):
        return obj
    return {}


# ---------------------------------------------------------------------------
# JD Management
# ---------------------------------------------------------------------------

def save_jd(name: str, jd_text: str, jd_data: dict | None = None,
            tags: list[str] | None = None) -> int:
    """Save a job description. Returns the JD id."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO saved_jds (name, jd_text, jd_data, tags)
               VALUES (?, ?, ?, ?)""",
            (
                name,
                jd_text,
                json.dumps(jd_data or {}, default=str),
                json.dumps(tags or []),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_all_jds() -> list[dict]:
    """Return all saved JDs, newest first."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM saved_jds ORDER BY updated_at DESC"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for key in ("jd_data", "tags"):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result
    finally:
        conn.close()


def get_jd(jd_id: int) -> Optional[dict]:
    """Return a single saved JD by id."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM saved_jds WHERE id = ?", (jd_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ("jd_data", "tags"):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
        return d
    finally:
        conn.close()


def update_jd(jd_id: int, name: str | None = None, jd_text: str | None = None,
              jd_data: dict | None = None, tags: list[str] | None = None) -> bool:
    """Update an existing saved JD. Only non-None fields are updated."""
    conn = _get_conn()
    try:
        updates = ["updated_at = datetime('now','localtime')"]
        params: list = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if jd_text is not None:
            updates.append("jd_text = ?")
            params.append(jd_text)
        if jd_data is not None:
            updates.append("jd_data = ?")
            params.append(json.dumps(jd_data, default=str))
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        params.append(jd_id)
        conn.execute(
            f"UPDATE saved_jds SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        return True
    finally:
        conn.close()


def delete_jd(jd_id: int) -> bool:
    """Delete a saved JD."""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM saved_jds WHERE id = ?", (jd_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def increment_jd_use_count(jd_id: int) -> None:
    """Increment the use_count for a saved JD."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE saved_jds SET use_count = use_count + 1, updated_at = datetime('now','localtime') WHERE id = ?",
            (jd_id,),
        )
        conn.commit()
    finally:
        conn.close()
