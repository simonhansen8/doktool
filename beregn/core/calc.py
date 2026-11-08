"""Beregnings-sporing.

En `Calc` registrerer hvert trin i en eftervisning: givne værdier, formler med
indsatte værdier, betingelser og udnyttelsesgrader. Trinene renderes senere til
rapporten, så rapporten altid viser præcis det, der faktisk er regnet.
"""
from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Any

from . import expr as E
from .units import NumberFormat, from_internal, to_internal, unit_html


@dataclass
class Var:
    name: str
    value: Any                 # intern værdi (N, mm) eller tekst
    unit: str = "-"
    desc: str = ""
    ref: str = ""
    symbol: str | None = None  # HTML-override af symbol

    @property
    def sym(self) -> str:
        return self.symbol or E.symbol_html(self.name)


class Namespace(dict):
    """Variabler, der deles mellem eftervisningerne for ét element."""

    def numeric(self) -> dict[str, Any]:
        return {k: v.value for k, v in self.items()}


# ------------------------------------------------------------------ trin
@dataclass
class Step:
    kind: str
    desc: str = ""
    ref: str = ""


@dataclass
class GivenStep(Step):
    vars: list[Var] = field(default_factory=list)


@dataclass
class EqStep(Step):
    var: Var | None = None
    expr: str = ""
    show_subst: bool = True
    is_util: bool = False


@dataclass
class CondStep(Step):
    lhs: str = ""
    op: str = "<="
    rhs: str = ""
    lhs_val: float = 0.0
    rhs_val: float = 0.0
    unit: str = "-"
    passed: bool = True
    text_true: str = ""
    text_false: str = ""


@dataclass
class NoteStep(Step):
    level: str = "info"   # info | warn | error


_OPS = {"<=": operator.le, "<": operator.lt, ">=": operator.ge, ">": operator.gt}
_OP_HTML = {"<=": "≤", "<": "&lt;", ">=": "≥", ">": "&gt;"}


