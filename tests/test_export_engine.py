"""Tests for export_engine.py — multi-format report exports."""

from __future__ import annotations

from pathlib import Path

import pytest

from export_engine import (
    export_candidate_report,
    export_comparative_report,
    export_executive_summary,
)


class TestExportCandidateReport:
    def test_markdown_export(self, sample_score, sample_jd, tmp_output):
        path = export_candidate_report(sample_score, sample_jd, fmt="md", output_dir=tmp_output)
        assert isinstance(path, str)
        p = Path(path)
        assert p.exists()
        assert p.suffix == ".md"
        content = p.read_text()
        assert "Alice Johnson" in content

    def test_json_export(self, sample_score, sample_jd, tmp_output):
        path = export_candidate_report(sample_score, sample_jd, fmt="json", output_dir=tmp_output)
        p = Path(path)
        assert p.exists()
        assert p.suffix == ".json"
        import json

        data = json.loads(p.read_text())
        assert isinstance(data, dict)

    def test_html_export(self, sample_score, sample_jd, tmp_output):
        path = export_candidate_report(sample_score, sample_jd, fmt="html", output_dir=tmp_output)
        p = Path(path)
        assert p.exists()
        content = p.read_text()
        assert "<html" in content.lower() or "<div" in content.lower()

    def test_unsupported_format_raises(self, sample_score, sample_jd, tmp_output):
        with pytest.raises(ValueError, match="Unsupported format"):
            export_candidate_report(sample_score, sample_jd, fmt="xyz", output_dir=tmp_output)


class TestExportComparativeReport:
    def test_markdown_comparative(self, sample_score, weak_score, sample_jd, tmp_output):
        path = export_comparative_report([sample_score, weak_score], sample_jd, fmt="md", output_dir=tmp_output)
        p = Path(path)
        assert p.exists()
        content = p.read_text()
        assert "Alice" in content
        assert "Bob" in content or "Weak" in content

    def test_csv_comparative(self, sample_score, weak_score, sample_jd, tmp_output):
        path = export_comparative_report([sample_score, weak_score], sample_jd, fmt="csv", output_dir=tmp_output)
        p = Path(path)
        assert p.exists()
        assert p.suffix == ".csv"


class TestExportExecutiveSummary:
    def test_executive_summary(self, sample_score, weak_score, sample_jd, tmp_output):
        path = export_executive_summary([sample_score, weak_score], sample_jd, output_dir=tmp_output)
        p = Path(path)
        assert p.exists()
        content = p.read_text()
        assert len(content) > 50
