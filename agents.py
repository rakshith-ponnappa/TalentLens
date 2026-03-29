"""
agents.py  –  Multi-Agent Candidate Evaluation System.

Eleven specialised agent personas evaluate each candidate from their unique
perspective, then collaborate to produce a consensus assessment.

Agent Personas:
  Software & Architecture:
    1. Application Architect      –  technical depth, system design, scalability
    2. Product Owner              –  delivery, domain fit, stakeholder skills
    3. Security Architect         –  security posture, compliance, risk awareness
    4. QA Architect               –  quality practices, testing, reliability
    5. SRE Engineer               –  ops expertise, observability, incident handling
  Cloud & AWS:
    6. Cloud Solutions Architect   –  AWS architecture, services breadth, design patterns
    7. AWS Migration Engineer      –  migration strategy, 6Rs, AWS migration tools
    8. Cloud Operations Engineer   –  day-2 ops, cost optimization, monitoring
    9. AWS Platform Engineer       –  IaC, CI/CD, container orchestration, security
  People & Hiring:
   10. HR Manager                 –  culture fit, career progression, retention risk
   11. Recruiting Engineer        –  role alignment, market fit, talent assessment

Each agent produces a structured evaluation (score + rationale).  A moderator
synthesises all perspectives into a final consensus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from models import CandidateProfile, CandidateScore, JDCriteria, VerificationResults


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AgentEvaluation:
    agent_name: str
    persona: str
    score: float                    # 0-100
    grade: str
    strengths: list[str]
    concerns: list[str]
    recommendation: str             # "Strong Hire" / "Hire" / "Lean Hire" / "No Hire"
    rationale: str
    key_questions: list[str]        # interview questions from this agent's POV
    skill_gaps: list[str]
    weight: float                   # how much this agent's score weighs in consensus


@dataclass
class AgentDiscussion:
    round_number: int
    agent_name: str
    message: str


@dataclass
class ConsensusResult:
    consensus_score: float
    consensus_grade: str
    consensus_recommendation: str
    confidence: float               # 0-1 agent agreement level
    evaluations: list[AgentEvaluation]
    discussion: list[AgentDiscussion]
    summary: str
    risk_flags: list[str]
    interview_focus_areas: list[str]


# ---------------------------------------------------------------------------
# Skill categorisation for agent perspectives
# ---------------------------------------------------------------------------

_SECURITY_SKILLS = {
    "devsecops", "hashicorp vault", "zero trust", "siem", "owasp",
    "nist", "pci dss", "soc 2", "aws iam", "iam", "azure ad",
    "microsoft sentinel", "azure firewall", "scp", "landing zone",
    "aws control tower", "encryption", "ssl", "tls", "kms",
    "secrets manager", "security", "compliance", "penetration testing",
    "vulnerability", "waf", "firewall", "rbac", "mfa", "oauth",
}

_QA_SKILLS = {
    "testing", "qa", "quality assurance", "selenium", "jest",
    "pytest", "unittest", "cypress", "postman", "test automation",
    "load testing", "performance testing", "jmeter", "gatling",
    "sonarqube", "code review", "bdd", "tdd", "regression testing",
    "integration testing", "chaos engineering", "reliability",
    "grafana", "datadog", "prometheus", "new relic",
}

_SRE_SKILLS = {
    "sre", "site reliability", "kubernetes", "k8s", "docker",
    "helm", "prometheus", "grafana", "datadog", "opentelemetry",
    "pagerduty", "incident", "on-call", "sla", "slo", "sli",
    "observability", "monitoring", "alerting", "chaos engineering",
    "linux", "bash", "python", "golang", "terraform", "ansible",
    "ci/cd", "jenkins", "argocd", "fluxcd", "istio", "service mesh",
    "load balancing", "nginx", "dns", "networking", "cloudwatch",
    "log analytics", "splunk", "eks", "aks", "gke", "openshift",
    "podman", "rancher", "automation",
}

_ARCHITECTURE_SKILLS = {
    "microservices", "system design", "architecture", "cloud native",
    "aws", "azure", "gcp", "kubernetes", "terraform", "infrastructure as code",
    "rest api", "graphql", "event-driven", "serverless", "lambda",
    "api gateway", "message queue", "kafka", "rabbitmq", "redis",
    "elasticsearch", "postgresql", "mongodb", "dynamodb", "cosmos db",
    "aurora", "cloudformation", "bicep", "arm templates", "pulumi",
    "design patterns", "scalability", "high availability", "disaster recovery",
    "multi-cloud", "hybrid cloud", "well-architected framework",
    "cloud adoption framework", "platform engineering",
}

_PRODUCT_SKILLS = {
    "agile", "scrum", "kanban", "jira", "confluence", "stakeholder",
    "product management", "roadmap", "sprint", "backlog", "user story",
    "acceptance criteria", "business analysis", "requirements",
    "domain knowledge", "communication", "leadership", "mentoring",
    "cross-functional", "documentation", "presentation", "itil",
    "servicenow", "budget", "vendor management", "project management",
}

_HR_SKILLS = {
    "communication", "leadership", "mentoring", "coaching", "team management",
    "conflict resolution", "performance management", "talent development",
    "succession planning", "employee engagement", "retention", "onboarding",
    "diversity", "inclusion", "cultural fit", "collaboration",
    "career development", "professional growth", "references",
    "stakeholder management", "cross-functional", "emotional intelligence",
    "organizational development", "change management", "workforce planning",
    "compensation", "benefits", "hr policy", "labour law",
}

_RECRUITING_SKILLS = {
    "sourcing", "talent acquisition", "ats", "applicant tracking",
    "boolean search", "recruiter", "headhunting", "employer branding",
    "candidate experience", "job posting", "job board", "interview",
    "screening", "assessment", "offer negotiation", "market mapping",
    "pipeline", "passive candidates", "networking", "referrals",
    "linkedin recruiter", "indeed", "glassdoor", "salary benchmarking",
    "competency framework", "job architecture", "role alignment",
    "hiring manager", "talent pipeline", "demand planning",
}

_AWS_CLOUD_SKILLS = {
    "aws", "ec2", "s3", "rds", "lambda", "cloudformation", "eks", "ecs",
    "vpc", "iam", "cloudwatch", "route 53", "direct connect", "transit gateway",
    "aws organizations", "aws control tower", "landing zone", "scp",
    "well-architected framework", "cloud adoption framework", "multi-account",
    "cost explorer", "trusted advisor", "aws config", "guardduty", "security hub",
    "cloud native", "serverless", "api gateway", "step functions",
    "dynamodb", "aurora", "elasticache", "cloudfront", "waf",
    "sns", "sqs", "kinesis", "eventbridge", "secrets manager",
    "kms", "certificate manager", "systems manager", "aws ssm",
}

_AWS_MIGRATION_SKILLS = {
    "aws migration hub", "aws dms", "aws mgn", "aws sct", "aws map",
    "application discovery service", "6rs", "lift and shift", "re-platform",
    "re-architecture", "tco analysis", "cloud adoption framework",
    "database migration", "server migration", "vmware", "on-premises",
    "hybrid cloud", "direct connect", "transit gateway", "migration",
    "cutover", "testing", "rollback", "data sync", "cloudendure",
    "aws snowball", "aws datasync", "rehost", "refactor",
    "migration readiness", "wave planning", "dependency mapping",
}

_CLOUD_OPS_SKILLS = {
    "cloudwatch", "cloudtrail", "aws config", "systems manager", "ssm",
    "patch manager", "automation", "cost optimization", "budgets",
    "trusted advisor", "compute optimizer", "incident management",
    "change management", "itil", "runbook", "on-call", "monitoring",
    "alerting", "log analytics", "cloudwatch logs", "eventbridge",
    "auto scaling", "elasticity", "backup", "disaster recovery",
    "business continuity", "rto", "rpo", "high availability",
    "service catalog", "tagging", "compliance", "governance",
}

_AWS_PLATFORM_SKILLS = {
    "aws", "terraform", "cloudformation", "cdk", "landing zone",
    "control tower", "organizations", "sso", "identity center",
    "config rules", "service catalog", "account factory",
    "networking", "vpc", "transit gateway", "route 53", "direct connect",
    "security hub", "guardduty", "inspector", "macie",
    "kms", "secrets manager", "certificate manager",
    "eks", "ecs", "ecr", "fargate", "lambda",
    "ci/cd", "codepipeline", "codebuild", "codecommit",
    "infrastructure as code", "iac", "well-architected framework",
}


# ---------------------------------------------------------------------------
# Individual Agent Evaluators
# ---------------------------------------------------------------------------

class _BaseAgent:
    name: str = ""
    persona: str = ""
    focus_skills: set[str] = set()
    weight: float = 0.2   # default equal weight

    def evaluate(
        self,
        candidate: CandidateProfile,
        jd: JDCriteria,
        score: CandidateScore,
        verification: Optional[VerificationResults] = None,
    ) -> AgentEvaluation:
        strengths = []
        concerns = []
        skill_gaps = []
        questions = []

        cand_skills_lower = {s.lower() for s in candidate.skills}
        resume_lower = candidate.raw_text.lower()

        # --- Skills coverage from this agent's perspective ---
        focus_found = []
        focus_missing = []
        for sk in self.focus_skills:
            if sk in cand_skills_lower or sk in resume_lower:
                focus_found.append(sk)
            else:
                focus_missing.append(sk)

        # JD-required skills in this agent's domain
        jd_req_lower = {s.lower() for s in jd.required_skills}
        domain_required = jd_req_lower & self.focus_skills
        domain_matched = domain_required & (cand_skills_lower | {t for t in self.focus_skills if t in resume_lower})
        domain_missing = domain_required - domain_matched

        focus_ratio = len(focus_found) / max(len(self.focus_skills), 1)
        domain_ratio = len(domain_matched) / max(len(domain_required), 1) if domain_required else 1.0

        # Base score from overall + domain weighting
        agent_score = score.overall_score * 0.4 + focus_ratio * 100 * 0.3 + domain_ratio * 100 * 0.3
        agent_score = min(agent_score, 100.0)

        # --- Build strengths / concerns ---
        strengths, concerns, skill_gaps, questions = self._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, agent_score,
        )

        # Adjust score based on concerns
        if len(concerns) > 3:
            agent_score *= 0.9
        if verification and verification.overall_trust_score < 0.4:
            agent_score *= 0.85
            concerns.append("Low trust score from verification")

        agent_score = round(max(0, min(100, agent_score)), 1)

        return AgentEvaluation(
            agent_name=self.name,
            persona=self.persona,
            score=agent_score,
            grade=_grade(agent_score),
            strengths=strengths[:5],
            concerns=concerns[:5],
            recommendation=_recommendation(agent_score),
            rationale=self._build_rationale(agent_score, strengths, concerns),
            key_questions=questions[:3],
            skill_gaps=skill_gaps[:5],
            weight=self.weight,
        )

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        """Override in subclass for persona-specific logic."""
        strengths = []
        concerns = []
        skill_gaps = list(domain_missing)
        questions = []

        if focus_found:
            strengths.append(f"Has {len(focus_found)} relevant {self.persona.lower()} skills: {', '.join(sorted(focus_found)[:5])}")
        if domain_missing:
            concerns.append(f"Missing {len(domain_missing)} required domain skill(s): {', '.join(sorted(domain_missing)[:3])}")
            for sk in sorted(domain_missing)[:2]:
                questions.append(f"How would you approach {sk} in this role?")
        if focus_missing and len(focus_missing) > len(focus_found):
            concerns.append(f"Limited depth in {self.persona.lower()} domain ({len(focus_found)}/{len(focus_found)+len(focus_missing)} skills)")

        return strengths, concerns, skill_gaps, questions

    def _build_rationale(self, score, strengths, concerns):
        parts = [f"From a {self.persona} perspective, this candidate scores {score:.1f}/100."]
        if strengths:
            parts.append(f"Key strengths: {strengths[0]}.")
        if concerns:
            parts.append(f"Primary concern: {concerns[0]}.")
        return " ".join(parts)


class ApplicationArchitectAgent(_BaseAgent):
    name = "Application Architect"
    persona = "Architecture"
    focus_skills = _ARCHITECTURE_SKILLS
    weight = 0.08

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        # Architecture depth checks
        cloud_count = sum(1 for c in ["aws", "azure", "gcp"] if c in resume_lower)
        if cloud_count >= 2:
            strengths.append(f"Multi-cloud experience ({cloud_count} platforms)")
        elif cloud_count == 1:
            strengths.append("Single cloud platform experience")
        else:
            concerns.append("No cloud platform experience detected")

        if any(k in resume_lower for k in ["system design", "architecture", "architect", "design pattern"]):
            strengths.append("Demonstrates system design / architecture experience")
        else:
            questions.append("Describe a complex system you designed end-to-end. What trade-offs did you make?")

        iac_tools = [t for t in ["terraform", "cloudformation", "bicep", "pulumi", "ansible"] if t in resume_lower]
        if iac_tools:
            strengths.append(f"IaC proficiency: {', '.join(iac_tools)}")
        else:
            concerns.append("No Infrastructure-as-Code tools mentioned")
            skill_gaps.append("infrastructure as code")

        if any(k in resume_lower for k in ["scalab", "high availability", "disaster recovery", "fault toleran"]):
            strengths.append("Awareness of scalability / HA / DR patterns")

        if candidate.total_experience_years < jd.min_experience_years * 0.7:
            concerns.append(f"Experience ({candidate.total_experience_years:.1f} yrs) below threshold for architecture role")

        questions.append("How would you design the system architecture for this role's primary use case?")

        return strengths, concerns, skill_gaps, questions


class ProductOwnerAgent(_BaseAgent):
    name = "Product Owner"
    persona = "Product & Delivery"
    focus_skills = _PRODUCT_SKILLS
    weight = 0.06

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        # Delivery signals
        if any(k in resume_lower for k in ["agile", "scrum", "sprint", "kanban"]):
            strengths.append("Agile/Scrum methodology experience")
        else:
            concerns.append("No agile methodology experience mentioned")
            questions.append("Describe your experience working in agile teams.")

        if any(k in resume_lower for k in ["lead", "mentor", "coach", "managed team", "team lead"]):
            strengths.append("Leadership / mentoring experience")

        if any(k in resume_lower for k in ["stakeholder", "business", "client", "cross-functional"]):
            strengths.append("Stakeholder engagement experience")
        else:
            questions.append("How do you handle competing priorities from different stakeholders?")

        if any(k in resume_lower for k in ["documentation", "confluence", "technical writing"]):
            strengths.append("Documentation / knowledge sharing practice")

        # Domain fit
        if jd.industry and jd.industry.lower() != "unspecified":
            if jd.industry.lower() in resume_lower:
                strengths.append(f"Industry domain experience: {jd.industry}")
            else:
                concerns.append(f"No direct {jd.industry} industry experience")
                questions.append(f"What experience do you have in the {jd.industry} domain?")

        return strengths, concerns, skill_gaps, questions


class SecurityArchitectAgent(_BaseAgent):
    name = "Security Architect"
    persona = "Security"
    focus_skills = _SECURITY_SKILLS
    weight = 0.10

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        # Security depth
        sec_terms = ["security", "compliance", "encryption", "authentication",
                     "authoriz", "vulnerab", "penetration", "firewall",
                     "zero trust", "rbac", "iam", "devsecops", "siem"]
        sec_count = sum(1 for t in sec_terms if t in resume_lower)

        if sec_count >= 5:
            strengths.append(f"Strong security awareness ({sec_count} security concepts found)")
        elif sec_count >= 2:
            strengths.append(f"Moderate security awareness ({sec_count} concepts)")
        else:
            concerns.append("Limited security awareness in resume")
            skill_gaps.append("security practices")
            questions.append("How do you integrate security into your development/deployment workflow?")

        compliance_terms = ["pci", "nist", "soc", "gdpr", "hipaa", "iso 27001", "compliance"]
        if any(t in resume_lower for t in compliance_terms):
            strengths.append("Compliance framework experience")
        else:
            concerns.append("No compliance framework experience mentioned")
            questions.append("What compliance frameworks have you worked with?")

        if any(t in resume_lower for t in ["vault", "secrets manager", "kms", "key management"]):
            strengths.append("Secrets/key management experience")

        if any(t in resume_lower for t in ["devsecops", "sast", "dast", "snyk", "trivy", "aqua"]):
            strengths.append("DevSecOps tooling experience")

        # Verification trust check
        if verification and verification.overall_trust_score < 0.5:
            concerns.append(f"Verification trust score is low ({verification.overall_trust_score:.0%}) — potential integrity risk")

        return strengths, concerns, skill_gaps, questions


class QAArchitectAgent(_BaseAgent):
    name = "QA Architect"
    persona = "Quality Assurance"
    focus_skills = _QA_SKILLS
    weight = 0.06

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        qa_terms = ["test", "testing", "qa", "quality", "automation",
                     "selenium", "cypress", "jest", "pytest", "unittest",
                     "bdd", "tdd", "regression", "integration test",
                     "load test", "performance test"]
        qa_count = sum(1 for t in qa_terms if t in resume_lower)

        if qa_count >= 5:
            strengths.append(f"Strong quality/testing culture ({qa_count} QA concepts)")
        elif qa_count >= 2:
            strengths.append(f"Some testing awareness ({qa_count} concepts)")
        else:
            concerns.append("Limited testing/QA awareness in resume")
            questions.append("How do you ensure code quality and reliability in your projects?")

        if any(t in resume_lower for t in ["ci/cd", "cicd", "pipeline", "continuous"]):
            strengths.append("CI/CD pipeline experience (quality gates potential)")
        else:
            concerns.append("No CI/CD experience — quality automation gaps likely")
            skill_gaps.append("CI/CD pipeline")

        if any(t in resume_lower for t in ["sonarqube", "code review", "static analysis", "lint"]):
            strengths.append("Code quality tooling experience")

        if any(t in resume_lower for t in ["monitoring", "observability", "alerting", "logging"]):
            strengths.append("Observability awareness (production quality)")

        if any(t in resume_lower for t in ["chaos", "resilience", "fault injection"]):
            strengths.append("Chaos/resilience engineering experience")
            
        questions.append("Walk me through your approach to testing a new feature end-to-end.")

        return strengths, concerns, skill_gaps, questions


class SREEngineerAgent(_BaseAgent):
    name = "SRE Engineer"
    persona = "Site Reliability"
    focus_skills = _SRE_SKILLS
    weight = 0.08

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        # Ops depth
        ops_terms = ["kubernetes", "k8s", "docker", "container", "helm",
                     "linux", "bash", "shell", "ansible", "terraform",
                     "ci/cd", "jenkins", "argocd", "deployment"]
        ops_count = sum(1 for t in ops_terms if t in resume_lower)

        if ops_count >= 6:
            strengths.append(f"Deep ops/infrastructure skill set ({ops_count} SRE tools)")
        elif ops_count >= 3:
            strengths.append(f"Moderate ops skill set ({ops_count} tools)")
        else:
            concerns.append("Limited operational tooling experience")
            skill_gaps.append("ops/SRE tooling")

        # Observability
        obs_tools = ["prometheus", "grafana", "datadog", "cloudwatch",
                      "new relic", "splunk", "opentelemetry", "dynatrace"]
        obs_found = [t for t in obs_tools if t in resume_lower]
        if obs_found:
            strengths.append(f"Observability stack: {', '.join(obs_found)}")
        else:
            concerns.append("No observability/monitoring tools mentioned")
            skill_gaps.append("observability")
            questions.append("How do you approach monitoring and alerting for production systems?")

        # SRE-specific
        if any(t in resume_lower for t in ["sla", "slo", "sli", "error budget"]):
            strengths.append("SLO/SLA awareness (SRE fundamentals)")
        if any(t in resume_lower for t in ["incident", "on-call", "runbook", "post-mortem"]):
            strengths.append("Incident management experience")
        else:
            questions.append("Describe your experience with production incidents and on-call rotations.")

        # Automation
        auto_langs = [l for l in ["python", "golang", "bash", "powershell"] if l in resume_lower]
        if auto_langs:
            strengths.append(f"Automation scripting: {', '.join(auto_langs)}")
        else:
            concerns.append("No scripting/automation language evident")

        questions.append("How would you reduce toil and improve reliability for this platform?")

        return strengths, concerns, skill_gaps, questions


class HRManagerAgent(_BaseAgent):
    name = "HR Manager"
    persona = "People & Culture"
    focus_skills = _HR_SKILLS
    weight = 0.10

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        # Career progression
        exp_count = len(candidate.experience) if candidate.experience else 0
        if exp_count >= 3:
            # Check for upward mobility (title changes)
            titles = [e.title.lower() for e in candidate.experience if e.title]
            senior_titles = [t for t in titles if any(k in t for k in
                            ["senior", "lead", "principal", "manager", "director", "head", "vp", "chief"])]
            if senior_titles:
                strengths.append(f"Career progression evident — {len(senior_titles)} senior-level role(s)")
            elif exp_count >= 4:
                concerns.append("Multiple roles but no clear career progression (no senior titles)")
                questions.append("Walk me through your career trajectory and how each move advanced your goals.")
        elif exp_count == 1 and candidate.total_experience_years > 5:
            concerns.append("Long tenure at single company — may need adaptation support")
        elif exp_count == 0:
            concerns.append("No structured experience entries found")

        # Job-hopping risk
        if exp_count >= 3:
            short_stints = sum(1 for e in candidate.experience
                              if e.duration_months > 0 and e.duration_months < 12)
            if short_stints >= 2:
                concerns.append(f"Retention risk — {short_stints} roles under 12 months")
                questions.append("I notice a few shorter tenures. What drove those transitions?")

        # Soft skills signals
        soft_terms = ["team", "collaborat", "communicat", "mentor", "coach",
                      "stakeholder", "present", "cross-functional", "leadership"]
        soft_count = sum(1 for t in soft_terms if t in resume_lower)
        if soft_count >= 4:
            strengths.append(f"Strong interpersonal / soft-skill signals ({soft_count} indicators)")
        elif soft_count >= 2:
            strengths.append("Some collaborative and communication skills evident")
        else:
            concerns.append("Limited evidence of soft skills / teamwork language")
            questions.append("Describe a situation where you had to influence a team without formal authority.")

        # Education depth
        edu_count = len(candidate.education) if candidate.education else 0
        if edu_count >= 1:
            degrees = [e.degree.lower() for e in candidate.education if e.degree]
            if any("master" in d or "mba" in d or "ms" in d or "m.s" in d for d in degrees):
                strengths.append("Advanced degree (Master's / MBA)")
            elif any("phd" in d or "doctor" in d for d in degrees):
                strengths.append("Doctoral-level education")

        # Verification trust from HR perspective
        if verification:
            if verification.overall_trust_score >= 0.7:
                strengths.append(f"High background verification trust ({verification.overall_trust_score:.0%})")
            elif verification.overall_trust_score < 0.4:
                concerns.append(f"Low verification trust ({verification.overall_trust_score:.0%}) — reference checks recommended")
                questions.append("Can you provide professional references from your last two employers?")

        # Culture fit questions
        questions.append("What kind of work environment brings out your best performance?")

        return strengths, concerns, skill_gaps, questions


class RecruitingEngineerAgent(_BaseAgent):
    name = "Recruiting Engineer"
    persona = "Talent Acquisition"
    focus_skills = _RECRUITING_SKILLS
    weight = 0.08

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        # Role-candidate alignment
        jd_title_words = set(jd.title.lower().split()) - {"the", "a", "an", "and", "or", "of", "for", "in", "at"}
        if candidate.experience:
            recent_title = candidate.experience[0].title.lower()
            title_overlap = sum(1 for w in jd_title_words if w in recent_title)
            if title_overlap >= 2:
                strengths.append(f"Strong title alignment — current role closely matches '{jd.title}'")
            elif title_overlap == 1:
                strengths.append("Partial title alignment with target role")
            else:
                concerns.append("Current title doesn't align with target role — career pivot?")
                questions.append(f"Your current title differs from '{jd.title}'. What motivates this transition?")

        # Experience level fit
        exp_yrs = candidate.total_experience_years
        if jd.min_experience_years > 0:
            if exp_yrs >= jd.min_experience_years * 1.5:
                concerns.append(f"Potentially overqualified ({exp_yrs:.0f} yrs vs {jd.min_experience_years:.0f} min) — flight risk")
            elif exp_yrs >= jd.min_experience_years:
                strengths.append(f"Experience ({exp_yrs:.1f} yrs) matches requirement ({jd.min_experience_years:.0f}+ yrs)")
            elif exp_yrs >= jd.min_experience_years * 0.7:
                strengths.append(f"Nearly meets experience requirement ({exp_yrs:.1f} yrs vs {jd.min_experience_years:.0f} min)")
            else:
                concerns.append(f"Under-experienced: {exp_yrs:.1f} yrs vs {jd.min_experience_years:.0f}+ required")

        # Skills market fit
        req_matched = len(score.matched_required_skills)
        req_total = req_matched + len(score.missing_required_skills)
        match_pct = req_matched / max(req_total, 1) * 100
        if match_pct >= 80:
            strengths.append(f"Excellent skills match ({match_pct:.0f}% of required skills)")
        elif match_pct >= 60:
            strengths.append(f"Good skills match ({match_pct:.0f}% of required skills)")
        elif match_pct >= 40:
            concerns.append(f"Moderate skills gap ({match_pct:.0f}% match) — training investment needed")
        else:
            concerns.append(f"Significant skills gap ({match_pct:.0f}% match) — not market-ready for role")

        # LinkedIn / professional presence for sourcing quality
        has_linkedin = bool(candidate.linkedin_url)
        has_github = bool(candidate.github_url)
        if verification:
            li = verification.linkedin
            if li and li.url_resolves:
                strengths.append("Active LinkedIn profile — good professional visibility")
            elif li and li.url:
                strengths.append("LinkedIn profile found (unverified)")
            elif not has_linkedin:
                concerns.append("No LinkedIn presence — limits reference checking and background validation")

        if has_github:
            strengths.append("GitHub profile available — portfolio evidence")

        # Compensation / market signals (inferred from seniority and location)
        if any(loc in (candidate.location or "").lower()
               for loc in ["san francisco", "new york", "london", "seattle", "bay area"]):
            concerns.append("High-cost location — salary expectations may be above budget")

        # Overall talent assessment
        questions.append("What are your salary expectations and notice period?")
        questions.append("Are you considering other opportunities currently?")

        return strengths, concerns, skill_gaps, questions


class CloudSolutionsArchitectAgent(_BaseAgent):
    name = "Cloud Solutions Architect"
    persona = "Cloud Architecture"
    focus_skills = _AWS_CLOUD_SKILLS
    weight = 0.14

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        # AWS breadth — core services
        core_aws = ["ec2", "s3", "rds", "lambda", "vpc", "iam", "cloudformation",
                     "cloudwatch", "route 53", "eks", "ecs"]
        aws_count = sum(1 for svc in core_aws if svc in resume_lower)
        if aws_count >= 7:
            strengths.append(f"Deep AWS breadth ({aws_count} core services)")
        elif aws_count >= 4:
            strengths.append(f"Good AWS coverage ({aws_count} core services)")
        elif aws_count >= 2:
            concerns.append(f"Limited AWS breadth — only {aws_count} core services mentioned")
        else:
            concerns.append("Minimal or no AWS core service experience")
            skill_gaps.append("AWS core services")

        # Multi-cloud awareness
        other_clouds = sum(1 for c in ["azure", "gcp", "google cloud"] if c in resume_lower)
        if "aws" in resume_lower and other_clouds >= 1:
            strengths.append("Multi-cloud awareness (AWS + additional platforms)")

        # Well-Architected
        if any(t in resume_lower for t in ["well-architected", "well architected", "waf review"]):
            strengths.append("AWS Well-Architected Framework experience")
        else:
            questions.append("How do you apply the AWS Well-Architected Framework in your designs?")

        # Serverless / modern patterns
        serverless_terms = ["lambda", "serverless", "api gateway", "step functions",
                            "dynamodb", "eventbridge", "sqs", "sns"]
        sl_count = sum(1 for t in serverless_terms if t in resume_lower)
        if sl_count >= 4:
            strengths.append("Strong serverless / event-driven architecture experience")
        elif sl_count >= 2:
            strengths.append("Some serverless experience")

        # Networking depth
        net_terms = ["vpc", "subnet", "security group", "nacl", "transit gateway",
                     "direct connect", "vpn", "route 53", "cloudfront"]
        net_count = sum(1 for t in net_terms if t in resume_lower)
        if net_count >= 4:
            strengths.append(f"Strong AWS networking knowledge ({net_count} concepts)")
        elif net_count < 2:
            concerns.append("Limited AWS networking experience")
            skill_gaps.append("AWS networking")

        # Landing zone / multi-account
        if any(t in resume_lower for t in ["landing zone", "control tower", "organizations",
                                            "multi-account", "account factory"]):
            strengths.append("AWS Landing Zone / multi-account strategy experience")
        else:
            questions.append("Describe your experience with AWS multi-account strategy and landing zones.")

        questions.append("Design an AWS architecture for a highly-available, multi-region application.")

        return strengths, concerns, skill_gaps, questions


class AWSMigrationEngineerAgent(_BaseAgent):
    name = "AWS Migration Engineer"
    persona = "Cloud Migration"
    focus_skills = _AWS_MIGRATION_SKILLS
    weight = 0.12

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        # Migration methodology
        migration_terms = ["migration", "migrate", "migrated", "lift and shift",
                           "rehost", "replatform", "refactor", "re-architect",
                           "6r", "7r", "cloud adoption"]
        mig_count = sum(1 for t in migration_terms if t in resume_lower)
        if mig_count >= 3:
            strengths.append(f"Strong migration methodology experience ({mig_count} migration concepts)")
        elif mig_count >= 1:
            strengths.append("Some migration experience mentioned")
        else:
            concerns.append("No migration methodology experience evident")
            skill_gaps.append("cloud migration methodology")
            questions.append("Describe a large-scale cloud migration you've led or participated in.")

        # AWS migration tools
        mig_tools = ["aws dms", "database migration", "aws mgn", "cloudendure",
                      "application discovery", "migration hub", "aws sct",
                      "schema conversion", "datasync", "snowball"]
        tool_count = sum(1 for t in mig_tools if t in resume_lower)
        if tool_count >= 3:
            strengths.append(f"AWS migration tooling expertise ({tool_count} tools)")
        elif tool_count >= 1:
            strengths.append("Familiar with some AWS migration tools")
        else:
            concerns.append("No AWS migration tooling mentioned")
            skill_gaps.append("AWS migration tools (DMS, MGN, SCT)")

        # On-premises / hybrid
        if any(t in resume_lower for t in ["on-premises", "on-prem", "data center",
                                            "datacenter", "vmware", "hyper-v"]):
            strengths.append("On-premises / data center experience (migration source knowledge)")
        else:
            concerns.append("No on-premises infrastructure background evident")

        # Assessment / planning
        if any(t in resume_lower for t in ["assessment", "discovery", "wave plan",
                                            "dependency", "tco", "total cost"]):
            strengths.append("Migration assessment and planning experience")
        else:
            questions.append("How do you approach migration assessment and wave planning?")

        # Database migration specific
        if any(t in resume_lower for t in ["database migration", "dms", "schema conversion",
                                            "oracle to", "sql server to", "rds"]):
            strengths.append("Database migration experience")

        questions.append("Walk me through your approach to migrating a complex legacy application to AWS.")

        return strengths, concerns, skill_gaps, questions


class CloudOperationsEngineerAgent(_BaseAgent):
    name = "Cloud Operations Engineer"
    persona = "Cloud Operations"
    focus_skills = _CLOUD_OPS_SKILLS
    weight = 0.10

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        # Day-2 operations
        ops_terms = ["monitoring", "alerting", "incident", "patching", "backup",
                     "disaster recovery", "runbook", "automation", "remediation",
                     "change management", "itil", "on-call"]
        ops_count = sum(1 for t in ops_terms if t in resume_lower)
        if ops_count >= 5:
            strengths.append(f"Strong day-2 operations experience ({ops_count} ops practices)")
        elif ops_count >= 3:
            strengths.append(f"Moderate operations experience ({ops_count} practices)")
        else:
            concerns.append("Limited operational/day-2 experience")
            skill_gaps.append("cloud operations practices")

        # AWS ops tools
        aws_ops = ["cloudwatch", "cloudtrail", "aws config", "systems manager",
                    "ssm", "eventbridge", "auto scaling", "trusted advisor"]
        aws_ops_count = sum(1 for t in aws_ops if t in resume_lower)
        if aws_ops_count >= 4:
            strengths.append(f"AWS operational tooling mastery ({aws_ops_count} tools)")
        elif aws_ops_count >= 2:
            strengths.append(f"Some AWS operational tooling ({aws_ops_count} tools)")
        else:
            concerns.append("Limited AWS-native operational tooling experience")
            skill_gaps.append("AWS operational tools (CloudWatch, Config, SSM)")

        # Cost optimization
        if any(t in resume_lower for t in ["cost optim", "cost reduc", "cost sav",
                                            "reserved instance", "savings plan",
                                            "right-siz", "rightsiz", "cost explorer",
                                            "finops", "compute optimizer"]):
            strengths.append("Cost optimization / FinOps experience")
        else:
            concerns.append("No cost optimization experience mentioned")
            questions.append("How do you approach AWS cost optimization for enterprise workloads?")

        # DR / HA
        if any(t in resume_lower for t in ["disaster recovery", "business continuity",
                                            "rto", "rpo", "failover", "multi-region",
                                            "high availability"]):
            strengths.append("DR/HA planning experience")
        else:
            questions.append("Describe your approach to disaster recovery planning on AWS.")

        # Governance / compliance
        if any(t in resume_lower for t in ["governance", "tagging", "compliance",
                                            "audit", "config rule", "guardrail"]):
            strengths.append("Cloud governance and compliance awareness")

        questions.append("How would you set up monitoring and alerting for a critical production workload?")

        return strengths, concerns, skill_gaps, questions


class AWSPlatformEngineerAgent(_BaseAgent):
    name = "AWS Platform Engineer"
    persona = "Platform Engineering"
    focus_skills = _AWS_PLATFORM_SKILLS
    weight = 0.08

    def _perspective_analysis(self, candidate, jd, score, verification,
                               focus_found, focus_missing,
                               domain_matched, domain_missing, base_score):
        strengths, concerns, skill_gaps, questions = super()._perspective_analysis(
            candidate, jd, score, verification, focus_found, focus_missing,
            domain_matched, domain_missing, base_score,
        )

        resume_lower = candidate.raw_text.lower()

        # IaC depth
        iac_tools = ["terraform", "cloudformation", "cdk", "pulumi", "bicep"]
        iac_found = [t for t in iac_tools if t in resume_lower]
        if len(iac_found) >= 2:
            strengths.append(f"Multi-IaC proficiency: {', '.join(iac_found)}")
        elif len(iac_found) == 1:
            strengths.append(f"IaC experience: {iac_found[0]}")
        else:
            concerns.append("No Infrastructure-as-Code tools mentioned")
            skill_gaps.append("IaC (Terraform/CloudFormation)")

        # CI/CD pipeline
        cicd_terms = ["ci/cd", "cicd", "pipeline", "codepipeline", "codebuild",
                       "github actions", "jenkins", "gitlab ci", "argocd"]
        cicd_found = [t for t in cicd_terms if t in resume_lower]
        if cicd_found:
            strengths.append(f"CI/CD experience: {', '.join(cicd_found[:3])}")
        else:
            concerns.append("No CI/CD pipeline experience")
            skill_gaps.append("CI/CD pipelines")

        # Container orchestration
        container_terms = ["kubernetes", "k8s", "eks", "ecs", "fargate", "docker",
                            "helm", "ecr", "container"]
        cont_count = sum(1 for t in container_terms if t in resume_lower)
        if cont_count >= 4:
            strengths.append(f"Strong containerization skills ({cont_count} container technologies)")
        elif cont_count >= 2:
            strengths.append(f"Container orchestration experience ({cont_count} technologies)")
        else:
            concerns.append("Limited container/orchestration experience")

        # Security engineering
        sec_tools = ["security hub", "guardduty", "inspector", "macie",
                     "kms", "secrets manager", "waf", "shield"]
        sec_count = sum(1 for t in sec_tools if t in resume_lower)
        if sec_count >= 3:
            strengths.append(f"AWS security services proficiency ({sec_count} tools)")
        elif sec_count >= 1:
            strengths.append("Some AWS security tooling experience")

        # Automation / scripting
        auto_langs = [l for l in ["python", "bash", "powershell", "golang", "typescript"] if l in resume_lower]
        if auto_langs:
            strengths.append(f"Platform automation languages: {', '.join(auto_langs)}")
        else:
            concerns.append("No automation scripting language evident")
            questions.append("What scripting/automation languages do you use for platform engineering?")

        questions.append("How would you design a self-service platform for development teams on AWS?")

        return strengths, concerns, skill_gaps, questions


# ---------------------------------------------------------------------------
# Agent Panel (Moderator)
# ---------------------------------------------------------------------------

_ALL_AGENTS = [
    # Software & Architecture
    ApplicationArchitectAgent(),
    ProductOwnerAgent(),
    SecurityArchitectAgent(),
    QAArchitectAgent(),
    SREEngineerAgent(),
    # Cloud & AWS
    CloudSolutionsArchitectAgent(),
    AWSMigrationEngineerAgent(),
    CloudOperationsEngineerAgent(),
    AWSPlatformEngineerAgent(),
    # People & Hiring
    HRManagerAgent(),
    RecruitingEngineerAgent(),
]

# Public catalogue for UI agent picker
AGENT_CATALOGUE = [
    {"name": a.name, "persona": a.persona, "weight": a.weight,
     "group": "Cloud & AWS" if any(k in a.name for k in ("Cloud", "AWS", "Migration"))
              else "People & Hiring" if a.name in ("HR Manager", "Recruiting Engineer")
              else "Software & Architecture"}
    for a in _ALL_AGENTS
]


def evaluate_candidate(
    candidate: CandidateProfile,
    jd: JDCriteria,
    score: CandidateScore,
    verification: Optional[VerificationResults] = None,
    selected_agents: Optional[list[str]] = None,
) -> ConsensusResult:
    """Run agent evaluations and synthesise a consensus.

    Args:
        selected_agents: Optional list of agent names to run.  If *None* or
            empty, all 11 agents are evaluated.  When a subset is provided
            only those agents participate and weights are renormalised.
    """
    if selected_agents:
        agents_to_run = [a for a in _ALL_AGENTS if a.name in selected_agents]
    else:
        agents_to_run = list(_ALL_AGENTS)

    # Renormalise weights so they still sum to 1.0 when a subset is used
    raw_weight_sum = sum(a.weight for a in agents_to_run)
    weight_scale = 1.0 / max(raw_weight_sum, 0.01)

    evaluations: list[AgentEvaluation] = []
    discussion: list[AgentDiscussion] = []

    # --- Round 1: Independent evaluations ---
    for agent in agents_to_run:
        ev = agent.evaluate(candidate, jd, score, verification)
        evaluations.append(ev)
        discussion.append(AgentDiscussion(
            round_number=1,
            agent_name=ev.agent_name,
            message=f"[Initial Assessment] Score: {ev.score}/100 ({ev.grade}). "
                    f"Recommendation: {ev.recommendation}. {ev.rationale}",
        ))

    # --- Round 2: Cross-perspective discussion ---
    # Each agent reviews others' findings and may adjust
    all_concerns = []
    all_strengths = []
    for ev in evaluations:
        all_concerns.extend(ev.concerns)
        all_strengths.extend(ev.strengths)

    # Security agent flags for all
    sec_ev = next((e for e in evaluations if e.agent_name == "Security Architect"), None)
    if sec_ev and sec_ev.score < 50:
        for ev in evaluations:
            if ev.agent_name != "Security Architect":
                discussion.append(AgentDiscussion(
                    round_number=2,
                    agent_name=ev.agent_name,
                    message=f"[Response to Security] Noted security concerns. "
                            f"Adjusting assessment — security gaps could impact "
                            f"production readiness.",
                ))

    # Architecture agent comments on technical depth
    arch_ev = next((e for e in evaluations if e.agent_name == "Application Architect"), None)
    if arch_ev:
        discussion.append(AgentDiscussion(
            round_number=2,
            agent_name="Application Architect",
            message=f"[Technical Depth Summary] Candidate has "
                    f"{len(arch_ev.strengths)} architectural strengths and "
                    f"{len(arch_ev.skill_gaps)} gaps. "
                    f"{'Strong technical foundation.' if arch_ev.score >= 70 else 'Needs technical growth.'}",
        ))

    # SRE comments on ops readiness
    sre_ev = next((e for e in evaluations if e.agent_name == "SRE Engineer"), None)
    if sre_ev:
        discussion.append(AgentDiscussion(
            round_number=2,
            agent_name="SRE Engineer",
            message=f"[Ops Readiness] {'Production-ready skill set.' if sre_ev.score >= 70 else 'Gaps in operational maturity.'} "
                    f"Score: {sre_ev.score}/100.",
        ))

    # QA comments on quality practices
    qa_ev = next((e for e in evaluations if e.agent_name == "QA Architect"), None)
    if qa_ev:
        discussion.append(AgentDiscussion(
            round_number=2,
            agent_name="QA Architect",
            message=f"[Quality Assessment] {'Good quality practices evident.' if qa_ev.score >= 65 else 'Quality gaps need addressing.'} "
                    f"{'CI/CD present.' if any('ci' in s.lower() for s in qa_ev.strengths) else 'CI/CD absent.'}",
        ))

    # PO comments on delivery fit
    po_ev = next((e for e in evaluations if e.agent_name == "Product Owner"), None)
    if po_ev:
        discussion.append(AgentDiscussion(
            round_number=2,
            agent_name="Product Owner",
            message=f"[Delivery Fit] {'Good delivery mindset.' if po_ev.score >= 65 else 'Delivery experience needs validation.'} "
                    f"{'Domain experience present.' if any('domain' in s.lower() or 'industry' in s.lower() for s in po_ev.strengths) else 'Domain fit unclear.'}",
        ))

    # HR Manager comments on culture and retention
    hr_ev = next((e for e in evaluations if e.agent_name == "HR Manager"), None)
    if hr_ev:
        retention_risk = any("retention" in c.lower() for c in hr_ev.concerns)
        discussion.append(AgentDiscussion(
            round_number=2,
            agent_name="HR Manager",
            message=f"[People Assessment] {'Good culture fit indicators.' if hr_ev.score >= 65 else 'Cultural alignment needs probing.'} "
                    f"{'⚠️ Retention risk flagged.' if retention_risk else 'No immediate retention concerns.'}",
        ))

    # Recruiting Engineer comments on market fit
    rec_ev = next((e for e in evaluations if e.agent_name == "Recruiting Engineer"), None)
    if rec_ev:
        discussion.append(AgentDiscussion(
            round_number=2,
            agent_name="Recruiting Engineer",
            message=f"[Market Fit] {'Candidate is well-aligned for role.' if rec_ev.score >= 70 else 'Some role-candidate alignment gaps.'} "
                    f"{'Competitive profile in market.' if rec_ev.score >= 60 else 'May need to assess competing offers.'}",
        ))

    # Cloud Solutions Architect on AWS expertise
    cloud_ev = next((e for e in evaluations if e.agent_name == "Cloud Solutions Architect"), None)
    if cloud_ev:
        discussion.append(AgentDiscussion(
            round_number=2,
            agent_name="Cloud Solutions Architect",
            message=f"[AWS Architecture] {'Strong AWS architecture foundation.' if cloud_ev.score >= 70 else 'AWS architecture gaps identified.'} "
                    f"Score: {cloud_ev.score}/100. {len(cloud_ev.skill_gaps)} skill gaps.",
        ))

    # AWS Migration Engineer on migration readiness
    mig_ev = next((e for e in evaluations if e.agent_name == "AWS Migration Engineer"), None)
    if mig_ev:
        discussion.append(AgentDiscussion(
            round_number=2,
            agent_name="AWS Migration Engineer",
            message=f"[Migration Assessment] {'Experienced in cloud migrations.' if mig_ev.score >= 65 else 'Migration experience needs validation.'} "
                    f"{'Migration tooling proficiency confirmed.' if mig_ev.score >= 70 else 'Gaps in migration methodology or tooling.'}",
        ))

    # Cloud Operations Engineer on ops maturity
    cops_ev = next((e for e in evaluations if e.agent_name == "Cloud Operations Engineer"), None)
    if cops_ev:
        discussion.append(AgentDiscussion(
            round_number=2,
            agent_name="Cloud Operations Engineer",
            message=f"[Ops Maturity] {'Day-2 operations ready.' if cops_ev.score >= 65 else 'Operational maturity needs development.'} "
                    f"{'Cost optimization aware.' if any('cost' in s.lower() for s in cops_ev.strengths) else 'FinOps gap identified.'}",
        ))

    # AWS Platform Engineer on platform readiness
    plat_ev = next((e for e in evaluations if e.agent_name == "AWS Platform Engineer"), None)
    if plat_ev:
        discussion.append(AgentDiscussion(
            round_number=2,
            agent_name="AWS Platform Engineer",
            message=f"[Platform Engineering] {'Solid IaC and automation skills.' if plat_ev.score >= 70 else 'Platform engineering skills need strengthening.'} "
                    f"{'Container orchestration present.' if any('container' in s.lower() for s in plat_ev.strengths) else 'Container experience limited.'}",
        ))

    # --- Round 3: Consensus ---
    # Weighted average (renormalised for subset)
    total_weight = sum(ev.weight for ev in evaluations) * weight_scale
    consensus_score = sum(ev.score * ev.weight * weight_scale for ev in evaluations) / max(total_weight, 0.01)
    consensus_score = round(consensus_score, 1)

    # Confidence = inverse of score variance (higher agreement = higher confidence)
    avg = consensus_score
    variance = sum((ev.score - avg) ** 2 for ev in evaluations) / max(len(evaluations), 1)
    std_dev = variance ** 0.5
    confidence = max(0.0, min(1.0, 1.0 - (std_dev / 50)))  # normalise: <50 std → good confidence

    # Risk flags
    risk_flags = []
    if sec_ev and sec_ev.score < 50:
        risk_flags.append("🔴 Security posture below threshold")
    if verification and verification.overall_trust_score < 0.4:
        risk_flags.append("🔴 Low verification trust score")
    if sre_ev and sre_ev.score < 40:
        risk_flags.append("🟡 Limited SRE/ops readiness")
    if any("no cloud" in c.lower() for c in all_concerns):
        risk_flags.append("🟡 No cloud platform experience")
    recs = [ev.recommendation for ev in evaluations]
    if recs.count("No Hire") >= 3:
        risk_flags.append("🔴 Majority of agents recommend No Hire")

    # Interview focus areas (aggregate unique questions)
    all_questions = []
    seen = set()
    for ev in evaluations:
        for q in ev.key_questions:
            q_norm = q.lower().strip()
            if q_norm not in seen:
                seen.add(q_norm)
                all_questions.append(q)

    # Consensus discussion message
    discussion.append(AgentDiscussion(
        round_number=3,
        agent_name="Moderator",
        message=f"[Consensus] After reviewing all perspectives: "
                f"Score {consensus_score}/100 ({_grade(consensus_score)}). "
                f"Confidence: {confidence:.0%}. "
                f"Recommendation: {_recommendation(consensus_score)}. "
                f"Risk flags: {len(risk_flags)}. "
                f"Interview focus areas: {len(all_questions)}.",
    ))

    return ConsensusResult(
        consensus_score=consensus_score,
        consensus_grade=_grade(consensus_score),
        consensus_recommendation=_recommendation(consensus_score),
        confidence=round(confidence, 2),
        evaluations=evaluations,
        discussion=discussion,
        summary=_build_summary(candidate, evaluations, consensus_score, risk_flags),
        risk_flags=risk_flags,
        interview_focus_areas=all_questions[:10],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade(score: float) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B+"
    if score >= 60: return "B"
    if score >= 50: return "C"
    if score >= 40: return "D"
    return "F"


def _recommendation(score: float) -> str:
    if score >= 80: return "Strong Hire"
    if score >= 65: return "Hire"
    if score >= 50: return "Lean Hire"
    return "No Hire"


def _build_summary(
    candidate: CandidateProfile,
    evaluations: list[AgentEvaluation],
    consensus_score: float,
    risk_flags: list[str],
) -> str:
    hire_count = sum(1 for e in evaluations if "Hire" in e.recommendation and "No" not in e.recommendation)
    no_hire_count = sum(1 for e in evaluations if e.recommendation == "No Hire")
    total_agents = len(evaluations)

    parts = [
        f"**{candidate.name}** received a consensus score of **{consensus_score}/100** "
        f"({_grade(consensus_score)}) with **{_recommendation(consensus_score)}** recommendation.",
        f"Agent panel: {hire_count}/{total_agents} recommend hire, {no_hire_count}/{total_agents} recommend no hire.",
    ]

    if risk_flags:
        parts.append(f"Risk flags: {', '.join(risk_flags[:3])}.")

    # Top strength across all agents
    all_s = [s for e in evaluations for s in e.strengths]
    if all_s:
        parts.append(f"Top strength: {all_s[0]}.")

    # Top concern
    all_c = [c for e in evaluations for c in e.concerns]
    if all_c:
        parts.append(f"Primary concern: {all_c[0]}.")

    return " ".join(parts)
