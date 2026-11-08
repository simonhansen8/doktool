# beregn – statiske beregningsrapporter efter Eurocode

Version 0.1 · Første version med fokus på stål (EN 1993-1-1) og dansk NA.

Værktøjet er bygget i tre lag, så det ikke er bundet til én opgave:

| Lag | Mappe | Indhold |
|---|---|---|
| **Beregningsmotor** | `beregn/checks/` | Små eftervisningsmoduler. Hver formel er knyttet til sin paragraf. |
| **Norm** | `beregn/norms/data/` | Partialkoefficienter og NDP'er i YAML. Et nationalt anneks arver de anbefalede værdier og overskriver kun det, der afviger. |
| **Rapport** | `beregn/report/` | HTML/PDF med formler, indsatte værdier, resultater og udnyttelsesgrader. Firmaskabelon med logo og farver. |

## Kom i gang

```bash
pip install -e ".[pdf]"          # pyyaml, jinja2, openpyxl + weasyprint til PDF
python -m beregn eksempler/eksempel_hal.yaml -o rapport.pdf
python -m beregn eksempler/eksempel_hal.xlsx -o rapport.html
```

Input kan være YAML eller Excel (se `eksempler/`). Størrelser i YAML skrives med enhed, f.eks. `8,0 m`, `165 kNm`.
Fortegn: N<sub>Ed</sub> > 0 er tryk.

## Eftervisninger i v0.1

| Nøgle | Eftervisning | Afsnit |
|---|---|---|
| `klassifikation` | Tværsnitsklasse (flange og krop, bøjning/tryk/kombineret) | 5.5, tabel 5.2 |
| `boejning` | Momentbæreevne om stærk akse | 6.2.5 |
| `forskydning` | Plastisk forskydningsbæreevne + kontrol af forskydningsbuling | 6.2.6 |
| `kombineret` | M + N + V i tværsnit (plastisk for klasse 1–2, elastisk for klasse 3) | 6.2.8–6.2.10 |
| `soejlefladning` | Bøjningsudknækning om y og z, valsede I/H-profiler | 6.3.1 |
| `kipning` | Kipning med M<sub>cr</sub> fra 3-faktor-formlen, generel eller valset metode inkl. f-faktor | 6.3.2 |

Profilbibliotek: IPE 80–600, HEA 100–600, HEB 100–600 (`beregn/sections/data/valsede_I.csv`).
Tværsnitskonstanterne beregnes ud fra geometrien og afviger under ca. 1 % fra producenttabellerne (testet).

## Afgrænsninger (vigtigt)

* **DK NA-værdierne skal verificeres** mod den gældende udgave, før værktøjet bruges i projekter.
  Rapporten viser et advarselsfelt, så længe `status` i `DK.yaml` indeholder "UDKAST".
* Kun moment om stærk akse. Biaksial bøjning er ikke med.
* **Stabilitetsinteraktion for bjælke-søjler (6.3.3) er ikke med endnu.** Elementer med både tryk og moment
  markeres "Mangler 6.3.3" i oversigten.
* Klasse 4-tværsnit og forskydningsbuling (EN 1993-1-5) er markeret "Ikke understøttet".
* Snitkræfterne er input; lastkombinationer efter EN 1990 laves ikke af værktøjet.

## Udvidelse

**Nyt nationalt anneks:** kopiér `beregn/norms/data/EN1993-1-1/_skabelon_nyt_anneks.yaml` til f.eks. `SE.yaml`,
og overskriv de NDP'er der afviger. En parameter kan være en fast værdi, et udtryk (`udtryk: "1.10 * gamma_3"`)
eller afhænge af et valg (`afhaenger_af: kontrolklasse`). Vælg det med `nationalt_anneks: SE` i input.

**Ny eftervisning:** opret en fil i `beregn/checks/` og importér den i `checks/__init__.py`:

```python
from .base import Check, register

@register
class Traek(Check):
    key = "traek"
    title = "Træk, tværsnit"
    clause = "EN 1993-1-1, 6.2.3"

    def run(self, ctx):
        c = ctx.calc()
        c.param("gamma_M0")                                   # hentes fra norm-laget
        c.eq("N_pl_Rd", "A * f_y / gamma_M0", "kN", "Plastisk bæreevne", "EN 1993-1-1, (6.6)")
        u = c.util("eta_t", "abs(N_Ed) / N_pl_Rd", ref="EN 1993-1-1, (6.5)")
        return self.result(c, u, governing="N_Ed / N_pl_Rd")
```

Formler skrives som almindelige udtryk. Rapporten viser dem automatisk symbolsk, med indsatte værdier og
med resultat. Variabelnavne oversættes til symboler: `W_pl_y` → W<sub>pl,y</sub>, `gamma_M0` → γ<sub>M0</sub>,
`lambda_bar_LT` → λ̄<sub>LT</sub>.

**Ny profil:** tilføj en linje med `h, b, tw, tf, r` i CSV-filen.

**Firmaskabelon:** kopiér `beregn/report/templates/standard/`, ret `skabelon.yaml` (navn, adresse, logo, farve)
og evt. `style.css`/`rapport.html.j2`, og kør med `--skabelon sti/til/mappe`.

## Test

```bash
python -m pytest tests
```

Testene kontrollerer profilkonstanter mod producenttabeller, DK-partialkoefficienter og hver eftervisning
mod en uafhængig håndregning.

## Næste skridt (forslag)

1. Bjælke-søjle-interaktion 6.3.3 (bilag A eller B) og bøjning om svag akse.
2. Flere lastkombinationer pr. element med automatisk styrende kombination.
3. Import direkte fra FEM-programmet (snitkræfter pr. element).
4. Flere profiltyper (RHS/SHS/CHS, UPE) og samlinger (EN 1993-1-8).
5. Beton (EN 1992) og træ (EN 1995) som nye modulpakker med egne norm-filer.
