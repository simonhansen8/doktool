"""Indlæsning fra Excel.

Ark 'Projekt': to kolonner (felt, værdi), inkl. nationalt_anneks og kontrolklasse.
Ark 'Elementer': én række pr. element. Kolonneoverskrifter kan have enhed i
klammer, f.eks. 'M_Ed [kNm]'. Rene tal tolkes i den enhed, der står i overskriften.
"""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook

from ..engine import Project
from .yaml_input import project_from_dict

_HDR = re.compile(r"^\s*([^\[]+?)\s*(?:\[(.+)\])?\s*$")
FORCES = ("N_Ed", "V_Ed", "M_Ed")
KIP = {"kip_laengde": "laengde", "momentform": "momentform", "psi": "psi", "lastplacering": "lastplacering",
       "C1": "C1", "C2": "C2", "k_c": "k_c",
       "fastholdt": "fastholdt", "C_my": "C_my", "C_mLT": "C_mLT"}
NORM_KEYS = ("standard", "nationalt_anneks", "kontrolklasse")


def _val(v, unit):
    if v is None or v == "":
        return None
    if unit and isinstance(v, (int, float)):
        return f"{v} {unit}"
    return v


def project_dict_from_excel(path: str | Path) -> dict:
    wb = load_workbook(path, data_only=True)
    info, norm = {}, {}
    if "Projekt" in wb.sheetnames:
        for row in wb["Projekt"].iter_rows(min_row=1, values_only=True):
            if row and row[0]:
                (norm if row[0] in NORM_KEYS else info)[str(row[0]).strip()] = row[1]
    ws = wb["Elementer"]
    rows = list(ws.iter_rows(values_only=True))
    heads = [_HDR.match(str(h)).groups() if h else (None, None) for h in rows[0]]
    elements = []
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        e: dict = {"snitkraefter": {}, "kipning": {}}
        for (key, unit), v in zip(heads, row):
            v = _val(v, unit)
            if key is None or v is None:
                continue
            if key in FORCES:
                e["snitkraefter"][key] = v
            elif key in KIP:
                e["kipning"][KIP[key]] = v
            elif key == "eftervisninger":
                e[key] = [s.strip() for s in str(v).split(",") if s.strip()]
            else:
                e[key] = v
        elements.append(e)
    return {"projekt": info, "norm": norm, "elementer": elements}


def load_project_excel(path: str | Path, norm_dirs=()) -> Project:
    return project_from_dict(project_dict_from_excel(path), norm_dirs)
