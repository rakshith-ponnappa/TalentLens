"""Tests for archetypes.py — role archetype classification."""

from __future__ import annotations

from archetypes import ArchetypeMatch, ArchetypeResult, classify_role
from models import JDCriteria


class TestClassifyRole:
    def test_returns_archetype_result(self, sample_jd):
        result = classify_role(sample_jd)
        assert isinstance(result, ArchetypeResult)

    def test_primary_archetype_present(self, sample_jd):
        result = classify_role(sample_jd)
        assert isinstance(result.primary, ArchetypeMatch)
        assert result.primary.archetype  # non-empty
        assert 0.0 <= result.primary.confidence <= 1.0

    def test_cloud_jd_matches_cloud_archetype(self, sample_jd):
        result = classify_role(sample_jd)
        # sample_jd has terraform, kubernetes, aws — should match cloud/devops
        cloud_related = {"Cloud/DevOps Engineer", "Platform Engineer", "SRE/Reliability Engineer", "Cloud Architect"}
        assert result.primary.archetype in cloud_related

    def test_archetype_has_interview_focus(self, sample_jd):
        result = classify_role(sample_jd)
        assert isinstance(result.primary.interview_focus, list)
        assert len(result.primary.interview_focus) > 0

    def test_archetype_has_key_skills(self, sample_jd):
        result = classify_role(sample_jd)
        assert isinstance(result.primary.key_skills, list)
        assert len(result.primary.key_skills) > 0

    def test_role_complexity(self, sample_jd):
        result = classify_role(sample_jd)
        assert result.role_complexity in {"individual_contributor", "leadership", "hybrid"}

    def test_suggested_panel(self, sample_jd):
        result = classify_role(sample_jd)
        assert isinstance(result.suggested_panel, list)

    def test_data_engineering_jd(self):
        jd = JDCriteria(
            title="Senior Data Engineer",
            required_skills=["spark", "airflow", "python", "sql", "data warehouse"],
            preferred_skills=["kafka", "dbt", "snowflake"],
            min_experience_years=5,
            max_experience_years=10,
            education_level="Bachelor",
            certifications_required=[],
            certifications_preferred=[],
            industry="Finance",
            role_level="Senior",
            keywords=["data pipeline", "etl", "streaming"],
            raw_text="Senior Data Engineer role. Spark, Airflow, SQL, data warehouse.",
        )
        result = classify_role(jd)
        assert result.primary.archetype == "Data Engineer"

    def test_management_jd(self):
        jd = JDCriteria(
            title="Engineering Manager",
            required_skills=["people management", "agile", "delivery"],
            preferred_skills=["python", "aws"],
            min_experience_years=8,
            max_experience_years=15,
            education_level="Bachelor",
            certifications_required=[],
            certifications_preferred=[],
            industry="Technology",
            role_level="Lead",
            keywords=["team lead", "hiring", "roadmap", "stakeholder management"],
            raw_text="Engineering Manager to lead a team of 10. Agile, delivery, hiring.",
        )
        result = classify_role(jd)
        assert result.primary.archetype == "Engineering Manager"
