"""
archetypes.py  –  Role Archetype Classification.

Classifies JDs into role archetypes to enable targeted scoring,
tailored interview questions, and better matching heuristics.

Archetypes:
  1. Cloud/DevOps Engineer    – IaC, CI/CD, containers, cloud platforms
  2. Platform Engineer        – Internal platforms, developer experience, SRE
  3. SRE/Reliability Engineer – Observability, incident response, SLOs
  4. Cloud Architect          – Design, multi-cloud, enterprise architecture
  5. Security Engineer        – AppSec, compliance, IAM, zero trust
  6. Data Engineer            – Pipelines, warehouses, streaming, ETL
  7. Backend Engineer         – APIs, microservices, databases, system design
  8. Full-Stack Engineer      – Frontend + backend, web frameworks
  9. AI/ML Engineer           – Models, LLMs, MLOps, data science
  10. Engineering Manager     – Leadership, delivery, people management
  11. Solutions Architect     – Pre-sales, customer-facing, integration
  12. QA/Test Engineer        – Automation, testing frameworks, quality

Each JD can match 1-2 archetypes (primary + secondary).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from models import JDCriteria


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ArchetypeMatch:
    archetype: str
    confidence: float         # 0.0–1.0
    matched_signals: list[str]  # Which keywords/patterns matched
    description: str
    interview_focus: list[str]  # What to probe for this archetype
    key_skills: list[str]       # Must-have skills for this archetype


@dataclass
class ArchetypeResult:
    primary: ArchetypeMatch
    secondary: ArchetypeMatch | None
    role_complexity: str       # "individual_contributor" / "leadership" / "hybrid"
    suggested_panel: list[str] # Who should interview (e.g., "Cloud Architect, SRE Lead")


# ---------------------------------------------------------------------------
# Archetype definitions
# ---------------------------------------------------------------------------

_ARCHETYPES: dict[str, dict] = {
    "Cloud/DevOps Engineer": {
        "signals": [
            "terraform", "ansible", "pulumi", "cloudformation", "bicep",
            "ci/cd", "cicd", "jenkins", "github actions", "gitlab",
            "docker", "kubernetes", "k8s", "helm", "argocd",
            "aws", "azure", "gcp", "cloud", "devops",
            "infrastructure as code", "iac", "pipeline",
            "container", "deployment", "automation",
        ],
        "description": "Builds and maintains cloud infrastructure, CI/CD pipelines, and deployment automation",
        "interview_focus": [
            "IaC design patterns and module structure",
            "CI/CD pipeline design for complex deployments",
            "Container orchestration and scaling strategies",
            "Cloud cost optimization experience",
            "Incident response and rollback procedures",
        ],
        "key_skills": ["terraform", "kubernetes", "ci/cd", "docker", "aws/azure/gcp"],
    },
    "Platform Engineer": {
        "signals": [
            "platform", "developer experience", "internal tooling",
            "golden path", "self-service", "backstage", "port",
            "idp", "internal developer", "platform team",
            "developer productivity", "service catalog",
            "paved road", "guardrails",
        ],
        "description": "Builds internal platforms and self-service tooling for developer productivity",
        "interview_focus": [
            "Internal platform design philosophy",
            "Developer experience measurements",
            "Self-service infrastructure patterns",
            "Platform adoption and change management",
            "Balancing standardization vs flexibility",
        ],
        "key_skills": ["kubernetes", "terraform", "backstage/port", "API design", "internal tooling"],
    },
    "SRE/Reliability Engineer": {
        "signals": [
            "sre", "site reliability", "reliability",
            "observability", "monitoring", "alerting",
            "prometheus", "grafana", "datadog", "new relic",
            "slo", "sli", "sla", "error budget",
            "incident", "on-call", "pagerduty", "opsgenie",
            "chaos engineering", "toil reduction", "postmortem",
        ],
        "description": "Ensures system reliability, manages incidents, and drives observability practices",
        "interview_focus": [
            "SLO/SLI definition and error budget management",
            "Incident response and postmortem culture",
            "Observability strategy (metrics, logs, traces)",
            "Capacity planning and scaling",
            "Toil identification and reduction",
        ],
        "key_skills": ["observability", "incident management", "SLO/SLI", "kubernetes", "automation"],
    },
    "Cloud Architect": {
        "signals": [
            "architect", "architecture", "solution design",
            "well-architected", "landing zone", "multi-cloud",
            "enterprise", "governance", "reference architecture",
            "high availability", "disaster recovery",
            "cloud strategy", "migration strategy",
            "hub-spoke", "network design",
        ],
        "description": "Designs cloud architectures, defines standards, and guides enterprise cloud strategy",
        "interview_focus": [
            "Architecture decision-making process",
            "Multi-cloud or complex hybrid designs",
            "Well-Architected Framework experience",
            "Stakeholder management and technical leadership",
            "Cost-performance trade-off analysis",
        ],
        "key_skills": ["cloud architecture", "well-architected", "enterprise design", "governance", "networking"],
    },
    "Security Engineer": {
        "signals": [
            "security", "devsecops", "appsec", "infosec",
            "iam", "zero trust", "siem", "soar",
            "penetration", "vulnerability", "compliance",
            "nist", "soc 2", "pci", "hipaa", "gdpr",
            "encryption", "kms", "waf", "firewall",
            "threat modeling", "secure coding",
        ],
        "description": "Implements security controls, compliance frameworks, and threat detection",
        "interview_focus": [
            "Security architecture and threat modeling",
            "Compliance framework implementation",
            "Incident response and forensics",
            "Secure SDLC integration",
            "Identity and access management design",
        ],
        "key_skills": ["iam", "compliance", "threat detection", "devsecops", "encryption"],
    },
    "Data Engineer": {
        "signals": [
            "data pipeline", "etl", "elt", "data warehouse",
            "spark", "airflow", "databricks", "snowflake",
            "kafka", "kinesis", "streaming", "batch processing",
            "data lake", "dbt", "data quality", "data catalog",
            "bigquery", "redshift", "data modeling",
        ],
        "description": "Builds data pipelines, warehouses, and data quality infrastructure",
        "interview_focus": [
            "Data pipeline design and failure handling",
            "Data modeling and warehouse architecture",
            "Real-time vs batch processing trade-offs",
            "Data quality and governance",
            "Scale and performance optimization",
        ],
        "key_skills": ["spark/databricks", "airflow", "sql", "data modeling", "kafka/streaming"],
    },
    "Backend Engineer": {
        "signals": [
            "backend", "api", "rest", "graphql", "grpc",
            "microservices", "distributed systems",
            "python", "java", "go", "golang", "rust", "node.js",
            "postgresql", "mysql", "mongodb", "redis",
            "message queue", "rabbitmq", "event-driven",
            "system design", "scalability",
        ],
        "description": "Builds APIs, microservices, and scalable backend systems",
        "interview_focus": [
            "System design and scalability patterns",
            "API design principles (REST, gRPC, GraphQL)",
            "Database design and query optimization",
            "Distributed systems challenges",
            "Performance profiling and optimization",
        ],
        "key_skills": ["api design", "microservices", "databases", "system design", "programming language"],
    },
    "Full-Stack Engineer": {
        "signals": [
            "full stack", "fullstack", "full-stack",
            "react", "angular", "vue", "svelte",
            "frontend", "front-end", "ui/ux",
            "html", "css", "javascript", "typescript",
            "next.js", "nuxt", "remix",
        ],
        "description": "Builds end-to-end features across frontend and backend",
        "interview_focus": [
            "Frontend framework architecture decisions",
            "State management patterns",
            "API integration and data fetching",
            "Performance (Core Web Vitals, SSR/SSG)",
            "Responsive design and accessibility",
        ],
        "key_skills": ["react/angular/vue", "typescript", "api integration", "css", "state management"],
    },
    "AI/ML Engineer": {
        "signals": [
            "machine learning", "ml", "deep learning",
            "llm", "large language model", "gpt", "bert",
            "pytorch", "tensorflow", "hugging face",
            "mlops", "model", "training", "inference",
            "nlp", "computer vision", "ai", "artificial intelligence",
            "rag", "fine-tuning", "embeddings", "vector",
            "langchain", "prompt engineering",
        ],
        "description": "Builds ML/AI systems, trains models, and implements MLOps pipelines",
        "interview_focus": [
            "Model selection and evaluation methodology",
            "MLOps pipeline design (training, serving, monitoring)",
            "LLM integration patterns and prompt engineering",
            "Data preparation and feature engineering",
            "Model performance optimization",
        ],
        "key_skills": ["ml frameworks", "model training", "mlops", "python", "data processing"],
    },
    "Engineering Manager": {
        "signals": [
            "manager", "management", "lead", "leadership",
            "team lead", "engineering manager", "people",
            "hiring", "retention", "performance review",
            "agile", "scrum", "delivery", "stakeholder",
            "roadmap", "strategy", "mentoring", "coaching",
            "1:1", "okr", "kpi",
        ],
        "description": "Leads engineering teams, manages delivery, and develops people",
        "interview_focus": [
            "Leadership philosophy and management style",
            "Team building and hiring strategy",
            "Conflict resolution and difficult conversations",
            "Technical decision-making vs delegation",
            "Delivery management and stakeholder communication",
        ],
        "key_skills": ["people management", "delivery", "stakeholder management", "agile", "mentoring"],
    },
    "Solutions Architect": {
        "signals": [
            "solutions architect", "pre-sales", "customer-facing",
            "integration", "proof of concept", "poc",
            "client", "demo", "technical sales",
            "discovery", "requirements gathering",
            "rfp", "rfi", "vendor",
        ],
        "description": "Bridges technical solutions with customer needs, often pre-sales or advisory",
        "interview_focus": [
            "Customer discovery and requirements translation",
            "Solution design under constraints",
            "Presentation and demo skills",
            "Cross-team collaboration",
            "Handling objections and technical pushback",
        ],
        "key_skills": ["solution design", "customer engagement", "presentation", "architecture", "integration"],
    },
    "QA/Test Engineer": {
        "signals": [
            "qa", "quality assurance", "testing",
            "test automation", "selenium", "cypress",
            "playwright", "jest", "pytest",
            "load testing", "performance testing",
            "test plan", "test strategy",
            "regression", "integration testing",
            "bdd", "tdd", "cucumber",
        ],
        "description": "Designs test strategies, builds automation frameworks, and ensures quality",
        "interview_focus": [
            "Test strategy design for complex systems",
            "Automation framework architecture",
            "Performance/load testing approach",
            "CI/CD integration of tests",
            "Risk-based testing prioritization",
        ],
        "key_skills": ["test automation", "testing frameworks", "ci/cd integration", "performance testing", "test design"],
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_role(jd: JDCriteria) -> ArchetypeResult:
    """Classify a JD into primary and secondary archetypes."""
    text = (jd.raw_text + " " + jd.title + " " + " ".join(jd.required_skills)).lower()

    scores: list[tuple[str, float, list[str]]] = []

    for name, config in _ARCHETYPES.items():
        matched = []
        for signal in config["signals"]:
            if signal in text:
                matched.append(signal)

        if matched:
            # Confidence = matched signals / total signals, boosted by title match
            base = len(matched) / len(config["signals"])
            title_boost = 0.2 if any(s in jd.title.lower() for s in config["signals"][:5]) else 0.0
            confidence = min(1.0, base + title_boost)
            scores.append((name, confidence, matched))

    scores.sort(key=lambda x: x[1], reverse=True)

    if not scores:
        # Fallback
        primary = ArchetypeMatch(
            archetype="General Engineer",
            confidence=0.3,
            matched_signals=[],
            description="Could not determine a specific archetype from the JD",
            interview_focus=["Technical fundamentals", "Problem-solving approach", "Communication"],
            key_skills=jd.required_skills[:5],
        )
        return ArchetypeResult(primary=primary, secondary=None,
                               role_complexity="individual_contributor", suggested_panel=["Hiring Manager"])

    primary_name, primary_conf, primary_signals = scores[0]
    primary_cfg = _ARCHETYPES[primary_name]
    primary = ArchetypeMatch(
        archetype=primary_name,
        confidence=round(primary_conf, 2),
        matched_signals=primary_signals,
        description=primary_cfg["description"],
        interview_focus=primary_cfg["interview_focus"],
        key_skills=primary_cfg["key_skills"],
    )

    secondary = None
    if len(scores) > 1 and scores[1][1] > 0.15:
        sec_name, sec_conf, sec_signals = scores[1]
        sec_cfg = _ARCHETYPES[sec_name]
        secondary = ArchetypeMatch(
            archetype=sec_name,
            confidence=round(sec_conf, 2),
            matched_signals=sec_signals,
            description=sec_cfg["description"],
            interview_focus=sec_cfg["interview_focus"],
            key_skills=sec_cfg["key_skills"],
        )

    # Determine complexity
    is_leadership = primary_name == "Engineering Manager" or "lead" in jd.title.lower()
    is_ic = not is_leadership
    role_complexity = "leadership" if is_leadership else "individual_contributor"
    if is_leadership and secondary and secondary.archetype != "Engineering Manager":
        role_complexity = "hybrid"

    # Suggested interview panel
    panel = _suggest_panel(primary, secondary, role_complexity)

    return ArchetypeResult(
        primary=primary,
        secondary=secondary,
        role_complexity=role_complexity,
        suggested_panel=panel,
    )


def _suggest_panel(
    primary: ArchetypeMatch,
    secondary: ArchetypeMatch | None,
    complexity: str,
) -> list[str]:
    """Suggest who should be on the interview panel."""
    panel = ["Hiring Manager"]

    # Add domain expert
    archetype_to_panel = {
        "Cloud/DevOps Engineer": "Senior DevOps/Cloud Engineer",
        "Platform Engineer": "Platform Team Lead",
        "SRE/Reliability Engineer": "SRE Lead",
        "Cloud Architect": "Principal Cloud Architect",
        "Security Engineer": "Security Lead/CISO",
        "Data Engineer": "Data Engineering Lead",
        "Backend Engineer": "Senior Backend Engineer",
        "Full-Stack Engineer": "Senior Full-Stack Developer",
        "AI/ML Engineer": "ML/AI Lead",
        "Engineering Manager": "VP of Engineering / Director",
        "Solutions Architect": "Solutions Architecture Lead",
        "QA/Test Engineer": "QA Lead",
    }

    panel.append(archetype_to_panel.get(primary.archetype, "Technical Lead"))

    if secondary:
        sec_panel = archetype_to_panel.get(secondary.archetype, "")
        if sec_panel and sec_panel not in panel:
            panel.append(sec_panel)

    if complexity in ("leadership", "hybrid"):
        if "HR Business Partner" not in panel:
            panel.append("HR Business Partner")

    return panel
