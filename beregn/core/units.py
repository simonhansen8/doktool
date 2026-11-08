"""Enheder og talformatering.

Internt regnes der altid konsistent i N og mm (dvs. spændinger i MPa = N/mm²,
momenter i Nmm). En enhed angiver kun hvordan en værdi vises og indlæses.
"""
from __future__ import annotations

import math
import re

# enhedsnavn -> (faktor til intern enhed, HTML-visning)
UNITS: dict[str, tuple[float, str]] = {
    "-": (1.0, ""),
    "": (1.0, ""),
    "N": (1.0, "N"),
    "kN": (1e3, "kN"),
    "MN": (1e6, "MN"),
    "Nmm": (1.0, "Nmm"),
    "kNm": (1e6, "kNm"),
    "kN/m": (1.0, "kN/m"),
    "mm": (1.0, "mm"),
    "cm": (10.0, "cm"),
    "m": (1e3, "m"),
    "mm2": (1.0, "mm<sup>2</sup>"),
    "cm2": (1e2, "cm<sup>2</sup>"),
    "mm3": (1.0, "mm<sup>3</sup>"),
    "cm3": (1e3, "cm<sup>3</sup>"),
    "mm4": (1.0, "mm<sup>4</sup>"),
    "cm4": (1e4, "cm<sup>4</sup>"),
    "mm6": (1.0, "mm<sup>6</sup>"),
    "cm6": (1e6, "cm<sup>6</sup>"),
    "MPa": (1.0, "MPa"),
    "N/mm2": (1.0, "N/mm<sup>2</sup>"),
    "GPa": (1e3, "GPa"),
    "kg/m": (1.0, "kg/m"),
    "%": (0.01, "%"),
}

_QTY = re.compile(r"^\s*([-+]?\d+(?:[.,]\d*)?(?:[eE][-+]?\d+)?)\s*([A-Za-z/%0-9²³⁴]*)\s*$")
_SUPMAP = str.maketrans({"²": "2", "³": "3", "⁴": "4"})


def to_internal(value: float, unit: str) -> float:
    return value * UNITS[unit][0]


def from_internal(value: float, unit: str) -> float:
    return value / UNITS[unit][0]


def parse_quantity(text, default_unit: str = "-") -> float:
    """'6,0 m' -> 6000.0 (mm). Et rent tal tolkes i default_unit."""
    if isinstance(text, (int, float)):
        return to_internal(float(text), default_unit)
    m = _QTY.match(str(text))
    if not m:
        raise ValueError(f"Kan ikke læse størrelse: {text!r}")
    num = float(m.group(1).replace(",", "."))
    unit = m.group(2).translate(_SUPMAP) or default_unit
    if unit not in UNITS:
        raise ValueError(f"Ukendt enhed {unit!r} i {text!r}")
    return to_internal(num, unit)


def unit_html(unit: str) -> str:
    return UNITS[unit][1]


class NumberFormat:
    """Talformatering med dansk decimalkomma som standard."""

    def __init__(self, decimal: str = ",", sig: int = 4):
        self.decimal = decimal
        self.sig = sig

    def __call__(self, x) -> str:
        if isinstance(x, bool):
            return str(x)
        if isinstance(x, int) and abs(x) < 100000:
            return self._sign(str(abs(x)), x < 0)
        x = float(x)
        if x == 0:
            return "0"
        ax = abs(x)
        if ax >= 1e6 or ax < 1e-3:
            exp = int(math.floor(math.log10(ax) / 3) * 3)
            mant = ax / 10 ** exp
            return self._sign(self._fixed(mant) + f"·10<sup>{exp}</sup>", x < 0)
        return self._sign(self._fixed(ax), x < 0)

    def _fixed(self, ax: float) -> str:
        digits = max(0, self.sig - 1 - int(math.floor(math.log10(ax))))
        s = f"{ax:.{digits}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        intpart, _, frac = s.partition(".")
        if len(intpart) > 4:  # tusindtalsseparator (tyndt mellemrum)
            groups = []
            while len(intpart) > 3:
                groups.insert(0, intpart[-3:])
                intpart = intpart[:-3]
            groups.insert(0, intpart)
            intpart = " ".join(groups)
        return intpart + (self.decimal + frac if frac else "")

    @staticmethod
    def _sign(s: str, neg: bool) -> str:
        return ("−" + s) if neg else s
