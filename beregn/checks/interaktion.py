"""Bjælke-søjler: bøjning og tryk, EN 1993-1-1, 6.3.3 med k-faktorer efter bilag B.

Moment om stærk akse (M_z,Ed = 0). Formel (6.61) og (6.62).
"""
from .base import Check, Context, register, NA, UNSUPPORTED

AB = "EN 1993-1-1, bilag B"

# momentform -> C_m efter tabel B.3 (simpelt understøttet, M_h = 0 ved tværlast)
CM_PRESETS = {"jaevn": 0.95, "punkt_midt": 0.90, "konstant": 1.0}


def cm_default(lt) -> tuple[float, str]:
    if lt.momentform == "lineaer":
        return max(0.6 + 0.4 * lt.psi, 0.4), "lineær momentfordeling"
    return CM_PRESETS[lt.momentform], {"jaevn": "jævnt fordelt last", "punkt_midt": "punktlast",
                                        "konstant": "konstant moment"}[lt.momentform]


@register
class Interaktion(Check):
    key = "interaktion"
    title = "Bjælke-søjle: bøjning og tryk"
    clause = "EN 1993-1-1, 6.3.3"
    requires = ("klassifikation", "soejlefladning", "kipning")

    def run(self, ctx: Context):
        c = ctx.calc()
        m, lt = ctx.member, ctx.member.ltb
        if m.N_Ed <= 0 or m.M_Ed == 0:
            c.note("Elementet er ikke påvirket af både tryk og moment; 6.3.3 er ikke relevant.")
            return self.result(c, None, NA)
        kl = ctx.results["klasse"]
        if kl == 4 or ctx.results.get("klasse_N") == 4 or "chi_y" not in ctx.results:
            c.warn("Klasse 4-tværsnit er ikke understøttet.")
            return self.result(c, None, UNSUPPORTED)
        absM = "abs(M_Ed)" if m.M_Ed < 0 else "M_Ed"
        c.param("gamma_M1")

        c.note("Reduktionsfaktorer fra søjlefladning og kipning:")
        for n in ("lambda_bar_y", "lambda_bar_z", "chi_y", "chi_z"):
            c.use(n)
        c.use("chi_LT_mod", "Reduktionsfaktor for kipning")
        susceptible = not lt.fastholdt
        c.note("Valset I-profil uden vridningsfastholdelse: <b>vridningsblødt</b> element, tabel B.2."
               if susceptible else "Elementet er fastholdt mod vridning: <b>ikke vridningsblødt</b>, tabel B.1.",
               ref="EN 1993-1-1, 6.3.3(1)")

        c.eq("N_Rk", "A * f_y", "kN", "Karakteristisk normalkraftbæreevne", "EN 1993-1-1, tabel 6.7")
        if kl <= 2:
            c.eq("M_y_Rk", "W_pl_y * f_y", "kNm", f"Karakteristisk momentbæreevne (klasse {kl})",
                 "EN 1993-1-1, tabel 6.7")
        else:
            c.eq("M_y_Rk", "W_el_y * f_y", "kNm", "Karakteristisk momentbæreevne (klasse 3)",
                 "EN 1993-1-1, tabel 6.7")

        cm, form = cm_default(lt)
        c.given("C_my", lt.C_my if lt.C_my is not None else cm, desc=f"Ækvivalent momentfaktor ({form})",
                ref=f"{AB}, tabel B.3")
        c.eq("n_y", "N_Ed / (chi_y * N_Rk / gamma_M1)", desc="Udnyttelse for udknækning om y", ref=AB)
        if kl <= 2:
            c.eq("k_yy", "min(C_my * (1 + (lambda_bar_y - 0.2) * n_y), C_my * (1 + 0.8 * n_y))",
                 desc="Interaktionsfaktor", ref=f"{AB}, tabel B.1")
        else:
            c.eq("k_yy", "min(C_my * (1 + 0.6 * lambda_bar_y * n_y), C_my * (1 + 0.6 * n_y))",
                 desc="Interaktionsfaktor", ref=f"{AB}, tabel B.1")

        if not susceptible:
            c.eq("k_zy", "0.6 * k_yy" if kl <= 2 else "0.8 * k_yy", desc="Interaktionsfaktor",
                 ref=f"{AB}, tabel B.1")
        else:
            c.given("C_mLT", lt.C_mLT if lt.C_mLT is not None else cm,
                    desc=f"Ækvivalent momentfaktor for kipning ({form})", ref=f"{AB}, tabel B.3")
            c.eq("n_z", "N_Ed / (chi_z * N_Rk / gamma_M1)", desc="Udnyttelse for udknækning om z", ref=AB)
            ns = c.ns
            lam_z = ns["lambda_bar_z"].value
            if kl <= 2 and lam_z < 0.4:
                c.eq("k_zy", "min(0.6 + lambda_bar_z, 1 - 0.1 * lambda_bar_z * n_z / (C_mLT - 0.25))",
                     desc="Interaktionsfaktor (λ̄<sub>z</sub> &lt; 0,4)", ref=f"{AB}, tabel B.2")
            elif kl <= 2:
                c.eq("k_zy", "max(1 - 0.1 * lambda_bar_z * n_z / (C_mLT - 0.25), 1 - 0.1 * n_z / (C_mLT - 0.25))",
                     desc="Interaktionsfaktor", ref=f"{AB}, tabel B.2")
            else:
                c.eq("k_zy", "max(1 - 0.05 * lambda_bar_z * n_z / (C_mLT - 0.25), 1 - 0.05 * n_z / (C_mLT - 0.25))",
                     desc="Interaktionsfaktor", ref=f"{AB}, tabel B.2")

        u1 = c.util("eta_661", f"N_Ed / (chi_y * N_Rk / gamma_M1) + k_yy * {absM} / (chi_LT_mod * M_y_Rk / gamma_M1)",
                    desc="Interaktion, udknækning om y", ref="EN 1993-1-1, (6.61)")
        u2 = c.util("eta_662", f"N_Ed / (chi_z * N_Rk / gamma_M1) + k_zy * {absM} / (chi_LT_mod * M_y_Rk / gamma_M1)",
                    desc="Interaktion, udknækning om z", ref="EN 1993-1-1, (6.62)")
        return self.result(c, max(u1, u2), governing="formel (6.61)" if u1 >= u2 else "formel (6.62)")
