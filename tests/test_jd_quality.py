"""Tests for jd_quality.py — JD quality scoring."""

from __future__ import annotations

from jd_quality import JDQualityReport, QualityDimension, analyze_jd_quality


class TestAnalyzeJDQuality:
    def test_basic_report_structure(self, sample_jd):
        report = analyze_jd_quality(sample_jd)
        assert isinstance(report, JDQualityReport)
        assert 0 <= report.overall_score <= 100
        assert report.grade in {"A+", "A", "B+", "B", "C", "D", "F"}
        assert isinstance(report.dimensions, list)
        assert len(report.dimensions) > 0

    def test_dimensions_have_correct_fields(self, sample_jd):
        report = analyze_jd_quality(sample_jd)
        for dim in report.dimensions:
            assert isinstance(dim, QualityDimension)
            assert isinstance(dim.name, str)
            assert 0 <= dim.score <= 100
            assert 0 <= dim.weight <= 1
            assert isinstance(dim.issues, list)
            assert isinstance(dim.suggestions, list)

    def test_word_count_and_read_time(self, sample_jd):
        report = analyze_jd_quality(sample_jd)
        assert report.word_count > 0
        assert report.estimated_read_time_min > 0

    def test_red_flags_and_strengths(self, sample_jd):
        report = analyze_jd_quality(sample_jd)
        assert isinstance(report.red_flags, list)
        assert isinstance(report.strengths, list)

    def test_summary_is_nonempty(self, sample_jd):
        report = analyze_jd_quality(sample_jd)
        assert isinstance(report.summary, str)
        assert len(report.summary) > 10

    def test_minimal_jd_scores_lower(self, sample_jd):
        """A JD with almost no text should score worse than a normal one."""
        from models import JDCriteria

        bare = JDCriteria(
            title="Dev",
            required_skills=[],
            preferred_skills=[],
            min_experience_years=0,
            max_experience_years=0,
            education_level="Any",
            certifications_required=[],
            certifications_preferred=[],
            industry="",
            role_level="",
            keywords=[],
            raw_text="We need a dev.",
        )
        report_bare = analyze_jd_quality(bare)
        report_full = analyze_jd_quality(sample_jd)
        assert report_bare.overall_score <= report_full.overall_score
