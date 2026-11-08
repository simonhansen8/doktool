"""Tværsnit påvirket af moment, normalkraft og forskydning (stærk akse).

EN 1993-1-1, 6.2.8 (M + V), 6.2.9 (M + N) og 6.2.10 (M + V + N).
"""
from .base import Check, Context, register, UNSUPPORTED


@register
class Kombineret(Check):
    key = "kombineret"
    title = "Moment, normalkraft og forskydning, tværsnit"
    clause = "EN 1993-1-1, 6.2.8–6.2.10"
    requires = ("klassifikation",)

    def run(self, ctx: Context):
        c = ctx.calc()
        m = ctx.member
        kl = ctx.results["klasse"]
        if kl == 4:
            c.warn("Klasse 4-tværsnit er ikke understøttet.")
            return self.result(c, None, UNSUPPORTED)
        c.param("gamma_M0", "eta")
        absN = "abs(N_Ed)" if m.N_Ed < 0 else "N_Ed"
        absM = "abs(M_Ed)" if m.M_Ed < 0 else "M_Ed"
        absV = "abs(V_Ed)" if m.V_Ed < 0 else "V_Ed"

        # forskydningens indflydelse
        c.eq("A_v", "max(A - 2 * b * t_f + (t_w + 2 * r) * t_f, eta * h_w * t_w)", "cm2",
             "Forskydningsareal", "EN 1993-1-1, 6.2.6(3)a")
        c.eq("V_pl_Rd", "A_v * (f_y / sqrt(3)) / gamma_M0", "kN", "Plastisk forskydningsbæreevne",
             "EN 1993-1-1, (6.18)")
        if c.cond(absV, "<=", "0.5 * V_pl_Rd", "Forskydningens indflydelse", "EN 1993-1-1, 6.2.8(2)",
                  unit="kN", text_true="ingen reduktion for forskydning",
                  text_false="reduktion for forskydning"):
            c.given("rho", 0.0, desc="Reduktionsfaktor for forskydning")
        else:
            c.eq("rho", f"(2 * {absV} / V_pl_Rd - 1)**2", desc="Reduktionsfaktor for forskydning",
                 ref="EN 1993-1-1, 6.2.8(3)")
        c.eq("A_w", "h_w * t_w", "cm2", "Kropsareal", "EN 1993-1-1, 6.2.8(5)")

        if kl <= 2:
            return self._plastic(c, absN, absM)
        return self._elastic(c, absN, absM)

    def _plastic(self, c, absN, absM):
        c.note("Klasse 1 eller 2: plastisk interaktion.")
        c.eq("N_pl_Rd", "(A - rho * A_w) * f_y / gamma_M0", "kN",
             "Plastisk normalkraftbæreevne (reduceret flydespænding i kroppen ved forskydning)",
             "EN 1993-1-1, (6.6) og 6.2.10(3)")
        c.eq("M_pl_y_V_Rd", "(W_pl_y - rho * A_w**2 / (4 * t_w)) * f_y / gamma_M0", "kNm",
             "Plastisk momentbæreevne inkl. forskydning", "EN 1993-1-1, (6.30)")
        c.eq("n", f"{absN} / N_pl_Rd", desc="Normalkraftforhold", ref="EN 1993-1-1, 6.2.9.1(5)")
        c.eq("a", "min((A - 2 * b * t_f) / A, 0.5)", desc="Kropsandel", ref="EN 1993-1-1, 6.2.9.1(5)")
        lim1 = c.cond(absN, "<=", "0.25 * N_pl_Rd", "Normalkraftens indflydelse", "EN 1993-1-1, (6.33)",
                      unit="kN")
        lim2 = c.cond(absN, "<=", "0.5 * h_w * t_w * f_y / gamma_M0", "", "EN 1993-1-1, (6.34)", unit="kN")
        if lim1 and lim2:
            c.note("Begge betingelser er opfyldt: normalkraften reducerer ikke momentbæreevnen.",
                   ref="6.2.9.1(4)")
            c.eq("M_N_y_Rd", "M_pl_y_V_Rd", "kNm", "Reduceret momentbæreevne")
        else:
            c.eq("M_N_y_Rd", "min(M_pl_y_V_Rd * (1 - n) / (1 - 0.5 * a), M_pl_y_V_Rd)", "kNm",
                 "Reduceret momentbæreevne", "EN 1993-1-1, (6.36)")
        u1 = c.util("eta_N", f"{absN} / N_pl_Rd", ref="EN 1993-1-1, (6.9)")
        u2 = c.util("eta_MN", f"{absM} / M_N_y_Rd", ref="EN 1993-1-1, (6.31)")
        gov = "N_Ed / N_pl_Rd" if u1 > u2 else "M_Ed / M_N_y_Rd"
        return self.result(c, max(u1, u2), governing=gov)

    def _elastic(self, c, absN, absM):
        c.note("Klasse 3: elastisk spændingskontrol.")
        if c.ns["rho"].value > 0:
            c.warn("V<sub>Ed</sub> &gt; 0,5 V<sub>pl,Rd</sub> for klasse 3: kombination med forskydning "
                   "skal eftervises efter 6.2.1(5) og er ikke med i denne version.")
        c.eq("sigma_x_Ed", f"{absN} / A + {absM} / W_el_y", "MPa", "Største normalspænding",
             "EN 1993-1-1, 6.2.9.2(1)")
        c.eq("f_y_d", "f_y / gamma_M0", "MPa", "Regningsmæssig flydespænding")
        u = c.util("eta_sigma", "sigma_x_Ed / f_y_d", ref="EN 1993-1-1, (6.42)")
        return self.result(c, u, governing="sigma_x_Ed / f_y_d")
