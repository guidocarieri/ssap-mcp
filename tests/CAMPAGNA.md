# Verification campaign on SSAP's own example models

Nineteen models shipped with SSAP2010, run end-to-end through this server.
Not synthetic cases: the files are the ones the author distributes, in
`C:\SSAP2010\pendii`, so anyone with SSAP installed can repeat this.

Every Fs below is read from the **final report**, which is the only
authoritative statement of what SSAP actually computed — never from the
`.tmp` files, which are mid-run snapshots.

Settings: 5000 surfaces, local-Fs and fluid-pressure maps **off** (they are a
different and far heavier computation, not needed for a factor of safety), each
run on a **freshly started SSAP instance**.

## Results — 17 of 19

| case | what it exercises | Fs |
|---|---|---|
| `07a_terra_armata` | geogrids + water table + surcharges | **1.8161** |
| `08b_gabbionata` | gabion wall + geosynthetic | **1.6476** |
| `08a_muro_tiranti` | gravity wall as a lens + anchors | **1.6224** |
| `04a_discarica_DRENATA` | **drained** conditions (c′, φ′) | **1.4539** |
| `07b_geogriglie_nondren` | geogrids + undrained | **1.3926** |
| `06_complesso_13strati` | **13 layers**, Hoek-Brown, piles, anchors, surcharges | **1.2230** |
| `02a_pali_tiranti_CON` | piles + anchors + Hoek-Brown + water table | **1.1376** |
| `09b_liquefazione_NO` | same model, liquefaction flag off | **1.1304** |
| `04b_discarica_NONDRENATA` | **undrained** conditions (cu) | **1.0545** |
| `03a_micropali_COMPLETO` | piles + anchors + undrained | **1.0061** |
| `03c_micropali_SOLOPALI` | piles only | **1.0017** |
| `05a_roccia_soloTIRANTI` | rock, Barton-Bandis joints, anchors | **0.9961** |
| `05b_roccia_WIREMESH` | as above **+ wire mesh** | **0.9138** |
| `03b_micropali_NUDO` | same slope, no reinforcement | **0.8795** |
| `02b_pali_tiranti_SENZA` | same site, no works | **0.7511** |
| `09a_liquefazione_SI` | **liquefiable** layers | **0.6308** |
| `05c_roccia_WIREMESH_WET` | rock + mesh **+ water table** | **0.1490** |

### What the pairs say

- **Liquefaction** — 0.6308 with, 1.1304 without: **−44.2%**, on models identical
  but for that one flag.
- **Drained vs undrained** — 1.4539 against 1.0545, **−27.5%**: same geometry,
  c′φ′ against cu. Both regimes are driven correctly.
- **Reinforcement** — bare slope 0.8795, with piles 1.0017, with piles and
  anchors 1.0061: **+13.9%**. Note that piles alone and piles+anchors differ by
  0.004, which is **inside the scatter** of a pseudo-random search: with a single
  run per configuration the anchors' contribution cannot be separated from noise.
- **Water table in rock** — 0.9138 dry against 0.1490 wet, on the same slope with
  the same mesh and anchors.
- ⛔ `02a` vs `02b` is **not** a valid comparison: 7 layers against 4. The numbers
  are there, the meaning is not.
- 🔴 `05b` (with mesh) reads **lower** than `05a` (anchors only). A reinforcement
  lowering Fs is counter-intuitive and is **not explained** here: the two models
  may differ by more than the mesh, or the mesh may move the critical surface to
  a different mechanism. Recorded as open rather than glossed over.

## The two that do not converge — and why

`01a_tiranti_roccia_CON` and `01b_tiranti_roccia_SENZA` (model `esempio4`) never
complete, with or without anchors, with the author's own settings, and with a
freshly started instance. The cause is in the model, and it is geotechnical.

Its `.GEO` declares both layers as Hoek-Brown with **D = 1.00** — maximum
disturbance — and the upper one with **GSI = 20**. Working the 2002 formulae:

| | GSI | D | mb | s | **σcm = σci·sᵃ** |
|---|---|---|---|---|---|
| `esempio4` layer 1 | 20 | 1.00 | 0.059 | 1.6·10⁻⁶ | **7.1 kPa** |
| `esempio4` layer 2 | 50 | 1.00 | 0.506 | 2.4·10⁻⁴ | 591 kPa |
| a real job (SP 490) | 33 | 0.50 | 0.329 | 1.3·10⁻⁴ | 341 kPa |

**7 kPa** of rock-mass strength, forty-eight times less than a real slope, over
10 m of relief: every surface falls well below unity and the solver looks for a
minimum in a field where everything collapses. The path inside the file says what
it is — `CORSO_SSAP_firenze_2011-2013` — a teaching model built as a limit case.

It is kept in the campaign, and red, on purpose. Changing its parameters to make
it pass would mean adjusting the ruler instead of reading the measurement.

## What this campaign found in the server

Nine defects, of which **six** were invisible to code review — two independent
audit passes over the source had produced exactly one real finding.

The worst was the last: **the server reused one SSAP instance across
consecutive runs**. SSAP accumulates state, so a run would fail — but not always
the same one. Failures moved between cases across passes, with identical files,
which sent me chasing causes in the models: the mesh, the joints, the maps, the
anchor loads. `05a` went from "forty minutes without finishing" to **88 seconds**
once each run got a clean instance.

A defect that moves is worse than one that is simply wrong, and it only shows up
when runs are chained — that is, only under automation. Whoever works by hand
runs one verification, reads it, closes it, and never sees it.
