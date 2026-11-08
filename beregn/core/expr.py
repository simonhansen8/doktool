"""Formeludtryk: sikker evaluering og rendering til HTML.

Et udtryk skrives som almindelig Python-syntaks, f.eks.

    "W_pl_y * f_y / gamma_M0"

og kan så både
  * evalueres numerisk (kun aritmetik og et lille sæt funktioner er tilladt),
  * renderes symbolsk:      W_pl,y · f_y / γ_M0  (med brøkstreg, sænket skrift osv.)
  * renderes med indsatte værdier: 628,4·10³ mm³ · 355 MPa / 1,10

Navnekonvention for symboler:
  første led er grundsymbolet, resten bliver sænket skrift adskilt af komma.
  Græske navne oversættes (gamma -> γ, chi -> χ, lambda -> λ ...).
  Leddet "bar" giver en streg over grundsymbolet (lambda_bar_LT -> λ̄_LT).
"""
from __future__ import annotations

import ast
import math
from typing import Callable

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "eta": "η", "theta": "θ", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "phi": "φ", "chi": "χ",
    "psi": "ψ", "omega": "ω", "xi": "ξ", "zeta": "ζ",
    "Phi": "Φ", "Delta": "Δ", "Sigma": "Σ", "Psi": "Ψ", "Omega": "Ω", "Lambda": "Λ",
}

FUNCS: dict[str, Callable] = {
    "sqrt": math.sqrt, "min": min, "max": max, "abs": abs,
    "log": math.log, "exp": math.exp, "sin": math.sin, "cos": math.cos, "tan": math.tan,
}
CONSTS = {"pi": math.pi}


def symbol_html(name: str) -> str:
    """Oversæt et variabelnavn til HTML-symbol."""
    parts = name.split("_")
    base, rest = parts[0], parts[1:]
    bar = "bar" in rest
    rest = [p for p in rest if p != "bar"]
    base_html = GREEK.get(base, base)
    if bar:
        base_html = f'<span class="bar">{base_html}</span>'
    if rest:
        sub = ",".join(GREEK.get(p, p) for p in rest)
        return f'<span class="sym"><i>{base_html}</i><sub>{sub}</sub></span>'
    return f'<span class="sym"><i>{base_html}</i></span>'


def symbol_text(name: str) -> str:
    """Ren tekst-version (til logs, tabeller uden HTML)."""
    parts = name.split("_")
    base, rest = parts[0], [p for p in parts[1:] if p != "bar"]
    b = GREEK.get(base, base) + ("\u0304" if "bar" in parts[1:] else "")
    return b + ("_" + ",".join(GREEK.get(p, p) for p in rest) if rest else "")


# ---------------------------------------------------------------- evaluering
_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a ** b,
}


def parse(expr: str) -> ast.AST:
    return ast.parse(expr, mode="eval").body


def evaluate(node: ast.AST | str, ns: dict[str, float]) -> float:
    if isinstance(node, str):
        node = parse(node)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in ns:
            return ns[node.id]
        if node.id in CONSTS:
            return CONSTS[node.id]
        raise NameError(f"Ukendt variabel i formel: {node.id}")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](evaluate(node.left, ns), evaluate(node.right, ns))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -evaluate(node.operand, ns)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS:
        return FUNCS[node.func.id](*[evaluate(a, ns) for a in node.args])
    raise ValueError(f"Ikke tilladt i formel: {ast.dump(node)}")


def names(node: ast.AST | str) -> list[str]:
    if isinstance(node, str):
        node = parse(node)
    return [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]


# ---------------------------------------------------------------- rendering
_PREC = {ast.Add: 1, ast.Sub: 1, ast.Mult: 2, ast.Div: 2, ast.Pow: 4}


def _prec(node: ast.AST) -> int:
    if isinstance(node, ast.BinOp):
        return _PREC[type(node.op)]
    if isinstance(node, ast.UnaryOp):
        return 3
    return 9


class Renderer:
    """Renderer et AST til HTML. `leaf` bestemmer hvordan et navn vises."""

    def __init__(self, leaf: Callable[[str], str], number: Callable[[float], str],
                 paren_pow_names: bool = False):
        self.leaf = leaf
        self.number = number
        self.paren_pow_names = paren_pow_names

    def paren(self, html: str) -> str:
        return f'<span class="paren">(</span>{html}<span class="paren">)</span>'

    def render(self, node: ast.AST, parent_prec: int = 0) -> str:
        html = self._render(node)
        return self.paren(html) if _prec(node) < parent_prec else html

    def _render(self, node: ast.AST) -> str:
        if isinstance(node, ast.Constant):
            return self.number(node.value)
        if isinstance(node, ast.Name):
            if node.id == "pi":
                return "π"
            return self.leaf(node.id)
        if isinstance(node, ast.UnaryOp):
            return "−" + self.render(node.operand, 3)
        if isinstance(node, ast.BinOp):
            op = type(node.op)
            if op is ast.Div:
                return (f'<span class="frac"><span class="num">{self.render(node.left)}</span>'
                        f'<span class="den">{self.render(node.right)}</span></span>')
            if op is ast.Pow:
                base = self.render(node.left, 5)
                if self.paren_pow_names and isinstance(node.left, ast.Name) and node.left.id != "pi":
                    base = self.paren(base)
                return f"{base}<sup>{self.render(node.right)}</sup>"
            sym = {ast.Add: " + ", ast.Sub: " − ", ast.Mult: " · "}[op]
            left = self.render(node.left, _PREC[op])
            rnode = node.right
            # a - (b + c) og a / (b*c) kræver parentes på højre side
            rp = _prec(rnode)
            right = self._render(rnode)
            if rp < _PREC[op] or (op is ast.Sub and rp == 1):
                right = self.paren(right)
            return left + sym + right
        if isinstance(node, ast.Call):
            fn = node.func.id
            args = [self.render(a) for a in node.args]
            if fn == "sqrt":
                # overstreg kun over simple udtryk; ellers √( ... ) som er mere læsbart med brøker
                complex_ = any((isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)) or isinstance(n, ast.Call)
                               for n in ast.walk(node.args[0]))
                if not complex_:
                    return f'<span class="sqrt"><span class="rad">√</span><span class="radicand">{args[0]}</span></span>'
                return f'<span class="rad">√</span>' + self.paren(args[0])
            if fn == "abs":
                return f"|{args[0]}|"
            return f"{fn}" + self.paren("; ".join(args))
        raise ValueError(f"Kan ikke rendere {ast.dump(node)}")
