"""Rapport-laget: genererer HTML og PDF ud fra beregningsresultaterne."""
from __future__ import annotations

import base64
import datetime as dt
import mimetypes
from pathlib import Path

import jinja2
import yaml

from .. import __version__
from ..core.expr import symbol_html
from ..core.units import NumberFormat
from ..engine import MemberResult, Project

TEMPLATES = Path(__file__).parent / "templates"


def _gov_html(text: str) -> str:
    return " ".join(symbol_html(t) if "_" in t else t for t in text.split(" "))


def _status(mr: MemberResult) -> str:
    if any(r.status == "IKKE OK" for r in mr.results):
        return "IKKE OK"
    if mr.missing:
        return "Mangler " + ", ".join(mr.missing)
    if mr.unsupported:
        return "Ikke understøttet"
    return "OK"


def _logo(tdir: Path, logo: str) -> str:
    if not logo:
        return ""
    p = (tdir / logo).resolve()
    if not p.exists():
        return ""
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def build_context(project: Project, results: list[MemberResult], tdir: Path) -> dict:
    fmt = project.fmt
    skabelon = yaml.safe_load((tdir / "skabelon.yaml").read_text(encoding="utf-8"))
    elementer = []
    for mr in results:
        m = mr.member
        gov = max((r for r in mr.results if r.utilisation is not None),
                  key=lambda r: r.utilisation, default=None)
        elementer.append(dict(
            navn=m.name, beskrivelse=m.description, profil=m.section.name, staal=m.grade,
            util=mr.max_util, status=_status(mr),
            styrende=f"{gov.title} ({gov.clause.replace('EN 1993-1-1, ', '')})" if gov else "–",
            basis=mr.basis.html_steps(),
            checks=[dict(title=r.title, clause=r.clause, util=r.utilisation, status=r.status,
                         governing=_gov_html(r.governing), steps=r.calc.html_steps())
                    for r in mr.results],
        ))
    norm_params = []
    for p in project.norm.params.values():
        if isinstance(p.value, bool):
            val = "ja" if p.value else "nej"
        elif isinstance(p.value, str):
            val = p.value.replace("_", " ")
        else:
            val = fmt(p.value) + (f" {p.unit}" if p.unit not in ("-", "") else "")
        norm_params.append(dict(sym=symbol_html(p.name) if not isinstance(p.value, (str, bool)) else p.desc,
                                value=val, desc=p.desc if not isinstance(p.value, (str, bool)) else "",
                                source=p.source))
    return dict(
        projekt=project.info, norm=project.norm, norm_params=norm_params, elementer=elementer,
        skabelon=skabelon, logo=_logo(tdir, skabelon.get("firma", {}).get("logo", "")),
        css=(tdir / "style.css").read_text(encoding="utf-8"),
        dato=dt.date.today().strftime("%d.%m.%Y"), version=__version__,
        fmt=lambda x, sig=4: NumberFormat(fmt.decimal, sig)(x),
    )


def render_html(project: Project, results: list[MemberResult], template: str | Path | None = None) -> str:
    tdir = Path(template) if template else TEMPLATES / "standard"
    env = jinja2.Environment(loader=jinja2.FileSystemLoader([tdir, TEMPLATES / "standard"]),
                             autoescape=False, trim_blocks=True, lstrip_blocks=True)
    return env.get_template("rapport.html.j2").render(**build_context(project, results, tdir))


def write_pdf(html: str, path: str | Path):
    try:
        from weasyprint import HTML
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("PDF kræver WeasyPrint: pip install weasyprint") from e
    HTML(string=html).write_pdf(str(path))
