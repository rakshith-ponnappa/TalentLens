"""
pipeline.py  –  Candidate Pipeline State Management.

Tracks candidates through hiring stages with full audit trail:
  Uploaded → Parsed → Scored → Shortlisted → Interview Scheduled →
  Interviewed → Offer Extended → Hired / Rejected / Withdrawn

Features:
  - SQLite-backed state machine with transition validation
  - Batch operations (move N candidates to next stage)
  - Pipeline analytics (funnel metrics, stage durations, conversion rates)
  - Audit log for every state change
  - Notes/tags per candidate per stage
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

class Stage(str, Enum):
    UPLOADED     = "uploaded"
    PARSED       = "parsed"
    SCORED       = "scored"
    SHORTLISTED  = "shortlisted"
    INTERVIEW    = "interview_scheduled"
    INTERVIEWED  = "interviewed"
    OFFER        = "offer_extended"
    HIRED        = "hired"
    REJECTED     = "rejected"
    WITHDRAWN    = "withdrawn"

    @property
    def display(self) -> str:
        return self.value.replace("_", " ").title()

    @property
    def is_terminal(self) -> bool:
        return self in {Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN}

    @property
    def order(self) -> int:
        """Ordinal for funnel ordering."""
        return {
            Stage.UPLOADED: 0, Stage.PARSED: 1, Stage.SCORED: 2,
            Stage.SHORTLISTED: 3, Stage.INTERVIEW: 4, Stage.INTERVIEWED: 5,
            Stage.OFFER: 6, Stage.HIRED: 7, Stage.REJECTED: 8, Stage.WITHDRAWN: 9,
        }[self]


# Valid transitions (from → allowed targets)
_TRANSITIONS: dict[Stage, set[Stage]] = {
    Stage.UPLOADED:    {Stage.PARSED, Stage.REJECTED, Stage.WITHDRAWN},
    Stage.PARSED:      {Stage.SCORED, Stage.REJECTED, Stage.WITHDRAWN},
    Stage.SCORED:      {Stage.SHORTLISTED, Stage.REJECTED, Stage.WITHDRAWN},
    Stage.SHORTLISTED: {Stage.INTERVIEW, Stage.REJECTED, Stage.WITHDRAWN},
    Stage.INTERVIEW:   {Stage.INTERVIEWED, Stage.REJECTED, Stage.WITHDRAWN},
    Stage.INTERVIEWED: {Stage.OFFER, Stage.REJECTED, Stage.WITHDRAWN},
    Stage.OFFER:       {Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN},
    # Terminal stages — no further transitions
    Stage.HIRED:       set(),
    Stage.REJECTED:    set(),
    Stage.WITHDRAWN:   set(),
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PipelineCandidate:
    id: int
    session_id: int
    name: str
    email: str
    source_file: str
    current_stage: Stage
    score: float
    grade: str
    tags: list[str]
    notes: str
    created_at: str
    updated_at: str


@dataclass
class StageTransition:
    id: int
    candidate_id: int
    from_stage: str
    to_stage: str
    changed_by: str
    reason: str
    timestamp: str


@dataclass
class FunnelMetrics:
    stage: str
    count: int
    pct_of_total: float
    avg_score: float
    avg_days_in_stage: float


@dataclass
class PipelineStats:
    total_candidates: int
    active_candidates: int
    stage_counts: dict[str, int]
    funnel: list[FunnelMetrics]
    conversion_rates: dict[str, float]   # "scored→shortlisted": 0.45
    avg_time_to_hire_days: float
    rejection_rate: float
    top_rejection_stage: str


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_DB_PATH = Path(__file__).parent / "data" / "screening_history.db"

_PIPELINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_candidates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL DEFAULT 0,
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL DEFAULT '',
    source_file TEXT    NOT NULL DEFAULT '',
    current_stage TEXT  NOT NULL DEFAULT 'uploaded',
    score       REAL    NOT NULL DEFAULT 0.0,
    grade       TEXT    NOT NULL DEFAULT '',
    tags        TEXT    NOT NULL DEFAULT '[]',
    notes       TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS pipeline_transitions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES pipeline_candidates(id) ON DELETE CASCADE,
    from_stage   TEXT    NOT NULL,
    to_stage     TEXT    NOT NULL,
    changed_by   TEXT    NOT NULL DEFAULT 'system',
    reason       TEXT    NOT NULL DEFAULT '',
    timestamp    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_pipeline_stage ON pipeline_candidates(current_stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_session ON pipeline_candidates(session_id);
CREATE INDEX IF NOT EXISTS idx_transitions_candidate ON pipeline_transitions(candidate_id);
"""


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_PIPELINE_SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def add_candidate(
    name: str,
    email: str = "",
    source_file: str = "",
    session_id: int = 0,
    score: float = 0.0,
    grade: str = "",
    tags: list[str] | None = None,
    notes: str = "",
    stage: Stage = Stage.UPLOADED,
) -> int:
    """Add a candidate to the pipeline. Returns the candidate ID."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO pipeline_candidates
           (session_id, name, email, source_file, current_stage, score, grade, tags, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, name, email, source_file, stage.value, score, grade,
         json.dumps(tags or []), notes),
    )
    conn.commit()
    cid = cur.lastrowid

    # Record initial transition
    conn.execute(
        """INSERT INTO pipeline_transitions (candidate_id, from_stage, to_stage, reason)
           VALUES (?, '', ?, 'initial')""",
        (cid, stage.value),
    )
    conn.commit()
    conn.close()
    return cid


def transition(
    candidate_id: int,
    to_stage: Stage,
    reason: str = "",
    changed_by: str = "system",
) -> bool:
    """Move a candidate to a new stage. Returns True on success."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT current_stage FROM pipeline_candidates WHERE id = ?",
        (candidate_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise ValueError(f"Candidate {candidate_id} not found")

    current = Stage(row["current_stage"])

    if to_stage not in _TRANSITIONS.get(current, set()):
        conn.close()
        raise ValueError(
            f"Invalid transition: {current.display} → {to_stage.display}. "
            f"Allowed: {', '.join(s.display for s in _TRANSITIONS.get(current, set()))}"
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE pipeline_candidates SET current_stage = ?, updated_at = ? WHERE id = ?",
        (to_stage.value, now, candidate_id),
    )
    conn.execute(
        """INSERT INTO pipeline_transitions
           (candidate_id, from_stage, to_stage, changed_by, reason)
           VALUES (?, ?, ?, ?, ?)""",
        (candidate_id, current.value, to_stage.value, changed_by, reason),
    )
    conn.commit()
    conn.close()
    return True


def batch_transition(
    candidate_ids: list[int],
    to_stage: Stage,
    reason: str = "",
    changed_by: str = "system",
) -> dict[int, str]:
    """Move multiple candidates. Returns {id: "ok" | "error: ..."} map."""
    results = {}
    for cid in candidate_ids:
        try:
            transition(cid, to_stage, reason, changed_by)
            results[cid] = "ok"
        except ValueError as e:
            results[cid] = f"error: {e}"
    return results


def update_score(candidate_id: int, score: float, grade: str) -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE pipeline_candidates SET score = ?, grade = ?, updated_at = datetime('now','localtime') WHERE id = ?",
        (score, grade, candidate_id),
    )
    conn.commit()
    conn.close()


