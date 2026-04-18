"""Tests for comparator.py — multi-candidate comparison engine."""

from __future__ import annotations

from comparator import CandidateComparison, ComparisonMatrix, DimensionScore, compare_candidates


class TestCompareCandidates:
    def test_returns_comparison_matrix(self, sample_score, weak_score, sample_jd):
        matrix = compare_candidates([sample_score, weak_score], sample_jd)
        assert isinstance(matrix, ComparisonMatrix)

    def test_candidates_list(self, sample_score, weak_score, sample_jd):
        matrix = compare_candidates([sample_score, weak_score], sample_jd)
        assert len(matrix.candidates) == 2
        assert all(isinstance(c, CandidateComparison) for c in matrix.candidates)

    def test_jd_title(self, sample_score, sample_jd):
        matrix = compare_candidates([sample_score], sample_jd)
        assert matrix.jd_title == sample_jd.title

    def test_dimension_names(self, sample_score, weak_score, sample_jd):
        matrix = compare_candidates([sample_score, weak_score], sample_jd)
        assert isinstance(matrix.dimension_names, list)
        assert len(matrix.dimension_names) >= 5  # at least 5 dimensions

    def test_stack_rank(self, sample_score, weak_score, sample_jd):
        matrix = compare_candidates([sample_score, weak_score], sample_jd)
        assert isinstance(matrix.stack_rank, list)
        assert len(matrix.stack_rank) == 2
        # Strong candidate should rank higher
        assert matrix.stack_rank[0] == "Alice Johnson"

    def test_best_per_dimension(self, sample_score, weak_score, sample_jd):
        matrix = compare_candidates([sample_score, weak_score], sample_jd)
        assert isinstance(matrix.best_per_dimension, dict)
        assert len(matrix.best_per_dimension) > 0

    def test_candidate_dimensions(self, sample_score, weak_score, sample_jd):
        matrix = compare_candidates([sample_score, weak_score], sample_jd)
        for cand in matrix.candidates:
            assert isinstance(cand.dimensions, list)
            for dim in cand.dimensions:
                assert isinstance(dim, DimensionScore)
                assert 0 <= dim.raw_score <= 100
                assert dim.weight >= 0

    def test_radar_data(self, sample_score, weak_score, sample_jd):
        matrix = compare_candidates([sample_score, weak_score], sample_jd)
        for cand in matrix.candidates:
            assert isinstance(cand.radar_data, dict)
            assert len(cand.radar_data) > 0
            for v in cand.radar_data.values():
                assert 0 <= v <= 100

    def test_overall_composite_bounded(self, sample_score, weak_score, sample_jd):
        matrix = compare_candidates([sample_score, weak_score], sample_jd)
        for cand in matrix.candidates:
            assert 0 <= cand.overall_composite <= 100

    def test_strengths_and_weaknesses(self, sample_score, weak_score, sample_jd):
        matrix = compare_candidates([sample_score, weak_score], sample_jd)
        for cand in matrix.candidates:
            assert isinstance(cand.strengths, list)
            assert isinstance(cand.weaknesses, list)

    def test_with_red_flag_reports(self, sample_score, weak_score, sample_jd, sample_candidate, weak_candidate):
        from red_flags import detect_red_flags

        rf_alice = detect_red_flags(sample_candidate, sample_jd)
        rf_bob = detect_red_flags(weak_candidate, sample_jd)
        rf_map = {"Alice Johnson": rf_alice, "Bob Weak": rf_bob}
        matrix = compare_candidates([sample_score, weak_score], sample_jd, red_flag_reports=rf_map)
        assert isinstance(matrix, ComparisonMatrix)

    def test_single_candidate(self, sample_score, sample_jd):
        matrix = compare_candidates([sample_score], sample_jd)
        assert len(matrix.candidates) == 1
        assert len(matrix.stack_rank) == 1
