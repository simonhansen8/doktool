"""Profilbibliotek for valsede I- og H-profiler.

Tværsnitskonstanterne beregnes ud fra geometrien (h, b, tw, tf, r) med de
formler, profilproducenterne bruger, så biblioteket kan udvides blot ved at
tilføje en linje i CSV-filen. Afvigelse fra producenttabeller er typisk < 1 %.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).parent / "data"
_PI = math.pi


@dataclass
class ISection:
    name: str
    series: str
    h: float
    b: float
    tw: float
    tf: float
    r: float
    props: dict = field(init=False)

    def __post_init__(self):
        h, b, tw, tf, r = self.h, self.b, self.tw, self.tf, self.r
        hi = h - 2 * tf                       # indvendig højde
        A = 2 * b * tf + hi * tw + (4 - _PI) * r ** 2
        Iy = (b * h ** 3 - (b - tw) * hi ** 3) / 12 + 0.03 * r ** 4 + 0.2146 * r ** 2 * (hi - 0.4468 * r) ** 2
        Iz = (2 * tf * b ** 3 + hi * tw ** 3) / 12 + 0.03 * r ** 4 + 0.2146 * r ** 2 * (tw + 0.4468 * r) ** 2
        Wpl_y = tw * h ** 2 / 4 + (b - tw) * (h - tf) * tf + (4 - _PI) / 2 * r ** 2 * hi + (3 * _PI - 10) / 3 * r ** 3
        Wpl_z = b ** 2 * tf / 2 + hi * tw ** 2 / 4 + r ** 3 * (10 / 3 - _PI) + (2 - _PI / 2) * tw * r ** 2
        # vridningsinertimoment, El Darwish & Johnston
        a1 = (-0.042 + 0.2204 * tw / tf + 0.1355 * r / tf - 0.0865 * r * tw / tf ** 2
              - 0.0725 * tw ** 2 / tf ** 2)
        D1 = ((tf + r) ** 2 + tw * (r + tw / 4)) / (2 * r + tf)
        It = 2 / 3 * b * tf ** 3 + hi * tw ** 3 / 3 + 2 * a1 * D1 ** 4 - 0.420 * tf ** 4
        Iw = Iz * (h - tf) ** 2 / 4
        Av_z = A - 2 * b * tf + (tw + 2 * r) * tf
        self.props = dict(
            A=A, I_y=Iy, I_z=Iz, W_el_y=Iy / (h / 2), W_el_z=Iz / (b / 2), W_pl_y=Wpl_y, W_pl_z=Wpl_z,
            i_y=math.sqrt(Iy / A), i_z=math.sqrt(Iz / A), I_t=It, I_w=Iw, A_v_z_0=Av_z,
            h_w=hi, c_f=(b - tw - 2 * r) / 2, c_w=hi - 2 * r, g=A * 7850e-9 * 1e3,
        )

    def __getattr__(self, k):
        try:
            return self.__dict__["props"][k]
        except KeyError:
            raise AttributeError(k) from None

    @property
    def t_max(self) -> float:
        return max(self.tf, self.tw)


# symbol, enhed, beskrivelse – bruges når konstanter vises i rapporten
PROP_INFO = {
    "h": ("mm", "Højde"), "b": ("mm", "Flangebredde"), "t_w": ("mm", "Kroptykkelse"),
    "t_f": ("mm", "Flangetykkelse"), "r": ("mm", "Rundingsradius"),
    "A": ("cm2", "Tværsnitsareal"), "I_y": ("cm4", "Inertimoment, y-akse"),
    "I_z": ("cm4", "Inertimoment, z-akse"), "W_el_y": ("cm3", "Elastisk modstandsmoment, y"),
    "W_pl_y": ("cm3", "Plastisk modstandsmoment, y"), "W_el_z": ("cm3", "Elastisk modstandsmoment, z"),
    "W_pl_z": ("cm3", "Plastisk modstandsmoment, z"), "i_y": ("mm", "Inertiradius, y"),
    "i_z": ("mm", "Inertiradius, z"), "I_t": ("cm4", "Vridningsinertimoment"),
    "I_w": ("cm6", "Hvælvningsinertimoment"), "h_w": ("mm", "Kropshøjde mellem flanger"),
    "g": ("kg/m", "Egenvægt"),
}


def library(path: Path | None = None) -> dict[str, ISection]:
    lib = {}
    with open(path or DATA / "valsede_I.csv", encoding="utf-8") as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in rows:
            s = ISection(row["navn"], row["serie"], *(float(row[k]) for k in ("h", "b", "tw", "tf", "r")))
            lib[_key(s.name)] = s
    return lib


def _key(name: str) -> str:
    return name.upper().replace(" ", "")


_LIB: dict[str, ISection] | None = None


def get(name: str) -> ISection:
    global _LIB
    if _LIB is None:
        _LIB = library()
    try:
        return _LIB[_key(name)]
    except KeyError:
        raise KeyError(f"Ukendt profil {name!r}") from None
