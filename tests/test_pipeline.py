"""Tests for pipeline.py — stage machine, CRUD, analytics."""

from __future__ import annotations

import pytest

from pipeline import (
    PipelineCandidate,
    PipelineStats,
    Stage,
    add_candidate,
    add_tags,
    batch_transition,
    get_candidate,
    get_pipeline_stats,
    get_stage_distribution,
    get_transitions,
    list_candidates,
    transition,
    update_notes,
    update_score,
)

# ---------------------------------------------------------------------------
# Use an in-memory / temp DB for every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Route pipeline DB to a temp file so tests don't pollute real data."""
    db_path = tmp_path / "test_pipeline.db"
    monkeypatch.setattr("pipeline._DB_PATH", db_path)


# ---------------------------------------------------------------------------
# Stage enum tests
# ---------------------------------------------------------------------------


class TestStage:
    def test_display_name(self):
        assert Stage.UPLOADED.display == "Uploaded"
        assert Stage.INTERVIEW.display == "Interview Scheduled"

    def test_terminal_stages(self):
        assert Stage.HIRED.is_terminal is True
        assert Stage.REJECTED.is_terminal is True
        assert Stage.WITHDRAWN.is_terminal is True
        assert Stage.SCORED.is_terminal is False

    def test_order(self):
        assert Stage.UPLOADED.order < Stage.PARSED.order < Stage.SCORED.order


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class TestAddCandidate:
    def test_basic_add(self):
        cid = add_candidate(name="Alice", email="a@b.com", source_file="a.pdf")
        assert isinstance(cid, int)
        assert cid > 0

    def test_default_stage_is_uploaded(self):
        cid = add_candidate(name="Bob")
        cand = get_candidate(cid)
        assert cand is not None
        assert cand.current_stage == Stage.UPLOADED

    def test_custom_initial_stage(self):
        cid = add_candidate(name="Carol", stage=Stage.PARSED)
        cand = get_candidate(cid)
        assert cand.current_stage == Stage.PARSED

    def test_initial_transition_logged(self):
        cid = add_candidate(name="Dave")
        transitions = get_transitions(cid)
        assert len(transitions) == 1
        assert transitions[0].to_stage == Stage.UPLOADED.value
        assert transitions[0].reason == "initial"


class TestTransition:
    def test_valid_transition(self):
        cid = add_candidate(name="Eve")
        assert transition(cid, Stage.PARSED) is True
        cand = get_candidate(cid)
        assert cand.current_stage == Stage.PARSED

    def test_invalid_transition_raises(self):
        cid = add_candidate(name="Frank")
        with pytest.raises(ValueError, match="Invalid transition"):
            transition(cid, Stage.HIRED)  # UPLOADED → HIRED is not allowed

    def test_nonexistent_candidate(self):
        with pytest.raises(ValueError, match="not found"):
            transition(99999, Stage.PARSED)

    def test_terminal_no_further(self):
        cid = add_candidate(name="Grace")
        transition(cid, Stage.REJECTED, reason="not a fit")
        with pytest.raises(ValueError, match="Invalid transition"):
            transition(cid, Stage.PARSED)

    def test_full_happy_path(self):
        cid = add_candidate(name="Heidi", score=85.0, grade="A")
        for next_stage in [
            Stage.PARSED,
            Stage.SCORED,
            Stage.SHORTLISTED,
            Stage.INTERVIEW,
            Stage.INTERVIEWED,
            Stage.OFFER,
            Stage.HIRED,
        ]:
            transition(cid, next_stage)
        cand = get_candidate(cid)
        assert cand.current_stage == Stage.HIRED

    def test_transition_audit_trail(self):
        cid = add_candidate(name="Ivan")
        transition(cid, Stage.PARSED, reason="parsed ok")
        transition(cid, Stage.SCORED, reason="scored")
        transitions = get_transitions(cid)
        assert len(transitions) == 3  # initial + 2 transitions
        assert transitions[1].from_stage == "uploaded"
        assert transitions[1].to_stage == "parsed"


class TestBatchTransition:
    def test_batch(self):
        ids = [add_candidate(name=f"Batch-{i}") for i in range(5)]
        # Move all to PARSED
        results = batch_transition(ids, Stage.PARSED)
        assert all(v == "ok" for v in results.values())

    def test_batch_partial_failure(self):
        id1 = add_candidate(name="Good")
        id2 = add_candidate(name="Bad")
        transition(id2, Stage.REJECTED)  # terminal
        results = batch_transition([id1, id2], Stage.PARSED)
        assert results[id1] == "ok"
        assert "error" in results[id2]


class TestUpdateScore:
    def test_update_score(self):
        cid = add_candidate(name="Kim")
        update_score(cid, 91.5, "A+")
        cand = get_candidate(cid)
        assert cand.score == 91.5
        assert cand.grade == "A+"


class TestTags:
    def test_add_tags(self):
        cid = add_candidate(name="Leo")
        add_tags(cid, ["strong", "referred"])
        cand = get_candidate(cid)
        assert "strong" in cand.tags
        assert "referred" in cand.tags

    def test_add_tags_dedup(self):
        cid = add_candidate(name="Mia")
        add_tags(cid, ["a", "b"])
        add_tags(cid, ["b", "c"])
        cand = get_candidate(cid)
        assert sorted(cand.tags) == ["a", "b", "c"]


class TestNotes:
    def test_update_notes(self):
        cid = add_candidate(name="Nina")
        update_notes(cid, "Great communicator")
        cand = get_candidate(cid)
        assert cand.notes == "Great communicator"


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class TestListCandidates:
    def test_list_all(self):
        add_candidate(name="P1", score=50)
        add_candidate(name="P2", score=80)
        cands = list_candidates()
        assert len(cands) >= 2
        assert all(isinstance(c, PipelineCandidate) for c in cands)

    def test_filter_by_stage(self):
        cid = add_candidate(name="Q1")
        transition(cid, Stage.PARSED)
        add_candidate(name="Q2")  # stays UPLOADED
        parsed = list_candidates(stage=Stage.PARSED)
        assert all(c.current_stage == Stage.PARSED for c in parsed)

    def test_filter_by_min_score(self):
        add_candidate(name="R1", score=30)
        add_candidate(name="R2", score=90)
        high = list_candidates(min_score=60)
        assert all(c.score >= 60 for c in high)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class TestAnalytics:
    def test_pipeline_stats_structure(self):
        add_candidate(name="S1", score=70)
        add_candidate(name="S2", score=40)
        stats = get_pipeline_stats()
        assert isinstance(stats, PipelineStats)
        assert stats.total_candidates >= 2
        assert isinstance(stats.stage_counts, dict)
        assert isinstance(stats.conversion_rates, dict)

    def test_stage_distribution(self):
        add_candidate(name="T1")
        cid = add_candidate(name="T2")
        transition(cid, Stage.PARSED)
        dist = get_stage_distribution()
        assert isinstance(dist, dict)
        assert dist.get("uploaded", 0) >= 1
        assert dist.get("parsed", 0) >= 1
