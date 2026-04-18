"""Tests for history.py — screening history database."""

from __future__ import annotations

import pytest

from history import (
    delete_jd,
    delete_session,
    get_all_jds,
    get_all_sessions,
    get_candidates_for_session,
    get_jd,
    get_session,
    get_stats_summary,
    save_jd,
    save_session,
)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Route history DB to a temp file so tests don't pollute real data."""
    db_path = tmp_path / "test_history.db"
    monkeypatch.setattr("history._DB_PATH", db_path)


class TestSessions:
    def test_save_and_retrieve_session(self, sample_score, sample_jd):
        sid = save_session(jd=sample_jd, scores=[sample_score])
        assert isinstance(sid, int)
        sessions = get_all_sessions()
        assert len(sessions) >= 1

    def test_get_session(self, sample_score, sample_jd):
        sid = save_session(jd=sample_jd, scores=[sample_score])
        session = get_session(sid)
        assert session is not None
        assert session["jd_title"] == sample_jd.title

    def test_get_candidates_for_session(self, sample_score, sample_jd):
        sid = save_session(jd=sample_jd, scores=[sample_score])
        cands = get_candidates_for_session(sid)
        assert isinstance(cands, list)
        assert len(cands) >= 1

    def test_delete_session(self, sample_score, sample_jd):
        sid = save_session(jd=sample_jd, scores=[sample_score])
        result = delete_session(sid)
        assert result is True
        session = get_session(sid)
        assert session is None


class TestJDs:
    def test_save_and_list_jds(self):
        jid = save_jd(name="Test JD", jd_text="Some JD text")
        assert isinstance(jid, int)
        jds = get_all_jds()
        assert len(jds) >= 1

    def test_get_jd(self):
        jid = save_jd(name="Another JD", jd_text="Another text")
        jd = get_jd(jid)
        assert jd is not None
        assert jd["name"] == "Another JD"

    def test_delete_jd(self):
        jid = save_jd(name="Del JD", jd_text="Delete me")
        result = delete_jd(jid)
        assert result is True
        jd = get_jd(jid)
        assert jd is None


class TestStats:
    def test_stats_summary(self, sample_score, sample_jd):
        save_session(jd=sample_jd, scores=[sample_score])
        stats = get_stats_summary()
        assert isinstance(stats, dict)
        assert stats.get("total_sessions", 0) >= 1
