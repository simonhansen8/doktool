"""Fladning af centralt trykkede elementer, EN 1993-1-1, 6.3.1."""
from .base import Check, Context, register, NA, UNSUPPORTED


def curve_rolled_I(h, b, tf, grade):
    """Tabel 6.2, valsede I-profiler. Returnerer (kurve_y, kurve_z)."""
    hi = grade.upper().startswith("S460")
    if h / b > 1.2:
        if tf <= 40:
            return ("a0", "a0") if hi else ("a", "b")
        return ("a", "a") if hi else ("b", "c")
    if tf <= 100:
        return ("a", "a") if hi else ("b", "c")
    return ("c", "c") if hi else ("d", "d")


@register
class Soejlefladning(Check):
    key = "soejlefladning"
    title = "Søjlefladning (bøjningsudknækning)"
    clause = "EN 1993-1-1, 6.3.1"
    requires = ("klassifikation",)

    def run(self, ctx: Context):
        c = ctx.calc()
        m = ctx.member
        if m.N_Ed <= 0:
            c.note("Elementet er ikke trykpåvirket; søjlefladning er ikke relevant.")
            return self.result(c, None, NA)
        if ctx.results["klasse_N"] == 4:
            c.warn("Klasse 4 for rent tryk er ikke understøttet (kræver A<sub>eff</sub>).")
            return self.result(c, None, UNSUPPORTED)
        c.param("gamma_M1")
        s = m.section
        cy, cz = curve_rolled_I(s.h, s.b, s.tf, m.grade)
        imp = ctx.norm.table("imperfektionsfaktor")
        c.note(f"Valset I-profil, h/b = {ctx.fmt(s.h / s.b)}, t<sub>f</sub> = {ctx.fmt(s.tf)} mm",
               ref="EN 1993-1-1, tabel 6.2")
        utils = {}
        for ax, L, curve in (("y", m.L_cr_y or m.L, cy), ("z", m.L_cr_z or m.L, cz)):
            c.note(f"<b>Udknækning om {ax}-aksen</b>")
            c.given(f"L_cr_{ax}", L, "m", "Knæklængde")
            c.given(f"alpha_{ax}", imp[curve], desc=f"Imperfektionsfaktor, kurve {curve}",
                    ref="EN 1993-1-1, tabel 6.2 og 6.1")
            c.eq(f"N_cr_{ax}", f"pi**2 * E * I_{ax} / L_cr_{ax}**2", "kN", "Kritisk normalkraft")
            lam = c.eq(f"lambda_bar_{ax}", f"sqrt(A * f_y / N_cr_{ax})", desc="Relativt slankhedsforhold",
                       ref="EN 1993-1-1, (6.50)")
            if lam <= 0.2:
                c.note("λ̄ ≤ 0,2: fladning kan ses bort fra.", ref="EN 1993-1-1, 6.3.1.2(4)")
                c.given(f"chi_{ax}", 1.0, desc="Reduktionsfaktor")
            else:
                c.eq(f"Phi_{ax}", f"0.5 * (1 + alpha_{ax} * (lambda_bar_{ax} - 0.2) + lambda_bar_{ax}**2)",
                     ref="EN 1993-1-1, 6.3.1.2(1)")
                c.eq(f"chi_{ax}", f"min(1, 1 / (Phi_{ax} + sqrt(Phi_{ax}**2 - lambda_bar_{ax}**2)))",
                     desc="Reduktionsfaktor", ref="EN 1993-1-1, (6.49)")
            c.eq(f"N_b_{ax}_Rd", f"chi_{ax} * A * f_y / gamma_M1", "kN", "Fladningsbæreevne",
                 "EN 1993-1-1, (6.47)")
            utils[ax] = c.util(f"eta_N_{ax}", f"N_Ed / N_b_{ax}_Rd", ref="EN 1993-1-1, (6.46)")
            ctx.results[f"chi_{ax}"] = c.value(f"chi_{ax}")
        if m.M_Ed != 0 and "interaktion" not in ctx.results.get("planlagt", []):
            c.warn("<b>Bemærk:</b> Elementet har både tryk og moment. Stabilitetsinteraktion efter "
                   "6.3.3 (formel 6.61/6.62) skal også eftervises. Tilføj eftervisningen 'interaktion'.",
                   ref="EN 1993-1-1, 6.3.3")
            ctx.results.setdefault("mangler", []).append("6.3.3")
        ax = max(utils, key=utils.get)
        return self.result(c, utils[ax], governing=f"N_Ed / N_b_{ax}_Rd")
