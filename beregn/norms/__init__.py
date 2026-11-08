"""Norm-laget: indlæser partialkoefficienter og NDP'er fra YAML-filer."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..core import expr as E

DATA_DIR = Path(__file__).parent / "data"


@dataclass
class Param:
    name: str
    value: Any
    unit: str = "-"
    desc: str = ""
    source: str = ""


@dataclass
class Norm:
    standard: str
    annex: str
    name: str
    status: str
    options: dict
    params: dict[str, Param] = field(default_factory=dict)
    tables: dict[str, dict] = field(default_factory=dict)
    used: dict[str, Param] = field(default_factory=dict)

    def param(self, name: str) -> Param:
        if name not in self.params:
            raise KeyError(f"Normparameter '{name}' findes ikke i {self.name}")
        p = self.params[name]
        self.used[name] = p
        return p

    def value(self, name: str):
        return self.param(name).value

    def table(self, name: str) -> dict:
        return self.tables[name]


def _read(standard: str, annex: str, search: list[Path]) -> dict:
    for d in search:
        f = d / standard / f"{annex}.yaml"
        if f.exists():
            return yaml.safe_load(f.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Fandt ikke norm-fil {standard}/{annex}.yaml i {search}")


def load_norm(standard: str = "EN1993-1-1", annex: str = "DK", options: dict | None = None,
              extra_dirs: list[str | Path] = ()) -> Norm:
    """Indlæs et nationalt anneks inkl. alt det arver fra."""
    search = [Path(p) for p in extra_dirs] + [DATA_DIR]
    chain, a = [], annex
    while a:
        d = _read(standard, a, search)
        chain.insert(0, d)
        a = d.get("arver")
    top = chain[-1]

    # valg (f.eks. kontrolklasse) med standardværdier
    opts: dict = {}
    for d in chain:
        for k, spec in (d.get("valg") or {}).items():
            opts[k] = spec.get("standard")
    opts.update(options or {})
    for d in chain:
        for k, spec in (d.get("valg") or {}).items():
            if spec.get("tilladte") and opts[k] not in spec["tilladte"]:
                raise ValueError(f"{k}={opts[k]!r} ikke tilladt; vælg en af {spec['tilladte']}")

    raw: dict[str, dict] = {}
    tables: dict[str, dict] = {}
    for d in chain:
        for k, spec in (d.get("parametre") or {}).items():
            raw[k] = spec if isinstance(spec, dict) else {"vaerdi": spec}
        for k, t in (d.get("tabeller") or {}).items():
            tables[k] = t

    params: dict[str, Param] = {}

    def resolve(k: str, stack=()):
        if k in params:
            return params[k].value
        if k in stack:
            raise ValueError(f"Cirkulær afhængighed i normparameter {k}")
        spec = raw[k]
        if "vaerdi" in spec:
            v = spec["vaerdi"]
        elif "afhaenger_af" in spec:
            v = spec["vaerdier"][opts[spec["afhaenger_af"]]]
        elif "udtryk" in spec:
            ns = {n: resolve(n, stack + (k,)) for n in E.names(spec["udtryk"]) if n in raw}
            v = E.evaluate(spec["udtryk"], ns)
        else:
            raise ValueError(f"Normparameter {k} mangler vaerdi/udtryk/afhaenger_af")
        if isinstance(v, float):
            v = round(v, 10)
        src = spec.get("kilde", "")
        if "afhaenger_af" in spec:
            src += f" ({spec['afhaenger_af']}: {opts[spec['afhaenger_af']]})"
        params[k] = Param(k, v, spec.get("enhed", "-"), spec.get("beskrivelse", ""), src)
        return v

    for k in raw:
        resolve(k)

    return Norm(standard, annex, top.get("navn", annex), top.get("status", ""), opts, params, tables)
