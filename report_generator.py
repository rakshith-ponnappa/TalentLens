"""
report_generator.py  –  Rich terminal output + JSON / Markdown export.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.markup import escape

from models import CandidateScore, JDCriteria

console = Console()


# --------------------------------------------------------------------------
# Terminal display
# --------------------------------------------------------------------------

def print_jd_summary(jd: JDCriteria) -> None:
    console.print(Panel.fit(
        f"[bold cyan]{jd.title}[/bold cyan]\n"
        f"[dim]Level:[/dim] {jd.role_level}  |  "
        f"[dim]Industry:[/dim] {jd.industry}  |  "
        f"[dim]Experience:[/dim] {jd.min_experience_years}+ yrs\n"
        f"[dim]Education:[/dim] {jd.education_level}+\n\n"
        f"[bold]Required skills ({len(jd.required_skills)}):[/bold]  "
        + ", ".join(jd.required_skills[:15])
        + ("..." if len(jd.required_skills) > 15 else ""),
        title="[bold]Job Description Parsed[/bold]",
        border_style="cyan",
    ))


def print_rankings(scores: list[CandidateScore]) -> None:
    table = Table(
        title="[bold]Candidate Rankings[/bold]",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("#", style="bold", width=3, justify="right")
    table.add_column("Candidate", min_width=20)
    table.add_column("Score", justify="right", width=7)
    table.add_column("Match", justify="right", width=8)
    table.add_column("Grade", justify="center", width=6)
    table.add_column("Req Skills", justify="center", width=12)
    table.add_column("Exp (yrs)", justify="right", width=9)
    table.add_column("Trust", justify="right", width=7)
    table.add_column("LinkedIn", justify="center", width=9)
    table.add_column("Identity", justify="center", width=9)
    table.add_column("Companies", justify="center", width=12)

    for s in scores:
        grade_style = {
            "A+": "bold green", "A": "green", "B+": "cyan", "B": "cyan",
            "C": "yellow", "D": "orange1", "F": "red",
        }.get(s.grade, "white")

        trust = s.verification.overall_trust_score
        trust_style = "green" if trust >= 0.7 else "yellow" if trust >= 0.4 else "red"
        trust_str = f"[{trust_style}]{trust:.0%}[/{trust_style}]"

        li = s.verification.linkedin
        li_str = (
            "[green]✓[/green]" if (li and li.url_resolves)
            else "[red]✗[/red]" if (li and li.url)
            else "[dim]–[/dim]"
        )

        ident = s.verification.identity
        if ident:
            id_score = ident.overall_identity_score
            id_style = "green" if id_score >= 0.6 else "yellow" if id_score >= 0.4 else "red"
            id_str = f"[{id_style}]{id_score:.0%}[/{id_style}]"
        else:
            id_str = "[dim]–[/dim]"

        req_pct = (
            len(s.matched_required_skills) / max(len(s.matched_required_skills) + len(s.missing_required_skills), 1)
        )
        req_str = (
            f"[green]{req_pct:.0%}[/green]" if req_pct >= 0.8
            else f"[yellow]{req_pct:.0%}[/yellow]" if req_pct >= 0.5
            else f"[red]{req_pct:.0%}[/red]"
        )

        co_verified = sum(1 for c in s.verification.companies if c.found)
        co_total = len(s.verification.companies)
        co_str = (
            f"[green]{co_verified}/{co_total}[/green]" if co_verified == co_total and co_total > 0
            else f"[yellow]{co_verified}/{co_total}[/yellow]" if co_total > 0
            else "[dim]–[/dim]"
        )

        table.add_row(
            str(s.rank),
            escape(s.candidate.name),
            f"[{grade_style}]{s.overall_score:.1f}[/{grade_style}]",
            f"{s.similarity_pct:.1f}%",
            f"[{grade_style}]{s.grade}[/{grade_style}]",
            req_str,
            f"{s.candidate.total_experience_years:.1f}",
            trust_str,
            li_str,
            id_str,
            co_str,
        )

    console.print(table)


def print_candidate_detail(s: CandidateScore) -> None:
    console.rule(f"[bold cyan]#{s.rank} – {s.candidate.name}[/bold cyan]")

    # Score breakdown
    b = s.breakdown
    score_lines = (
        f"  Required Skills   {b.required_skills:5.1f} pts\n"
        f"  Preferred Skills  {b.preferred_skills:5.1f} pts\n"
        f"  Experience        {b.experience:5.1f} pts\n"
        f"  Education         {b.education:5.1f} pts\n"
        f"  Certifications    {b.certifications:5.1f} pts\n"
        f"  Semantic Sim.     {b.semantic_similarity:5.1f} pts\n"
        f"  [bold]TOTAL             {s.overall_score:5.1f} / 100[/bold]"
    )
    console.print(Panel(score_lines, title="Score Breakdown", border_style="green"))

    # Skills
    if s.matched_required_skills:
        console.print(f"  [green]✓ Required skills matched:[/green] " + ", ".join(s.matched_required_skills))
    if s.missing_required_skills:
        console.print(f"  [red]✗ Required skills missing:[/red] " + ", ".join(s.missing_required_skills))

    # LinkedIn
    li = s.verification.linkedin
    if li and li.url:
        li_status = "[green]✓ Verified[/green]" if li.url_resolves else "[red]✗ Not found[/red]"
        console.print(f"\n  LinkedIn: {li_status}  Auth score: {li.authenticity_score:.0%}")
        if li.red_flags:
            for flag in li.red_flags:
                console.print(f"    [yellow]⚠ {escape(flag)}[/yellow]")

    # Companies
    if s.verification.companies:
        console.print("\n  [bold]Company verification:[/bold]")
        for co in s.verification.companies:
            status = "[green]✓[/green]" if co.found else "[red]✗[/red]"
            console.print(
                f"    {status} {escape(co.name)} – {co.company_type}"
                f" | {co.employee_count} employees"
                f" | Legit score: {co.legitimacy_score:.0%}"
                + (f" [{co.status}]" if co.status != "Unknown" else "")
            )

    # Certifications
    if s.candidate.certifications:
        console.print("\n  [bold]Certifications:[/bold]")
        for cert in s.verification.certifications:
            found = "[green]✓ Known[/green]" if cert.found_in_registry else "[yellow]? Unknown cert[/yellow]"
            console.print(f"    {found}  {escape(cert.name)}  ({escape(cert.issuer)})")
            if cert.verification_url:
                console.print(f"       Verify: {cert.verification_url}")

    # Identity verification (always present; critical when no LinkedIn)
    ident = s.verification.identity
    if ident:
        method_label = {
            "LinkedIn": "[green]LinkedIn + alt[/green]",
            "Alternative": "[yellow]Alternative (no LinkedIn)[/yellow]",
            "Partial": "[red]Partial[/red]",
        }.get(ident.method, ident.method)
        console.print(f"\n  [bold]Identity verification ({method_label}):[/bold]"
                       f"  Score: {ident.overall_identity_score:.0%}")

        # Email
        if ident.email:
            em = ident.email
            fmt_ok = "[green]✓[/green]" if em.format_valid else "[red]✗[/red]"
            mx_ok = "[green]✓[/green]" if em.mx_record_exists else "[red]✗[/red]"
            dtype = {
                "Corporate": "[green]Corporate[/green]",
                "Personal": "[dim]Personal[/dim]",
                "Disposable": "[red]DISPOSABLE[/red]",
            }.get(em.domain_type, em.domain_type)
            console.print(f"    Email: {fmt_ok} format  |  {mx_ok} MX  |  {dtype}  |  {escape(em.domain)}")
            if em.domain_matches_employer:
                console.print(f"      [green]✓ Domain matches a claimed employer[/green]")
            if em.domain_type == "Disposable":
                console.print(f"      [red]⚠ Disposable email – high risk[/red]")

        # Education
        if ident.education:
            console.print("    [bold]Education:[/bold]")
            for edu in ident.education:
                found = "[green]✓[/green]" if edu.found_online else "[yellow]?[/yellow]"
                console.print(f"      {found} {escape(edu.institution)} ({edu.source})")

        # Timeline
        if ident.timeline:
            tl = ident.timeline
            plau = "[green]✓ Plausible[/green]" if tl.timeline_plausible else "[yellow]⚠ Check[/yellow]"
            console.print(f"    Timeline: {plau}"
                          f"  (claimed {tl.total_claimed_years} yrs, calculated {tl.calculated_years} yrs)")
            for gap in tl.gap_details:
                console.print(f"      [yellow]⚠ {escape(gap)}[/yellow]")
            for overlap in tl.overlap_details:
                console.print(f"      [red]⚠ {escape(overlap)}[/red]")

        # Web presence
        if ident.web_presence:
            wp = ident.web_presence
            console.print(f"    Web presence: {wp.presence_score:.0%}"
                          f"  ({wp.results_found} profile(s) found)")
            if wp.name_company_cooccurrence:
                console.print("      [green]✓ Name + company confirmed online[/green]")
            for prof in wp.professional_profiles:
                console.print(f"      [dim]→ {escape(prof)}[/dim]")
            for flag in wp.red_flags:
                console.print(f"      [yellow]⚠ {escape(flag)}[/yellow]")


# --------------------------------------------------------------------------
# JSON export
# --------------------------------------------------------------------------

def export_json(scores: list[CandidateScore], jd: JDCriteria, out_path: Path) -> None:
    data = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "job_title": jd.title,
        "candidates": [_score_to_dict(s) for s in scores],
    }
    out_path.write_text(json.dumps(data, indent=2, default=str))
    console.print(f"\n[dim]JSON report saved → {out_path}[/dim]")


def _score_to_dict(s: CandidateScore) -> dict:
    return {
        "rank": s.rank,
        "name": s.candidate.name,
        "email": s.candidate.email,
        "linkedin_url": s.candidate.linkedin_url,
        "overall_score": s.overall_score,
        "similarity_pct": s.similarity_pct,
        "grade": s.grade,
        "experience_years": s.candidate.total_experience_years,
        "breakdown": {
            "required_skills": s.breakdown.required_skills,
            "preferred_skills": s.breakdown.preferred_skills,
            "experience": s.breakdown.experience,
            "education": s.breakdown.education,
            "certifications": s.breakdown.certifications,
            "semantic_similarity": s.breakdown.semantic_similarity,
        },
        "matched_required_skills": s.matched_required_skills,
        "missing_required_skills": s.missing_required_skills,
        "matched_preferred_skills": s.matched_preferred_skills,
        "verification": {
            "overall_trust_score": s.verification.overall_trust_score,
            "linkedin": {
                "url": s.verification.linkedin.url if s.verification.linkedin else "",
                "resolves": s.verification.linkedin.url_resolves if s.verification.linkedin else False,
                "authenticity_score": s.verification.linkedin.authenticity_score if s.verification.linkedin else 0,
                "red_flags": s.verification.linkedin.red_flags if s.verification.linkedin else [],
            },
            "companies": [
                {
                    "name": c.name,
                    "found": c.found,
                    "source": c.source,
                    "company_type": c.company_type,
                    "employee_count": c.employee_count,
                    "legitimacy_score": c.legitimacy_score,
                    "status": c.status,
                }
                for c in s.verification.companies
            ],
            "certifications": [
                {
                    "name": c.name,
                    "issuer": c.issuer,
                    "found_in_registry": c.found_in_registry,
                    "verification_url": c.verification_url,
                }
                for c in s.verification.certifications
            ],
            "identity": _identity_to_dict(s.verification.identity),
        },
    }


def _identity_to_dict(ident) -> dict:
    if not ident:
        return {}
    result: dict = {
        "method": ident.method,
        "overall_identity_score": ident.overall_identity_score,
    }
    if ident.email:
        result["email"] = {
            "address": ident.email.address,
            "format_valid": ident.email.format_valid,
            "domain": ident.email.domain,
            "domain_type": ident.email.domain_type,
            "domain_matches_employer": ident.email.domain_matches_employer,
            "mx_record_exists": ident.email.mx_record_exists,
            "deliverable": ident.email.deliverable,
        }
    if ident.education:
        result["education"] = [
            {"institution": e.institution, "found_online": e.found_online, "source": e.source}
            for e in ident.education
        ]
    if ident.timeline:
        result["timeline"] = {
            "has_gaps": ident.timeline.has_gaps,
            "gap_details": ident.timeline.gap_details,
            "has_overlaps": ident.timeline.has_overlaps,
            "overlap_details": ident.timeline.overlap_details,
            "claimed_years": ident.timeline.total_claimed_years,
            "calculated_years": ident.timeline.calculated_years,
            "plausible": ident.timeline.timeline_plausible,
        }
    if ident.web_presence:
        result["web_presence"] = {
            "profiles_found": ident.web_presence.results_found,
            "professional_profiles": ident.web_presence.professional_profiles,
            "name_company_cooccurrence": ident.web_presence.name_company_cooccurrence,
            "presence_score": ident.web_presence.presence_score,
            "red_flags": ident.web_presence.red_flags,
        }
    return result
