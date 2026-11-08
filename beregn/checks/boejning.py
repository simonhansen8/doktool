"""Bøjning om stærk akse, EN 1993-1-1, 6.2.5."""
from .base import Check, Context, register, UNSUPPORTED


@register
class Boejning(Check):
    key = "boejning"
    title = "Bøjningsmoment, tværsnit"
    clause = "EN 1993-1-1, 6.2.5"
    requires = ("klassifikation",)

    def run(self, ctx: Context):
        c = ctx.calc()
        kl = ctx.results["klasse"]
        if kl == 4:
            c.warn("Klasse 4-tværsnit er ikke understøttet.")
            return self.result(c, None, UNSUPPORTED)
        c.param("gamma_M0")
        if kl <= 2:
            c.note(f"Klasse {kl}: plastisk modstandsmoment anvendes.", ref="6.2.5(2), (6.13)")
            c.eq("W_y", "W_pl_y", "cm3", "Modstandsmoment")
            ref = "EN 1993-1-1, (6.13)"
        else:
            c.note("Klasse 3: elastisk modstandsmoment anvendes.", ref="6.2.5(2), (6.14)")
            c.eq("W_y", "W_el_y", "cm3", "Modstandsmoment")
            ref = "EN 1993-1-1, (6.14)"
        c.eq("M_c_Rd", "W_y * f_y / gamma_M0", "kNm", "Momentbæreevne", ref)
        u = c.util("eta_M", "abs(M_Ed) / M_c_Rd" if ctx.member.M_Ed < 0 else "M_Ed / M_c_Rd",
                   ref="EN 1993-1-1, (6.12)")
        return self.result(c, u, governing="M_Ed / M_c_Rd")
