"""Forskydning, EN 1993-1-1, 6.2.6."""
from .base import Check, Context, register


@register
class Forskydning(Check):
    key = "forskydning"
    title = "Forskydning, tværsnit"
    clause = "EN 1993-1-1, 6.2.6"

    def run(self, ctx: Context):
        c = ctx.calc()
        c.param("gamma_M0", "eta")
        c.eq("A_v", "max(A - 2 * b * t_f + (t_w + 2 * r) * t_f, eta * h_w * t_w)", "cm2",
             "Forskydningsareal, valsede I-profiler", "EN 1993-1-1, 6.2.6(3)a")
        c.eq("V_pl_Rd", "A_v * (f_y / sqrt(3)) / gamma_M0", "kN", "Plastisk forskydningsbæreevne",
             "EN 1993-1-1, (6.18)")
        if "epsilon" not in c.ns:
            c.eq("epsilon", "sqrt(235 / f_y)", ref="EN 1993-1-1, tabel 5.2")
        if not c.cond("h_w / t_w", "<=", "72 * epsilon / eta", "Kontrol af forskydningsbuling",
                      "EN 1993-1-1, 6.2.6(6)", text_true="forskydningsbuling skal ikke eftervises",
                      text_false="forskydningsbuling skal eftervises"):
            c.warn("Forskydningsbuling efter EN 1993-1-5 er ikke med i denne version.")
        u = c.util("eta_V", "abs(V_Ed) / V_pl_Rd" if ctx.member.V_Ed < 0 else "V_Ed / V_pl_Rd",
                   ref="EN 1993-1-1, (6.17)")
        ctx.results["V_pl_Rd"] = c.value("V_pl_Rd")
        return self.result(c, u, governing="V_Ed / V_pl_Rd")
