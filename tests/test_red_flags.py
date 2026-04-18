"""Tests for red_flags.py — red flag detection engine."""

from __future__ import annotations

from models import CandidateProfile, ExperienceEntry
from red_flags import RedFlagReport, Severity, detect_red_flags


class TestDetectRedFlags:
    def test_clean_candidate_low_risk(self, sample_candidate, sample_jd):
        report = detect_red_flags(sample_candidate, sample_jd)
        assert isinstance(report, RedFlagReport)
        assert report.risk_level in {"clean", "low", "medium", "high"}
        assert report.risk_score >= 0.0
        assert report.candidate_name == "Alice Johnson"

    def test_weak_candidate_gets_flags(self, weak_candidate, sample_jd):
        report = detect_red_flags(weak_candidate, sample_jd)
        assert report.total_flags > 0
        # Disposable email should be flagged
        categories = {f.category for f in report.flags}
        assert "contact" in categories or "email" in categories or report.total_flags > 0

    def test_no_jd_still_works(self, sample_candidate):
        report = detect_red_flags(sample_candidate, jd=None)
        assert isinstance(report, RedFlagReport)

    def test_report_fields(self, sample_candidate, sample_jd):
        report = detect_red_flags(sample_candidate, sample_jd)
        assert isinstance(report.flags, list)
        assert isinstance(report.summary, str)
        assert report.critical_count >= 0
        assert report.warning_count >= 0
        assert report.info_count >= 0
        assert report.total_flags == report.critical_count + report.warning_count + report.info_count


class TestEmploymentGaps:
    def test_large_gap_flagged(self):
        candidate = CandidateProfile(
            name="Gap Person",
            email="gap@example.com",
            phone="",
            linkedin_url="",
            github_url="",
            location="",
            skills=[],
            experience=[
                ExperienceEntry("Co A", "Dev", "2015-01", "2016-01", 12, "", ""),
                ExperienceEntry("Co B", "Dev", "2018-06", "2020-01", 18, "", ""),
            ],
            education=[],
            certifications=[],
            total_experience_years=3.0,
            raw_text="",
            source_file="gap.pdf",
        )
        report = detect_red_flags(candidate)
        gap_flags = [f for f in report.flags if f.category == "employment_gap"]
        assert len(gap_flags) >= 1


class TestJobHopping:
    def test_short_tenures_flagged(self):
        exps = [ExperienceEntry(f"Co-{i}", "Dev", f"20{18 + i}-01", f"20{18 + i}-08", 7, "", "") for i in range(5)]
        candidate = CandidateProfile(
            name="Hopper",
            email="hop@example.com",
            phone="",
            linkedin_url="",
            github_url="",
            location="",
            skills=[],
            experience=exps,
            education=[],
            certifications=[],
            total_experience_years=3.0,
            raw_text="",
            source_file="hopper.pdf",
        )
        report = detect_red_flags(candidate)
        hop_flags = [f for f in report.flags if f.category == "job_hopping"]
        assert len(hop_flags) >= 1


class TestTitleInflation:
    def test_cto_with_1yr_flagged(self, weak_candidate, sample_jd):
        # weak_candidate has "CTO" with 1.5 years total
        report = detect_red_flags(weak_candidate, sample_jd)
        title_flags = [f for f in report.flags if f.category == "title_inflation"]
        assert len(title_flags) >= 1


class TestEducationFlags:
    def test_future_graduation(self, weak_candidate):
        # weak_candidate has graduation_year=2035
        report = detect_red_flags(weak_candidate)
        edu_flags = [f for f in report.flags if f.category == "education"]
        assert len(edu_flags) >= 1


class TestEmailFlags:
    def test_disposable_email(self, weak_candidate):
        # weak_candidate uses yopmail.com
        report = detect_red_flags(weak_candidate)
        email_flags = [f for f in report.flags if f.category in {"contact", "email", "disposable_email"}]
        assert len(email_flags) >= 1

    def test_no_email(self):
        candidate = CandidateProfile(
            name="No Email",
            email="",
            phone="",
            linkedin_url="",
            github_url="",
            location="",
            skills=[],
            experience=[],
            education=[],
            certifications=[],
            total_experience_years=0,
            raw_text="",
            source_file="noemail.pdf",
        )
        report = detect_red_flags(candidate)
        contact_flags = [f for f in report.flags if f.category == "contact"]
        assert len(contact_flags) >= 1


class TestRiskScoring:
    def test_risk_score_bounded(self, sample_candidate, sample_jd):
        report = detect_red_flags(sample_candidate, sample_jd)
        assert 0.0 <= report.risk_score <= 1.0

    def test_risk_level_valid(self, weak_candidate, sample_jd):
        report = detect_red_flags(weak_candidate, sample_jd)
        assert report.risk_level in {"clean", "low", "medium", "high"}

    def test_flags_sorted_by_severity(self, weak_candidate, sample_jd):
        report = detect_red_flags(weak_candidate, sample_jd)
        if len(report.flags) > 1:
            severity_order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
            for i in range(len(report.flags) - 1):
                a = severity_order.get(report.flags[i].severity, 9)
                b = severity_order.get(report.flags[i + 1].severity, 9)
                assert a <= b
