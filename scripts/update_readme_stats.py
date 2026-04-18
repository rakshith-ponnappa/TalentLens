"""Auto-update test stats in README.md from pipeline artifacts."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
COVERAGE_JSON = ROOT / "reports" / "coverage.json"
ALLURE_DIR = ROOT / "allure-results"


def _count_tests() -> tuple[int, int, int]:
    """Count total tests, passed, and test files from allure-results."""
    total = passed = 0
    test_files: set[str] = set()
    if ALLURE_DIR.exists():
        for f in ALLURE_DIR.glob("*-result.json"):
            try:
                data = json.loads(f.read_text())
                total += 1
                if data.get("status") == "passed":
                    passed += 1
                # Extract test file from fullName like "tests.test_pipeline.TestStage#..."
                full = data.get("fullName", "")
                parts = full.split(".")
                for p in parts:
                    if p.startswith("test_"):
                        test_files.add(p)
                        break
            except (json.JSONDecodeError, KeyError):
                continue
    return total, passed, len(test_files) if test_files else 0


def _get_coverage() -> float:
    """Read coverage percentage from reports/coverage.json."""
    if COVERAGE_JSON.exists():
        try:
            data = json.loads(COVERAGE_JSON.read_text())
            return round(data.get("totals", {}).get("percent_covered", 0), 1)
        except (json.JSONDecodeError, KeyError):
            pass
    return 0.0


def main() -> None:
    if not README.exists():
        print("README.md not found")
        sys.exit(1)

    total, passed, test_files = _count_tests()
    coverage = _get_coverage()

    if total == 0:
        print("No allure results found — run tests first")
        sys.exit(0)

    pass_rate = round(passed / total * 100) if total else 0

    new_stats = (
        "<!-- BEGIN TEST STATS -->\n"
        "| Metric | Value |\n"
        "|:-------|:------|\n"
        f"| **Total Tests** | {total} |\n"
        f"| **Test Files** | {test_files} |\n"
        f"| **Pass Rate** | {pass_rate}% |\n"
        f"| **Coverage** | {coverage}% |\n"
        "<!-- END TEST STATS -->"
    )

    text = README.read_text()
    pattern = r"<!-- BEGIN TEST STATS -->.*?<!-- END TEST STATS -->"
    if re.search(pattern, text, re.DOTALL):
        updated = re.sub(pattern, new_stats, text, flags=re.DOTALL)
        README.write_text(updated)
        print(f"✅ README updated: {total} tests, {pass_rate}% pass, {coverage}% coverage")
    else:
        print("⚠️  No <!-- BEGIN TEST STATS --> marker found in README.md")


if __name__ == "__main__":
    main()
