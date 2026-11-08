"""Materialer. Stålkvaliteter med tykkelsesafhængig flydespænding."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DATA = Path(__file__).parent / "data"


@dataclass
class Steel:
    grade: str
    fy: float      # MPa
    fu: float      # MPa
    t: float       # den godstykkelse fy er bestemt for [mm]
    source: str


def _lookup(rows, t):
    for tmax, val in rows:
        if t <= tmax:
            return val
    raise ValueError(f"Godstykkelse t = {t} mm uden for tabellens område")


def steel(grade: str, t: float, fy_source: str = "tabel_3_1", data_file: Path | None = None) -> Steel:
    db = yaml.safe_load((data_file or DATA / "staal_EN10025-2.yaml").read_text(encoding="utf-8"))
    tab = db[fy_source]
    g = grade.upper().split()[0]
    if g not in tab:
        raise KeyError(f"Ukendt stålkvalitet {grade}; kendte: {[k for k in tab if k != 'kilde']}")
    return Steel(g, _lookup(tab[g]["fy"], t), _lookup(tab[g]["fu"], t), t, tab["kilde"])
