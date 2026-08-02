# Verification campaign on SSAP's own example models

Nineteen models shipped with SSAP2010, plus one built from scratch, run end-to-end through this server.
Not synthetic cases: the files are the ones the author distributes, in
`C:\SSAP2010\pendii`, so anyone with SSAP installed can repeat this.

Every Fs below is read from the **final report**, which is the only
authoritative statement of what SSAP actually computed — never from the
`.tmp` files, which are mid-run snapshots.

Settings: 5000 surfaces, local-Fs and fluid-pressure maps **off** (they are a
different and far heavier computation, not needed for a factor of safety), each
run on a **freshly started SSAP instance**.

## Results — 20 of 20

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
| `10_modello_mio` | **built from scratch**: loose cover, silt, Hoek-Brown rock, water table, 3 passive bolts | **1.0305** |
| `01a_tiranti_roccia_CON` | Hoek-Brown rock + anchors | **1.0120** |
| `03a_micropali_COMPLETO` | piles + anchors + undrained | **1.0061** |
| `03c_micropali_SOLOPALI` | piles only | **1.0017** |
| `05a_roccia_soloTIRANTI` | rock, Barton-Bandis joints, anchors | **0.9961** |
| `05b_roccia_WIREMESH` | as above **+ wire mesh** | **0.9138** |
| `03b_micropali_NUDO` | same slope, no reinforcement | **0.8795** |
| `01b_tiranti_roccia_SENZA` | same rock slope, **no anchors** | **0.8240** |
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
- **Anchors on rock** — 0.8240 without, 1.0120 with: **+22.8%**, same slope and
  same settings. The cleanest pair of the campaign.
- **Water table in rock** — 0.9138 dry against 0.1490 wet, on the same slope with
  the same mesh and anchors.
- ⛔ `02a` vs `02b` is **not** a valid comparison: 7 layers against 4. The numbers
  are there, the meaning is not.
- 🔴 `05b` (with mesh) reads **lower** than `05a` (anchors only). A reinforcement
  lowering Fs is counter-intuitive and is **not explained** here: the two models
  may differ by more than the mesh, or the mesh may move the critical surface to
  a different mechanism. Recorded as open rather than glossed over.

## `esempio4` — a wrong diagnosis, corrected

`01a_tiranti_roccia_CON` (**1.012**) and `01b_tiranti_roccia_SENZA` (**0.824**)
now converge in 68 and 83 seconds. Their pair is the clearest of the campaign:
**+22.8%** from the anchors alone, same slope, same settings.

They are recorded here because for most of this campaign they did not converge,
and I explained why — at length, with the Hoek-Brown arithmetic: the rock mass
computes to sigma_cm = 7.1 kPa (GSI 20, D 1.00), forty-eight times weaker than a
real slope, so every surface falls far below unity and the solver hunts for a
minimum in a field where everything collapses. The path inside the file even
says `CORSO_SSAP_firenze_2011-2013`, a teaching model built as a limit case.

Every sentence of that is true. The conclusion was wrong.

They did not converge because **I had zeroed their starting zone**. Having
mistaken `X1`/`X2` for the internal obstacle — which has its own separate fields,
`X1 OSTACOLO`/`X2 OSTACOLO`, further down the same file — I set them to zero.
`X1 = X2 = 0` is an empty interval: SSAP has nowhere to start generating
surfaces, so the run never begins. No error, no dialog. The panel simply sits
there with empty results and the start buttons still enabled, while the pilot
waits out its timeout on a computation that never started.

The lesson is not about that parameter. It is that a plausible explanation with
correct arithmetic behind it is still just a hypothesis, and mine survived only
because it was never retested after the real cause was removed. What settled it
was **looking at the panel** — which reports its own state, and had been saying
"the model is loaded, you may launch the verification" the whole time.
