"""Kører eftervisningerne for et projekt og samler resultaterne."""
from __future__ import annotations

from dataclasses import dataclass, field

from .checks import REGISTRY, CheckResult, Member, prepare
from .core.calc import Calc
from .core.units import NumberFormat
from .norms import Norm

DEFAULT_CHECKS = ["klassifikation", "boejning", "forskydning", "kombineret", "soejlefladning", "kipning",
                  "interaktion"]


@dataclass
class MemberResult:
    member: Member
    basis: Calc
    results: list[CheckResult] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)   # eftervisninger der mangler for elementet

    @property
    def max_util(self) -> float | None:
        u = [r.utilisation for r in self.results if r.utilisation is not None]
        return max(u) if u else None

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def unsupported(self) -> bool:
        return bool(self.missing) or any(r.status == "Ikke understøttet" for r in self.results)


@dataclass
class Project:
    info: dict
    norm: Norm
    members: list[Member]
    fmt: NumberFormat = field(default_factory=NumberFormat)


def _order(keys: list[str]) -> list[str]:
    out: list[str] = []

    def add(k):
        if k in out:
            return
        if k not in REGISTRY:
            raise KeyError(f"Ukendt eftervisning '{k}'. Kendte: {sorted(REGISTRY)}")
        for dep in REGISTRY[k].requires:
            add(dep)
        out.append(k)

    for k in keys:
        add(k)
    return out


def run_member(member: Member, norm: Norm, fmt: NumberFormat) -> MemberResult:
    ctx, basis = prepare(member, norm, fmt)
    mr = MemberResult(member, basis)
    order = _order(member.checks or DEFAULT_CHECKS)
    ctx.results["planlagt"] = order
    for key in order:
        mr.results.append(REGISTRY[key]().run(ctx))
    mr.missing = ctx.results.get("mangler", [])
    return mr


def run_project(p: Project) -> list[MemberResult]:
    return [run_member(m, p.norm, p.fmt) for m in p.members]
