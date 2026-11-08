"""Indlæsning af projekter fra YAML (eller en tilsvarende dict fra JSON/Excel/FEM).

Størrelser kan skrives med enhed, f.eks. "6,0 m", "120 kNm", "85 kN".
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ..checks import LTBInput, Member
from ..core.units import NumberFormat, parse_quantity as q
from ..engine import Project
from ..norms import load_norm
from ..sections import get as get_section


def member_from_dict(d: dict) -> Member:
    s = d.get("snitkraefter", {})
    k = d.get("kipning", {}) or {}
    L = q(d["laengde"], "m")
    ltb = LTBInput(
        L=q(k["laengde"], "m") if "laengde" in k else None,
        momentform=k.get("momentform", "jaevn"),
        psi=float(k.get("psi", 1.0)),
        lastplacering=k.get("lastplacering", "overflange"),
        k=float(k.get("k", 1.0)), k_w=float(k.get("k_w", 1.0)),
        C1=k.get("C1"), C2=k.get("C2"), k_c=k.get("k_c"),
    )
    return Member(
        name=str(d["navn"]),
        description=d.get("beskrivelse", ""),
        section=get_section(d["profil"]),
        grade=d.get("staal", "S355"),
        L=L,
        N_Ed=q(s.get("N_Ed", 0), "kN"),
        V_Ed=q(s.get("V_Ed", 0), "kN"),
        M_Ed=q(s.get("M_Ed", 0), "kNm"),
        L_cr_y=q(d["knaeklaengde_y"], "m") if "knaeklaengde_y" in d else None,
        L_cr_z=q(d["knaeklaengde_z"], "m") if "knaeklaengde_z" in d else None,
        ltb=ltb,
        checks=d.get("eftervisninger", []),
    )


def project_from_dict(d: dict, norm_dirs=()) -> Project:
    n = d.get("norm", {})
    opts = {k: v for k, v in n.items() if k not in ("standard", "nationalt_anneks")}
    norm = load_norm(n.get("standard", "EN1993-1-1"), n.get("nationalt_anneks", "DK"), opts, norm_dirs)
    fmt = NumberFormat(**(d.get("format") or {}))
    return Project(d.get("projekt", {}), norm, [member_from_dict(m) for m in d["elementer"]], fmt)


def load_project(path: str | Path, norm_dirs=()) -> Project:
    return project_from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")), norm_dirs)
