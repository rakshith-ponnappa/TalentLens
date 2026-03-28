"""
Configuration loader – reads .env, validates weights, exposes typed settings.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path if _env_path.exists() else None)


@dataclass
class Weights:
    required_skills: int
    preferred_skills: int
    experience: int
    education: int
    certifications: int
    semantic: int

    def validate(self) -> None:
        total = (
            self.required_skills
            + self.preferred_skills
            + self.experience
            + self.education
            + self.certifications
            + self.semantic
        )
        if total != 100:
            raise ValueError(f"Scoring weights must sum to 100, got {total}")


@dataclass
class Config:
    llm_provider: str
    llm_model: str
    openai_api_key: str
    anthropic_api_key: str
    opencorporates_api_key: str
    credly_client_id: str
    hunter_api_key: str
    weights: Weights


def load_config() -> Config:
    weights = Weights(
        required_skills=int(os.getenv("WEIGHT_REQUIRED_SKILLS", 35)),
        preferred_skills=int(os.getenv("WEIGHT_PREFERRED_SKILLS", 15)),
        experience=int(os.getenv("WEIGHT_EXPERIENCE", 25)),
        education=int(os.getenv("WEIGHT_EDUCATION", 10)),
        certifications=int(os.getenv("WEIGHT_CERTIFICATIONS", 10)),
        semantic=int(os.getenv("WEIGHT_SEMANTIC", 5)),
    )
    weights.validate()

    return Config(
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        opencorporates_api_key=os.getenv("OPENCORPORATES_API_KEY", ""),
        credly_client_id=os.getenv("CREDLY_CLIENT_ID", ""),
        hunter_api_key=os.getenv("HUNTER_API_KEY", ""),
        weights=weights,
    )
