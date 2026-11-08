"""Kipning af bjælker, EN 1993-1-1, 6.3.2.

M_cr bestemmes med 3-faktor-formlen for dobbeltsymmetriske tværsnit
(NCCI SN003 / ECCS), da EN 1993-1-1 ikke selv angiver en formel.
"""
from .base import Check, Context, register, NA, UNSUPPORTED

NCCI = "NCCI SN003"

# momentform -> (C1, C2, k_c), simpelt understøttet bjælke, k = 1
PRESETS = {
    "jaevn": (1.127, 0.454, 0.94, "jævnt fordelt last"),
    "punkt_midt": (1.348, 0.630, 0.90, "punktlast midt på spændet"),
    "konstant": (1.0, 0.0, 1.0, "konstant moment"),
}


@register
class Kipning(Check):
    key = "kipning"
    title = "Kipning"
    clause = "EN 1993-1-1, 6.3.2"
    requires = ("klassifikation",)

    def run(self, ctx: Context):
        c = ctx.calc()
        m, lt, s = ctx.member, ctx.member.ltb, ctx.member.section
        if m.M_Ed == 0:
            c.note("Intet moment om stærk akse; kipning er ikke relevant.")
            return self.result(c, None, NA)
        if lt.fastholdt:
            c.note("Bjælken er angivet som fuldt fastholdt mod kipning; χ<sub>LT</sub> = 1.",
                   ref="EN 1993-1-1, 6.3.2.1")
            c.given("chi_LT_mod", 1.0, desc="Reduktionsfaktor for kipning", show=False)
            ctx.results["chi_LT"] = 1.0
            return self.result(c, None, NA)
        kl = ctx.results["klasse"]
        if kl == 4:
            return self.result(c, None, UNSUPPORTED)
        c.param("gamma_M1")
        absM = "abs(M_Ed)" if m.M_Ed < 0 else "M_Ed"

        # --- kritisk moment
        if lt.momentform == "lineaer":
            psi = lt.psi
            C1d, C2d, kcd = min(1.88 - 1.40 * psi + 0.52 * psi ** 2, 2.70), 0.0, 1 / (1.33 - 0.33 * psi)
            form = f"lineær momentfordeling, ψ = {ctx.fmt(psi)}"
        else:
            C1d, C2d, kcd, form = PRESETS[lt.momentform]
        c.note(f"Momentform: {form}.")
        zg = {"overflange": s.h / 2, "forskydningscenter": 0.0, "underflange": -s.h / 2}[lt.lastplacering]
        c.given("L_LT", lt.L or m.L, "m", "Kiplængde (afstand mellem kipafstivninger)")
        c.given("C_1", lt.C1 if lt.C1 is not None else C1d, desc="Momentfaktor", ref=NCCI)
        c.given("C_2", lt.C2 if lt.C2 is not None else C2d, desc="Faktor for lastplacering", ref=NCCI)
        c.given("z_g", zg, "mm", f"Lastangrebspunkt over forskydningscenter ({lt.lastplacering})", NCCI)
        c.given("k", lt.k, desc="Effektiv-længdefaktor, sideudbøjning", ref=NCCI)
        c.given("k_w", lt.k_w, desc="Effektiv-længdefaktor, hvælving", ref=NCCI)
        c.eq("M_cr", "C_1 * pi**2 * E * I_z / (k * L_LT)**2 * (sqrt((k / k_w)**2 * (I_w / I_z)"
                     " + (k * L_LT)**2 * G * I_t / (pi**2 * E * I_z) + (C_2 * z_g)**2) - C_2 * z_g)",
             "kNm", "Elastisk kritisk kipmoment", NCCI)

        # --- slankhed
        if kl <= 2:
            c.eq("W_y", "W_pl_y", "cm3", f"Modstandsmoment (klasse {kl})", "EN 1993-1-1, 6.3.2.2(1)")
        else:
            c.eq("W_y", "W_el_y", "cm3", "Modstandsmoment (klasse 3)", "EN 1993-1-1, 6.3.2.2(1)")
        lam = c.eq("lambda_bar_LT", "sqrt(W_y * f_y / M_cr)", desc="Relativt slankhedsforhold",
                   ref="EN 1993-1-1, 6.3.2.2(1)")

        # --- reduktionsfaktor
        method = ctx.norm.value("kip_metode")
        rolled = method == "valsede"
        tab = ctx.norm.table("kipkurve_valsede" if rolled else "kipkurve_generel")
        hb = s.h / s.b
        curve = next(r["kurve"] for r in tab["graenser"] if hb <= r["h_b_max"])
        imp = ctx.norm.table("imperfektionsfaktor")
        if rolled:
            c.note("Metode for valsede profiler og tilsvarende svejste profiler.",
                   ref="EN 1993-1-1, 6.3.2.3")
            c.param("lambda_bar_LT_0", "beta_LT")
        else:
            c.note("Generel metode.", ref="EN 1993-1-1, 6.3.2.2")
            c.given("lambda_bar_LT_0", 0.2, ref="EN 1993-1-1, 6.3.2.2(1)")
            c.given("beta_LT", 1.0, ref="EN 1993-1-1, 6.3.2.2(1)")
        c.given("alpha_LT", imp[curve], desc=f"Imperfektionsfaktor, kipkurve {curve} (h/b = {ctx.fmt(hb)})",
                ref=f"{tab['kilde']} / tabel 6.3")

        if lam <= c.value("lambda_bar_LT_0"):
            c.note("λ̄<sub>LT</sub> ≤ λ̄<sub>LT,0</sub>: kipning kan ses bort fra.",
                   ref="EN 1993-1-1, 6.3.2.2(4) / 6.3.2.3(1)")
            c.given("chi_LT_mod", 1.0, desc="Reduktionsfaktor for kipning")
        else:
            c.eq("Phi_LT", "0.5 * (1 + alpha_LT * (lambda_bar_LT - lambda_bar_LT_0) + beta_LT * lambda_bar_LT**2)",
                 ref="EN 1993-1-1, 6.3.2.3(1)" if rolled else "EN 1993-1-1, 6.3.2.2(1)")
            if rolled:
                c.eq("chi_LT", "min(1, 1 / (Phi_LT + sqrt(Phi_LT**2 - beta_LT * lambda_bar_LT**2)), "
                               "1 / lambda_bar_LT**2)", desc="Reduktionsfaktor", ref="EN 1993-1-1, (6.57)")
            else:
                c.eq("chi_LT", "min(1, 1 / (Phi_LT + sqrt(Phi_LT**2 - lambda_bar_LT**2)))",
                     desc="Reduktionsfaktor", ref="EN 1993-1-1, (6.56)")
            if rolled and ctx.norm.value("kip_f_faktor"):
                c.given("k_c", lt.k_c if lt.k_c is not None else kcd, desc="Korrektionsfaktor for momentform",
                        ref="EN 1993-1-1, tabel 6.6")
                c.eq("f", "min(1, 1 - 0.5 * (1 - k_c) * (1 - 2 * (lambda_bar_LT - 0.8)**2))",
                     desc="Modifikationsfaktor", ref="EN 1993-1-1, (6.58)")
                c.eq("chi_LT_mod", "min(1, chi_LT / f, 1 / lambda_bar_LT**2)", desc="Modificeret reduktionsfaktor",
                     ref="EN 1993-1-1, (6.58)")
            else:
                c.eq("chi_LT_mod", "chi_LT", desc="Reduktionsfaktor")
        c.eq("M_b_Rd", "chi_LT_mod * W_y * f_y / gamma_M1", "kNm", "Kipningsbæreevne", "EN 1993-1-1, (6.55)")
        u = c.util("eta_LT", f"{absM} / M_b_Rd", ref="EN 1993-1-1, (6.54)")
        ctx.results["chi_LT"] = c.value("chi_LT_mod")
        return self.result(c, u, governing="M_Ed / M_b_Rd")