def add_tags(candidate_id: int, new_tags: list[str]) -> None:
    conn = _get_conn()
    row = conn.execute("SELECT tags FROM pipeline_candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row:
        existing = json.loads(row["tags"])
        merged = list(set(existing + new_tags))
        conn.execute(
            "UPDATE pipeline_candidates SET tags = ?, updated_at = datetime('now','localtime') WHERE id = ?",
            (json.dumps(merged), candidate_id),
        )
        conn.commit()
    conn.close()


def update_notes(candidate_id: int, notes: str) -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE pipeline_candidates SET notes = ?, updated_at = datetime('now','localtime') WHERE id = ?",
        (notes, candidate_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _row_to_candidate(row: sqlite3.Row) -> PipelineCandidate:
    return PipelineCandidate(
        id=row["id"],
        session_id=row["session_id"],
        name=row["name"],
        email=row["email"],
        source_file=row["source_file"],
        current_stage=Stage(row["current_stage"]),
        score=row["score"],
        grade=row["grade"],
        tags=json.loads(row["tags"]),
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_candidate(candidate_id: int) -> PipelineCandidate | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM pipeline_candidates WHERE id = ?", (candidate_id,)).fetchone()
    conn.close()
    return _row_to_candidate(row) if row else None


def list_candidates(
    stage: Stage | None = None,
    session_id: int | None = None,
    min_score: float = 0.0,
    tags: list[str] | None = None,
    limit: int = 200,
) -> list[PipelineCandidate]:
    conn = _get_conn()
    query = "SELECT * FROM pipeline_candidates WHERE score >= ?"
    params: list = [min_score]

    if stage:
        query += " AND current_stage = ?"
        params.append(stage.value)
    if session_id is not None:
        query += " AND session_id = ?"
        params.append(session_id)

    query += " ORDER BY score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    candidates = [_row_to_candidate(r) for r in rows]

    # Filter by tags in Python (JSON column)
    if tags:
        tag_set = set(t.lower() for t in tags)
        candidates = [
            c for c in candidates
            if tag_set & set(t.lower() for t in c.tags)
        ]

    return candidates


def get_transitions(candidate_id: int) -> list[StageTransition]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM pipeline_transitions WHERE candidate_id = ? ORDER BY timestamp",
        (candidate_id,),
    ).fetchall()
    conn.close()
    return [
        StageTransition(
            id=r["id"], candidate_id=r["candidate_id"],
            from_stage=r["from_stage"], to_stage=r["to_stage"],
            changed_by=r["changed_by"], reason=r["reason"],
            timestamp=r["timestamp"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def get_pipeline_stats(session_id: int | None = None) -> PipelineStats:
    conn = _get_conn()

    where = ""
    params: list = []
    if session_id is not None:
        where = "WHERE session_id = ?"
        params = [session_id]

    # Stage counts
    rows = conn.execute(
        f"SELECT current_stage, COUNT(*) as cnt, AVG(score) as avg_score "
        f"FROM pipeline_candidates {where} GROUP BY current_stage",
        params,
    ).fetchall()

    stage_counts = {r["current_stage"]: r["cnt"] for r in rows}
    total = sum(stage_counts.values())
    active = total - stage_counts.get("hired", 0) - stage_counts.get("rejected", 0) - stage_counts.get("withdrawn", 0)

    # Funnel metrics
    funnel = []
    for stage in Stage:
        if stage.is_terminal:
            continue
        cnt = stage_counts.get(stage.value, 0)
        avg_s = next((r["avg_score"] for r in rows if r["current_stage"] == stage.value), 0.0)
        funnel.append(FunnelMetrics(
            stage=stage.display,
            count=cnt,
            pct_of_total=round(cnt / max(total, 1) * 100, 1),
            avg_score=round(avg_s or 0, 1),
            avg_days_in_stage=0.0,  # computed below
        ))

    # Conversion rates between consecutive non-terminal stages
    conversion = {}
    ordered = [s for s in Stage if not s.is_terminal]
    for i in range(len(ordered) - 1):
        from_s = ordered[i]
        to_s = ordered[i + 1]
        from_count = stage_counts.get(from_s.value, 0)
        # "Made it past" = count in to_s or any later stage
        later_stages = ordered[i + 1:]
        later_count = sum(stage_counts.get(s.value, 0) for s in later_stages)
        # Also count terminal states that were reached from later stages
        later_count += stage_counts.get("hired", 0)
        rate = later_count / max(from_count + later_count, 1)
        conversion[f"{from_s.display} → {to_s.display}"] = round(rate, 3)

    # Rejection rate
    rejected_count = stage_counts.get("rejected", 0) + stage_counts.get("withdrawn", 0)
    rejection_rate = rejected_count / max(total, 1)

    # Top rejection stage
    rej_by_stage = conn.execute(
        f"""SELECT from_stage, COUNT(*) as cnt FROM pipeline_transitions
            WHERE to_stage IN ('rejected', 'withdrawn')
            {"AND candidate_id IN (SELECT id FROM pipeline_candidates WHERE session_id = ?)" if session_id else ""}
            GROUP BY from_stage ORDER BY cnt DESC LIMIT 1""",
        params,
    ).fetchone()

    top_rej = rej_by_stage["from_stage"] if rej_by_stage else "N/A"

    # Average time to hire
    hire_times = conn.execute(
        f"""SELECT pc.created_at, pt.timestamp
            FROM pipeline_candidates pc
            JOIN pipeline_transitions pt ON pt.candidate_id = pc.id
            WHERE pt.to_stage = 'hired'
            {"AND pc.session_id = ?" if session_id else ""}""",
        params,
    ).fetchall()

    avg_hire_days = 0.0
    if hire_times:
        days_list = []
        for r in hire_times:
            try:
                created = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S")
                hired_at = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
                days_list.append((hired_at - created).days)
            except (ValueError, TypeError):
                pass
        if days_list:
            avg_hire_days = sum(days_list) / len(days_list)

    conn.close()

    return PipelineStats(
        total_candidates=total,
        active_candidates=active,
        stage_counts=stage_counts,
        funnel=funnel,
        conversion_rates=conversion,
        avg_time_to_hire_days=round(avg_hire_days, 1),
        rejection_rate=round(rejection_rate, 3),
        top_rejection_stage=top_rej,
    )


def get_stage_distribution(session_id: int | None = None) -> dict[str, int]:
    """Simple stage → count map for dashboard charts."""
    conn = _get_conn()
    where = "WHERE session_id = ?" if session_id else ""
    params = [session_id] if session_id else []
    rows = conn.execute(
        f"SELECT current_stage, COUNT(*) as cnt FROM pipeline_candidates {where} GROUP BY current_stage",
        params,
    ).fetchall()
    conn.close()
    return {r["current_stage"]: r["cnt"] for r in rows}
