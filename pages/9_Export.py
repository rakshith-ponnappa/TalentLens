"""
Page 9: Export Center — Multi-format report generation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from export_engine import (
    export_candidate_report,
    export_comparative_report,
    export_executive_summary,
)

st.header("📤 Export Center")

if "scored_candidates" not in st.session_state:
    st.warning("No screening data. Run **Screening** first.")
    st.stop()

scores = st.session_state["scored_candidates"]
jd = st.session_state.get("jd_criteria")

# ---------------------------------------------------------------------------
# Export options
# ---------------------------------------------------------------------------

tab_single, tab_compare, tab_exec = st.tabs(
    ["Single Candidate", "Comparative Report", "Executive Summary"]
)

SINGLE_FORMATS = ["md", "html", "json", "docx", "pdf"]
COMPARE_FORMATS = ["md", "csv", "html", "json"]

# ---------------------------------------------------------------------------
# Single candidate export
# ---------------------------------------------------------------------------

with tab_single:
    st.subheader("Export Individual Candidate Report")

    col1, col2 = st.columns(2)
    with col1:
        names = [s.candidate.name for s in scores]
        selected = st.selectbox("Candidate", names, key="export_single_name")
    with col2:
        fmt = st.selectbox("Format", SINGLE_FORMATS, key="export_single_fmt")

    if st.button("📄 Generate Report", key="btn_single"):
        sc = next(s for s in scores if s.candidate.name == selected)

        with st.spinner(f"Generating {fmt.upper()} report..."):
            try:
                file_path = export_candidate_report(sc, jd, fmt=fmt)
                p = Path(file_path)

                st.success(f"Report saved: `{p.name}`")

                # Read file for preview/download
                mime_map = {
                    "md": ("text/markdown", "utf-8"),
                    "html": ("text/html", "utf-8"),
                    "json": ("application/json", "utf-8"),
                    "csv": ("text/csv", "utf-8"),
                    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", None),
                    "pdf": ("application/pdf", None),
                }
                mime, encoding = mime_map.get(fmt, ("text/plain", "utf-8"))

                if encoding:
                    data = p.read_text(encoding=encoding)
                    if fmt in ("md", "json"):
                        st.code(data[:3000], language="markdown" if fmt == "md" else "json")
                    elif fmt == "html":
                        st.components.v1.html(data, height=600, scrolling=True)
                    st.download_button(f"⬇️ Download {fmt.upper()}", data=data, file_name=p.name, mime=mime)
                else:
                    data = p.read_bytes()
                    st.download_button(f"⬇️ Download {fmt.upper()}", data=data, file_name=p.name, mime=mime)

            except Exception as e:
                st.error(f"Export failed: {e}")

# ---------------------------------------------------------------------------
# Comparative report
# ---------------------------------------------------------------------------

with tab_compare:
    st.subheader("Export Comparative Report")

    names = [s.candidate.name for s in scores]
    selected_names = st.multiselect(
        "Select candidates (2+)",
        names,
        default=names[:min(3, len(names))],
        key="export_compare_names",
    )

    fmt = st.selectbox("Format", COMPARE_FORMATS, key="export_compare_fmt")

    if st.button("📊 Generate Comparative Report", key="btn_compare", disabled=len(selected_names) < 2):
        sel_scores = [s for s in scores if s.candidate.name in selected_names]

        with st.spinner("Generating comparative report..."):
            try:
                file_path = export_comparative_report(sel_scores, jd, fmt=fmt)
                p = Path(file_path)

                st.success(f"Report saved: `{p.name}`")

                mime_map = {
                    "md": ("text/markdown", "utf-8"),
                    "csv": ("text/csv", "utf-8"),
                    "html": ("text/html", "utf-8"),
                    "json": ("application/json", "utf-8"),
                }
                mime, encoding = mime_map.get(fmt, ("text/plain", "utf-8"))

                data = p.read_text(encoding=encoding)
                if fmt in ("md", "json", "csv"):
                    st.code(data[:3000], language="markdown" if fmt == "md" else fmt)
                elif fmt == "html":
                    st.components.v1.html(data, height=600, scrolling=True)

                st.download_button(f"⬇️ Download {fmt.upper()}", data=data, file_name=p.name, mime=mime)

            except Exception as e:
                st.error(f"Export failed: {e}")

# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

with tab_exec:
    st.subheader("Executive Summary")
    st.caption("One-page hiring manager report with top candidates and recommendations (Markdown)")

    if st.button("📋 Generate Executive Summary", key="btn_exec"):
        with st.spinner("Generating executive summary..."):
            try:
                file_path = export_executive_summary(scores, jd)
                p = Path(file_path)

                st.success(f"Report saved: `{p.name}`")

                content = p.read_text(encoding="utf-8")
                st.markdown(content)

                st.download_button(
                    "⬇️ Download Markdown",
                    data=content,
                    file_name=p.name,
                    mime="text/markdown",
                )

            except Exception as e:
                st.error(f"Export failed: {e}")
