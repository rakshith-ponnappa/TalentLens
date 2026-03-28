#!/usr/bin/env python3
"""
main.py  –  Resume Screening Pipeline CLI

Usage examples:

  # Step 1: Analyze a JD (saves session state)
  python main.py jd path/to/jd.pdf
  python main.py jd path/to/jd.txt

  # Step 2: Screen resumes against the saved JD
  python main.py screen resume1.pdf resume2.pdf resume3.docx

  # Combined: JD + resumes in one command
  python main.py run --jd jd.pdf --resumes r1.pdf r2.pdf r3.pdf

  # Show detail for a specific candidate
  python main.py detail --resume r1.pdf

  # Re-run verification only
  python main.py verify --resume r1.pdf
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from config import load_config
from jd_analyzer import analyze_jd
from resume_parser import parse_resume, parse_resumes
from scorer import score_candidate, rank_candidates
from verifier import run_verification
from report_generator import (
    print_jd_summary,
    print_rankings,
    print_candidate_detail,
    export_json,
    console,
)

app = typer.Typer(
    name="resume-screener",
    help="End-to-end resume screening, ranking & verification pipeline",
    add_completion=False,
)

_SESSION_FILE = Path(__file__).parent / ".session.json"
_OUTPUT_DIR = Path(__file__).parent / "output"
_OUTPUT_DIR.mkdir(exist_ok=True)


# --------------------------------------------------------------------------
# Session helpers
# --------------------------------------------------------------------------

def _save_jd_session(jd_path: str) -> None:
    _SESSION_FILE.write_text(json.dumps({"jd_path": str(jd_path)}))


def _load_jd_path() -> str | None:
    if _SESSION_FILE.exists():
        return json.loads(_SESSION_FILE.read_text()).get("jd_path")
    return None


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

@app.command()
def jd(
    source: str = typer.Argument(..., help="Path to JD file (PDF/DOCX/TXT) or paste text"),
):
    """Parse and display a Job Description. Saves it for the next `screen` run."""
    cfg = load_config()
    p = Path(source)

    if not p.exists():
        console.print("[yellow]File not found – treating input as raw text.[/yellow]")

    with console.status("[bold cyan]Analyzing Job Description…[/bold cyan]"):
        jd_criteria = analyze_jd(source, cfg)

    print_jd_summary(jd_criteria)

    _save_jd_session(source)
    console.print(f"[dim]JD saved to session. Run `python main.py screen <resumes>` next.[/dim]")


@app.command()
def screen(
    resumes: list[str] = typer.Argument(..., help="Resume files (PDF/DOCX/TXT)"),
    jd_source: str = typer.Option(None, "--jd", "-j", help="JD file (uses session if omitted)"),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip background verification"),
    detail: bool = typer.Option(False, "--detail", "-d", help="Show per-candidate detail"),
    export: bool = typer.Option(True, "--export/--no-export", help="Export JSON report"),
    top: int = typer.Option(0, "--top", "-n", help="Show only top N candidates (0 = all)"),
):
    """Screen multiple resumes against a Job Description and rank them."""
    cfg = load_config()

    # Resolve JD
    jd_source = jd_source or _load_jd_path()
    if not jd_source:
        console.print("[bold red]No JD provided. Run `python main.py jd <file>` first.[/bold red]")
        raise typer.Exit(1)

    with console.status("[bold cyan]Parsing Job Description…[/bold cyan]"):
        jd_criteria = analyze_jd(jd_source, cfg)
    print_jd_summary(jd_criteria)

    # Parse resumes
    candidates = []
    for path in resumes:
        with console.status(f"[cyan]Parsing {Path(path).name}…[/cyan]"):
            try:
                candidates.append(parse_resume(path, cfg))
            except Exception as e:
                console.print(f"[red]Failed to parse {path}: {e}[/red]")

    if not candidates:
        console.print("[bold red]No resumes parsed successfully.[/bold red]")
        raise typer.Exit(1)

    console.print(f"\n[green]Parsed {len(candidates)} resume(s).[/green]")

    # Verify
    verifications = {}
    if not no_verify:
        console.print("\n[bold]Running background verification…[/bold]")
        for cand in candidates:
            with console.status(f"[dim]Verifying {cand.name}…[/dim]"):
                verifications[cand.name] = run_verification(cand, cfg)
    
    # Score
    scores = []
    for cand in candidates:
        ver = verifications.get(cand.name)
        scores.append(score_candidate(cand, jd_criteria, ver, cfg))

    ranked = rank_candidates(scores)
    if top > 0:
        ranked = ranked[:top]

    # Display
    console.print()
    print_rankings(ranked)

    if detail:
        for s in ranked:
            print_candidate_detail(s)

    # Export
    if export:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = _OUTPUT_DIR / f"screening_{ts}.json"
        export_json(ranked, jd_criteria, out)


@app.command()
def run(
    jd_source: str = typer.Option(..., "--jd", "-j", help="JD file path"),
    resumes: list[str] = typer.Option(..., "--resume", "-r", help="Resume file(s)"),
    no_verify: bool = typer.Option(False, "--no-verify"),
    detail: bool = typer.Option(False, "--detail", "-d"),
    top: int = typer.Option(0, "--top", "-n"),
):
    """Run full pipeline (JD + resumes) in a single command."""
    # Delegate to screen with jd_source provided
    _save_jd_session(jd_source)
    screen(
        resumes=list(resumes),
        jd_source=jd_source,
        no_verify=no_verify,
        detail=detail,
        export=True,
        top=top,
    )


@app.command()
def detail_cmd(
    resume: str = typer.Argument(..., help="Resume file"),
    jd_source: str = typer.Option(None, "--jd", "-j"),
    no_verify: bool = typer.Option(False, "--no-verify"),
):
    """Show full detail report for a single candidate."""
    cfg = load_config()

    jd_source = jd_source or _load_jd_path()
    if not jd_source:
        console.print("[bold red]No JD found. Run `python main.py jd <file>` first.[/bold red]")
        raise typer.Exit(1)

    with console.status("[cyan]Parsing…[/cyan]"):
        jd_criteria = analyze_jd(jd_source, cfg)
        candidate = parse_resume(resume, cfg)

    ver = None
    if not no_verify:
        with console.status(f"[dim]Verifying {candidate.name}…[/dim]"):
            ver = run_verification(candidate, cfg)

    score = score_candidate(candidate, jd_criteria, ver, cfg)
    score.rank = 1
    print_candidate_detail(score)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

if __name__ == "__main__":
    app()