class Calc:
    def __init__(self, ns: Namespace, norm=None, fmt: NumberFormat | None = None):
        self.ns = ns
        self.norm = norm
        self.fmt = fmt or NumberFormat()
        self.steps: list[Step] = []

    # ---------------------------------------------------------------- input
    def given(self, name: str, value, unit: str = "-", desc: str = "", ref: str = "",
              *, internal: bool = True, show: bool = True, symbol: str | None = None):
        """Definér en kendt værdi. `internal=False` betyder at value er i `unit`."""
        if not internal and not isinstance(value, str):
            value = to_internal(value, unit)
        v = Var(name, value, unit, desc, ref, symbol)
        self.ns[name] = v
        if show:
            last = self.steps[-1] if self.steps else None
            if isinstance(last, GivenStep):
                last.vars.append(v)
            else:
                self.steps.append(GivenStep("given", vars=[v]))
        return value

    def use(self, name: str, desc: str | None = None, unit: str | None = None):
        """Vis en allerede kendt værdi (f.eks. tværsnitskonstant) i dette afsnit."""
        v = self.ns[name]
        shown = Var(v.name, v.value, unit or v.unit, desc if desc is not None else v.desc, v.ref, v.symbol)
        last = self.steps[-1] if self.steps else None
        if isinstance(last, GivenStep):
            last.vars.append(shown)
        else:
            self.steps.append(GivenStep("given", vars=[shown]))
        return v.value

    def param(self, *names: str):
        """Hent normparametre (partialkoefficienter m.m.) fra norm-laget."""
        out = []
        for n in names:
            p = self.norm.param(n)
            out.append(self.given(n, p.value, p.unit, p.desc, p.source))
        return out[0] if len(out) == 1 else out

    # ---------------------------------------------------------------- regning
    def eq(self, name: str, expr: str, unit: str = "-", desc: str = "", ref: str = "",
           *, show_subst: bool | None = None, symbol: str | None = None, util: bool = False):
        value = E.evaluate(expr, self.ns.numeric())
        v = Var(name, value, unit, desc, ref, symbol)
        self.ns[name] = v
        trivial = E.parse(expr).__class__.__name__ in ("Name", "Constant")
        self.steps.append(EqStep("eq", desc, ref, var=v, expr=expr,
                                 show_subst=(not trivial) if show_subst is None else show_subst,
                                 is_util=util))
        return value

    def util(self, name: str, expr: str, desc: str = "Udnyttelsesgrad", ref: str = ""):
        return self.eq(name, expr, "-", desc, ref, util=True)

    def cond(self, lhs: str, op: str, rhs: str, desc: str = "", ref: str = "",
             unit: str = "-", text_true: str = "", text_false: str = "") -> bool:
        ns = self.ns.numeric()
        a, b = E.evaluate(lhs, ns), E.evaluate(rhs, ns)
        ok = _OPS[op](a, b)
        self.steps.append(CondStep("cond", desc, ref, lhs=lhs, op=op, rhs=rhs, lhs_val=a,
                                   rhs_val=b, unit=unit, passed=ok,
                                   text_true=text_true, text_false=text_false))
        return ok

    def note(self, text: str, level: str = "info", ref: str = ""):
        self.steps.append(NoteStep("note", text, ref, level=level))

    def warn(self, text: str, ref: str = ""):
        self.note(text, "warn", ref)

    def value(self, name: str):
        return self.ns[name].value

    # ---------------------------------------------------------------- HTML
    def _leaf_symbol(self, name: str) -> str:
        v = self.ns.get(name)
        return v.sym if v else E.symbol_html(name)

    def _leaf_value(self, name: str) -> str:
        v = self.ns[name]
        if isinstance(v.value, str):
            return v.value
        val = from_internal(v.value, v.unit)
        s = self.fmt(val)
        u = unit_html(v.unit)
        s = f"{s} {u}" if u else s
        return f"({s})" if val < 0 else s

    def render_expr(self, expr: str, subst: bool = False) -> str:
        r = E.Renderer(self._leaf_value if subst else self._leaf_symbol, self.fmt,
                       paren_pow_names=subst)
        return r.render(E.parse(expr))

    def render_value(self, v: Var) -> str:
        if isinstance(v.value, str):
            return v.value
        u = unit_html(v.unit)
        s = self.fmt(from_internal(v.value, v.unit))
        return f"{s} {u}" if u else s

    def step_html(self, s: Step) -> dict:
        """Returnér en dict, som rapport-skabelonen kan rendere."""
        if isinstance(s, GivenStep):
            return {"kind": "given", "rows": [
                {"sym": v.sym, "value": self.render_value(v), "desc": v.desc, "ref": v.ref}
                for v in s.vars]}
        if isinstance(s, EqStep):
            parts = [s.var.sym, self.render_expr(s.expr)]
            if s.show_subst:
                parts.append(self.render_expr(s.expr, subst=True))
            parts.append(f"<b>{self.render_value(s.var)}</b>")
            # undgå "x = x" når udtrykket er et rent navn/tal
            if not s.show_subst and parts[1] == parts[0]:
                parts.pop(1)
            return {"kind": "eq", "html": " = ".join(parts), "desc": s.desc, "ref": s.ref,
                    "util": s.is_util, "value": s.var.value}
        if isinstance(s, CondStep):
            u = unit_html(s.unit)
            fa = self.fmt(from_internal(s.lhs_val, s.unit)) + (f" {u}" if u else "")
            fb = self.fmt(from_internal(s.rhs_val, s.unit)) + (f" {u}" if u else "")
            lhs, rhs = self.render_expr(s.lhs), self.render_expr(s.rhs)
            lhs_html = lhs if lhs == fa else f"{lhs} = {fa}"
            rhs_html = rhs if rhs == fb else f"{fb} = {rhs}"
            op = _OP_HTML[s.op] if s.passed else {"<=": "&gt;", "<": "≥", ">=": "&lt;", ">": "≤"}[s.op]
            return {"kind": "cond", "html": f"{lhs_html} {op} {rhs_html}", "desc": s.desc,
                    "ref": s.ref, "passed": s.passed,
                    "verdict": s.text_true if s.passed else s.text_false}
        if isinstance(s, NoteStep):
            return {"kind": "note", "html": s.desc, "level": s.level, "ref": s.ref}
        raise TypeError(s)

    def html_steps(self) -> list[dict]:
        return [self.step_html(s) for s in self.steps]
