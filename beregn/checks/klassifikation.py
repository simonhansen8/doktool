"""Tværsnitsklassifikation, EN 1993-1-1 afsnit 5.5 og tabel 5.2."""
from .base import Check, Context, register, OK, UNSUPPORTED

T52 = "EN 1993-1-1, tabel 5.2"


def _ladder(c, lhs, limits, part):
    """Gå klassegrænserne igennem indtil én er opfyldt. Returnerer klassen."""
    for cls, rhs in enumerate(limits, start=1):
        if c.cond(lhs, "<=", rhs, ref=T52, text_true=f"{part}: klasse {cls}",
                  text_false=f"ikke klasse {cls}"):
            return cls
    return 4


def web_class(c, compression_only: bool = False) -> int:
    m = c.ns
    N, M = m["N_Ed"].value, m["M_Ed"].value
    if compression_only or (N > 0 and M == 0):
        c.note("Krop påvirket af tryk")
        return _ladder(c, "c_w / t_w", ["33 * epsilon", "38 * epsilon", "42 * epsilon"], "Krop")
    if N <= 0:
        c.note("Krop påvirket af bøjning" + (" (træk virker gunstigt og ses bort fra)" if N < 0 else ""))
        return _ladder(c, "c_w / t_w", ["72 * epsilon", "83 * epsilon", "124 * epsilon"], "Krop")
    c.note("Krop påvirket af bøjning og tryk")
    alpha = c.eq("alpha", "min(1, 0.5 * (1 + N_Ed / (c_w * t_w * f_y)))",
                 desc="Andel af kroppen i tryk (plastisk)", ref=T52)
    if alpha > 0.5:
        lim1, lim2 = "396 * epsilon / (13 * alpha - 1)", "456 * epsilon / (13 * alpha - 1)"
    else:
        lim1, lim2 = "36 * epsilon / alpha", "41.5 * epsilon / alpha"
    for cls, rhs in ((1, lim1), (2, lim2)):
        if c.cond("c_w / t_w", "<=", rhs, ref=T52, text_true=f"Krop: klasse {cls}",
                  text_false=f"ikke klasse {cls}"):
            return cls
    c.eq("sigma_1", "N_Ed / A + abs(M_Ed) / W_el_y", "MPa", "Største trykspænding (elastisk)")
    c.eq("sigma_2", "N_Ed / A - abs(M_Ed) / W_el_y", "MPa", "Mindste spænding (elastisk)")
    psi = c.eq("psi", "sigma_2 / sigma_1", desc="Spændingsforhold", ref=T52)
    rhs = "42 * epsilon / (0.67 + 0.33 * psi)" if psi > -1 else "62 * epsilon * (1 - psi) * sqrt(-psi)"
    if c.cond("c_w / t_w", "<=", rhs, ref=T52, text_true="Krop: klasse 3", text_false="ikke klasse 3"):
        return 3
    return 4


@register
class Klassifikation(Check):
    key = "klassifikation"
    title = "Tværsnitsklassifikation"
    clause = "EN 1993-1-1, 5.5"

    def run(self, ctx: Context):
        c = ctx.calc()
        c.eq("epsilon", "sqrt(235 / f_y)", desc="Materialefaktor", ref=T52)
        c.eq("c_f", "(b - t_w - 2 * r) / 2", "mm", "Flangens udragende del", T52)
        cf = _ladder(c, "c_f / t_f", ["9 * epsilon", "10 * epsilon", "14 * epsilon"], "Flange")
        c.eq("c_w", "h - 2 * t_f - 2 * r", "mm", "Kroppens fri højde", T52)
        cw = web_class(c)
        kl = max(cf, cw)
        c.note(f"<b>Tværsnittet er i klasse {kl}</b> for den aktuelle påvirkning.")
        ctx.results["klasse"] = kl
        ctx.results["klasse_flange"] = cf
        if ctx.member.N_Ed > 0 and ctx.member.M_Ed != 0:
            c.note("Klasse for rent tryk (anvendes ved søjlefladning):")
            kn = max(cf, web_class(c, compression_only=True))
            c.note(f"<b>Klasse {kn}</b> for rent tryk.")
        else:
            kn = kl
        ctx.results["klasse_N"] = kn
        if kl == 4 or kn == 4:
            c.warn("Klasse 4 kræver effektive tværsnit efter EN 1993-1-5 og er ikke med i denne version.")
            return self.result(c, None, UNSUPPORTED)
        return self.result(c, None, OK, governing=f"Klasse {kl}")
