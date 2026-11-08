"""Fælles grundlag for eftervisningsmoduler.

Et eftervisningsmodul er en klasse med `key`, `title`, `clause` og en
`run(ctx)`-metode, der registreres med @register. Nye eftervisninger (andre
materialer, samlinger osv.) tilføjes blot som nye moduler.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.calc import Calc, Namespace
from ..core.units import NumberFormat
from ..materials import steel
from ..norms import Norm
from ..sections import PROP_INFO, ISection

REGISTRY: dict[str, type["Check"]] = {}


def register(cls):
    REGISTRY[cls.key] = cls
    return cls


# status-værdier
OK, FAIL, NA, UNSUPPORTED = "OK", "IKKE OK", "Ikke relevant", "Ikke understøttet"


@dataclass
class LTBInput:
    """Kipningsdata. C1, C2 og k_c udledes af momentform, men kan overskrives."""
    L: float | None = None              # kiplængde [mm] (afstand mellem kipafstivninger)
    momentform: str = "jaevn"           # jaevn | punkt_midt | lineaer | konstant
    psi: float = 1.0                    # endemomentforhold ved lineær momentfordeling
    lastplacering: str = "overflange"   # overflange | forskydningscenter | underflange
    k: float = 1.0
    k_w: float = 1.0
    C1: float | None = None
    C2: float | None = None
    k_c: float | None = None


@dataclass
class Member:
    name: str
    section: ISection
    grade: str
    L: float                            # elementlængde [mm]
    N_Ed: float = 0.0                   # [N], tryk positiv
    V_Ed: float = 0.0                   # [N]
    M_Ed: float = 0.0                   # [Nmm], om stærk akse
    L_cr_y: float | None = None
    L_cr_z: float | None = None
    ltb: LTBInput = field(default_factory=LTBInput)
    checks: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class CheckResult:
    key: str
    title: str
    clause: str
    calc: Calc
    utilisation: float | None = None
    status: str = OK
    governing: str = ""                 # hvilket udtryk der er styrende

    @property
    def ok(self) -> bool:
        return self.status in (OK, NA)


@dataclass
class Context:
    member: Member
    norm: Norm
    ns: Namespace
    fmt: NumberFormat
    results: dict[str, Any] = field(default_factory=dict)

    def calc(self) -> Calc:
        return Calc(self.ns, self.norm, self.fmt)


class Check:
    key = ""
    title = ""
    clause = ""
    requires: tuple[str, ...] = ()      # moduler der skal køres først

    def run(self, ctx: Context) -> CheckResult:  # pragma: no cover
        raise NotImplementedError

    def result(self, c: Calc, util: float | None, status: str | None = None, governing: str = ""):
        if status is None:
            status = OK if util is not None and util <= 1.0 + 1e-9 else FAIL
        return CheckResult(self.key, self.title, self.clause, c, util, status, governing)


# --------------------------------------------------------------- grundlag
def prepare(member: Member, norm: Norm, fmt: NumberFormat) -> tuple[Context, Calc]:
    """Læg tværsnit, materiale, længder og snitkræfter i det fælles navnerum
    og returnér et 'Grundlag'-afsnit til rapporten."""
    ns = Namespace()
    ctx = Context(member, norm, ns, fmt)
    c = ctx.calc()
    s = member.section

    c.note(f"<b>Profil:</b> {s.name}", ref="EN 10365")
    for key, attr in [("h", "h"), ("b", "b"), ("t_w", "tw"), ("t_f", "tf"), ("r", "r")]:
        unit, desc = PROP_INFO[key]
        c.given(key, getattr(s, attr), unit, desc)
    for key in ("A", "I_y", "W_el_y", "W_pl_y", "I_z", "W_pl_z", "I_t", "I_w", "g"):
        unit, desc = PROP_INFO[key]
        c.given(key, s.props[key], unit, desc)
    c.given("h_w", s.h_w, "mm", PROP_INFO["h_w"][1], show=False)
    c.given("c_f", s.c_f, "mm", "Flangens udragende del", show=False)
    c.given("c_w", s.c_w, "mm", "Kroppens fri højde", show=False)

    fy_src = norm.value("fy_kilde")
    st = steel(member.grade, s.t_max, fy_src)
    c.note(f"<b>Materiale:</b> {st.grade}, bestemmende godstykkelse t = {fmt(st.t)} mm")
    c.given("f_y", st.fy, "MPa", "Flydespænding", st.source)
    c.given("f_u", st.fu, "MPa", "Brudspænding", st.source)
    c.param("E", "G")

    c.note("<b>Geometri og snitkræfter</b> (regningsmæssige, N<sub>Ed</sub> &gt; 0 er tryk)")
    c.given("L", member.L, "m", "Elementlængde")
    c.given("N_Ed", member.N_Ed, "kN", "Normalkraft")
    c.given("V_Ed", member.V_Ed, "kN", "Forskydningskraft")
    c.given("M_Ed", member.M_Ed, "kNm", "Moment om y-aksen")
    return ctx, c
