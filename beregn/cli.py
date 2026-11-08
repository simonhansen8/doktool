"""Kommandolinje:  python -m beregn projekt.yaml -o rapport.pdf"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import run_project
from .io.yaml_input import load_project
from .report.html import render_html, write_pdf


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="beregn", description="Generér statisk beregningsrapport.")
    ap.add_argument("input", help="Projektfil (YAML eller Excel)")
    ap.add_argument("-o", "--output", help="Rapportfil (.pdf eller .html). Standard: <input>.pdf")
    ap.add_argument("--skabelon", help="Mappe med firmaskabelon (skabelon.yaml, style.css, rapport.html.j2)")
    ap.add_argument("--norm-mappe", action="append", default=[], help="Ekstra mappe med norm-filer")
    a = ap.parse_args(argv)

    if a.input.lower().endswith((".xlsx", ".xlsm")):
        from .io.excel_input import load_project_excel
        project = load_project_excel(a.input, a.norm_mappe)
    else:
        project = load_project(a.input, a.norm_mappe)
    results = run_project(project)
    html = render_html(project, results, a.skabelon)
    out = Path(a.output or Path(a.input).with_suffix(".pdf"))
    if out.suffix.lower() == ".html":
        out.write_text(html, encoding="utf-8")
    else:
        write_pdf(html, out)

    width = max(len(r.member.name) for r in results)
    for mr in results:
        u = mr.max_util
        flag = "IKKE OK" if not mr.ok else ("TJEK" + (f" (mangler {', '.join(mr.missing)})" if mr.missing else "")
                                             if mr.unsupported else "OK")
        print(f"{mr.member.name:<{width}}  {mr.member.section.name:<8} "
              f"{(f'{u*100:5.1f} %') if u is not None else '   - ':>8}  {flag}")
    print(f"Rapport skrevet: {out}")
    return 0 if all(mr.ok for mr in results) else 1


if __name__ == "__main__":
    sys.exit(main())
