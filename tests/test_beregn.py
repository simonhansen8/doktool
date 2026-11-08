"""Tests: profilkonstanter mod producenttabeller og eftervisninger mod uafhængig håndregning."""
import math

import pytest

from beregn import sections
from beregn.checks import LTBInput, Member
from beregn.core.units import NumberFormat, parse_quantity
from beregn.engine import run_member
from beregn.norms import load_norm

FMT = NumberFormat()

# (profil, egenskab, tabelværdi i mm-enheder) – ArcelorMittal-tabeller
TABLE = [
    ("IPE 300", "A", 53.81e2), ("IPE 300", "I_y", 8356e4), ("IPE 300", "W_pl_y", 628.4e3),
    ("IPE 300", "I_z", 603.8e4), ("IPE 300", "I_w", 125.9e9), ("IPE 300", "I_t", 20.12e4),
    ("HEB 200", "A", 78.08e2), ("HEB 200", "I_y", 5696e4), ("HEB 200", "W_pl_y", 642.5e3),
    ("HEB 200", "I_z", 2003e4), ("HEB 200", "I_t", 59.28e4), ("HEB 200", "I_w", 171.1e9),
    ("HEA 200", "A", 53.83e2), ("HEA 200", "I_y", 3692e4), ("HEA 200", "W_pl_y", 429.5e3),
    ("IPE 600", "I_y", 92080e4), ("IPE 600", "W_pl_y", 3512e3),
]


@pytest.mark.parametrize("name,prop,ref", TABLE)
def test_profile_properties(name, prop, ref):
    assert sections.get(name).props[prop] == pytest.approx(ref, rel=0.012)


def test_parse_quantity():
    assert parse_quantity("6,0 m") == 6000
    assert parse_quantity("120 kNm") == 120e6
    assert parse_quantity(85, "kN") == 85e3


def test_dk_partial_factors():
    n = load_norm(annex="DK")
    assert (n.value("gamma_M0"), n.value("gamma_M1")) == (1.10, 1.20)
    n = load_norm(annex="DK", options={"kontrolklasse": "lempet"})
    assert n.value("gamma_M0") == pytest.approx(1.21)
    n = load_norm(annex="anbefalet")
    assert n.value("gamma_M0") == 1.0


def _run(member, annex="DK"):
    mr = run_member(member, load_norm(annex=annex), FMT)
    return {r.key: r for r in mr.results}


def test_bending_ipe300_dk():
    m = Member("B", sections.get("IPE 300"), "S355", 6000, M_Ed=120e6, checks=["boejning"])
    r = _run(m)["boejning"]
    Mrd = 628.4e3 * 355 / 1.10                    # fy = 355 for tf = 10,7 mm
    assert r.utilisation == pytest.approx(120e6 / Mrd, rel=2e-3)


def test_fy_thickness_dk_vs_recommended():
    # HEB 300: tf = 19 mm -> produktstandard 345 MPa (DK), tabel 3.1 355 MPa (anbefalet)
    m = Member("B", sections.get("HEB 300"), "S355", 6000, M_Ed=300e6, checks=["boejning"])
    dk = _run(m)["boejning"].calc.ns["f_y"].value
    rec = _run(m, "anbefalet")["boejning"].calc.ns["f_y"].value
    assert (dk, rec) == (345, 355)


def test_shear_ipe300():
    s = sections.get("IPE 300")
    m = Member("B", s, "S355", 6000, V_Ed=200e3, checks=["forskydning"])
    Av = max(s.A - 2 * s.b * s.tf + (s.tw + 2 * s.r) * s.tf, 1.2 * s.h_w * s.tw)
    assert _run(m)["forskydning"].utilisation == pytest.approx(200e3 / (Av * 355 / math.sqrt(3) / 1.1), rel=1e-6)


def _chi(lam, alpha):
    phi = 0.5 * (1 + alpha * (lam - 0.2) + lam ** 2)
    return min(1, 1 / (phi + math.sqrt(phi ** 2 - lam ** 2)))


def test_flexural_buckling_heb200():
    s = sections.get("HEB 200")
    m = Member("S", s, "S355", 4000, N_Ed=900e3, checks=["soejlefladning"])
    E = 210000
    lam_z = math.sqrt(s.A * 355 / (math.pi ** 2 * E * s.I_z / 4000 ** 2))
    Nb = _chi(lam_z, 0.49) * s.A * 355 / 1.20        # h/b = 1,0 -> kurve c om z
    assert _run(m)["soejlefladning"].utilisation == pytest.approx(900e3 / Nb, rel=1e-6)


def test_ltb_ipe300_hand_calc():
    s = sections.get("IPE 300")
    m = Member("B", s, "S355", 6000, M_Ed=60e6, ltb=LTBInput(momentform="jaevn", lastplacering="overflange"),
               checks=["kipning"])
    E, G, L, C1, C2, zg = 210000, 81000, 6000, 1.127, 0.454, s.h / 2
    Mcr = C1 * math.pi ** 2 * E * s.I_z / L ** 2 * (math.sqrt(s.I_w / s.I_z + L ** 2 * G * s.I_t /
                                                            (math.pi ** 2 * E * s.I_z) + (C2 * zg) ** 2) - C2 * zg)
    assert Mcr == pytest.approx(78.4e6, rel=0.01)   # kontrolleret i hånden
    lam = math.sqrt(s.W_pl_y * 355 / Mcr)
    phi = 0.5 * (1 + 0.34 * (lam - 0.4) + 0.75 * lam ** 2)  # h/b = 2,0 -> kurve b (tabel 6.5)
    chi = min(1, 1 / (phi + math.sqrt(phi ** 2 - 0.75 * lam ** 2)), 1 / lam ** 2)
    f = min(1, 1 - 0.5 * (1 - 0.94) * (1 - 2 * (lam - 0.8) ** 2))
    chi_mod = min(1, chi / f, 1 / lam ** 2)
    Mb = chi_mod * s.W_pl_y * 355 / 1.20
    assert _run(m)["kipning"].utilisation == pytest.approx(60e6 / Mb, rel=1e-6)


def test_combined_reduction_with_axial():
    s = sections.get("HEB 200")
    m = Member("S", s, "S355", 4000, N_Ed=900e3, M_Ed=40e6, checks=["kombineret"])
    Npl = s.A * 355 / 1.1
    n, a = 900e3 / Npl, min((s.A - 2 * s.b * s.tf) / s.A, 0.5)
    MN = min(s.W_pl_y * 355 / 1.1 * (1 - n) / (1 - 0.5 * a), s.W_pl_y * 355 / 1.1)
    assert _run(m)["kombineret"].utilisation == pytest.approx(max(n, 40e6 / MN), rel=1e-6)


def test_classification_class3_web_in_compression():
    # IPE 600 i rent tryk, S355: c/t > 42 eps -> klasse 4 -> ikke understøttet
    m = Member("S", sections.get("IPE 600"), "S355", 3000, N_Ed=500e3, checks=["klassifikation"])
    r = _run(m)["klassifikation"]
    assert r.status == "Ikke understøttet"


def test_report_renders():
    from beregn.io.yaml_input import load_project
    from beregn.engine import run_project
    from beregn.report.html import render_html
    p = load_project("eksempler/eksempel_hal.yaml")
    html = render_html(p, run_project(p))
    assert "Kipning" in html and "<sub>b,Rd</sub>" in html
