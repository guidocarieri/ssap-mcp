# -*- coding: utf-8 -*-
"""Congruenza geometrica fra un .par e il modello a cui lo si vuole applicare.

⛔ Nasce da un guasto misurato il 2026-08-01: un .par con i limiti di ricerca a
X ~ 1965..2539 m applicato a un modello esteso fra X = 10 e 35 m manda SSAP in
«Invalid floating point operation», con un dialogo che propone di IGNORARE e
RISCHIARE LA CORRUZIONE DEI DATI. Il .par non e' un file di preferenze: porta
dentro le coordinate della finestra di ricerca, ed e' legato AL MODELLO.

Questa funzione e' il controllo che manca a `run_verification`.
"""
from __future__ import annotations

import pathlib
import re

# Etichette del .PAR che definiscono la FINESTRA DI RICERCA: sono quelle che
# vincolano davvero dove SSAP cerca le superfici.
#
# ⛔ Tarato su verita' note il 2026-08-01, non su una soglia di comodo. Non si
# guardano i campi «ESCLUSIONE SOVRACCARICO ...»: sono OPZIONALI e valgono 0.0 o
# un valore sentinella quando non sono impostati, e prendendoli sul serio si
# bocciano a torto i .par legittimi degli esempi (micropiles: respinto per uno
# 0.0; scarpata_roccia: per uno 0.95).
# ⛔ «LIMITE INFERIORE - m» NON e' una progressiva: misurato su 4 modelli con
# geometrie diversissime vale 0.00 in tre casi e 0.95 nel quarto, mentre LIMITE1
# e LIMITE2 cadono SEMPRE dentro l'estensione X del modello (48,40 e 108,60 su
# 40..110; 4,58 e 29,00 su 1,95..30; 104,10 e 580,18 su 50..591; 36,37 e 153,70
# su 20..156). Usarlo come coordinata bocciava a torto i .par legittimi.
ETICHETTE_X = (
    "LIMITE1 SUPERIORE  M",
    "LIMITE1 SUPERIORE M",
    "LIMITE2 SUPERIORE- M",
    "LIMITE2 SUPERIORE M",
)


def estensione_modello(dat: pathlib.Path) -> tuple[float, float, float, float]:
    """(x_min, x_max, y_min, y_max) leggendo tutte le coppie X Y del .dat."""
    xs, ys = [], []
    for riga in dat.read_text(encoding="latin-1", errors="replace").splitlines():
        campi = riga.split()
        # ⛔ Alcuni .DAT marcano le righe di coordinate con un '@' iniziale
        # (es. «@   0.00   19.95»). Pretendere esattamente due campi le
        # scartava TUTTE, e il modello risultava senza geometria: misurato il
        # 2026-08-02 su un modello con geogriglie degli esempi di SSAP.
        if campi and campi[0] in ("@", "&", "*"):
            campi = campi[1:]
        if len(campi) < 2:
            continue
        try:
            x, y = float(campi[0]), float(campi[1])
        except ValueError:
            continue
        xs.append(x)
        ys.append(y)
    if not xs:
        raise ValueError(f"nessuna coppia X Y in {dat.name}")
    return min(xs), max(xs), min(ys), max(ys)


def progressive_par(par: pathlib.Path) -> dict[str, float]:
    """Le progressive dichiarate nel .par, per etichetta."""
    righe = par.read_text(encoding="latin-1", errors="replace").splitlines()
    fuori = {}
    for i, r in enumerate(righe):
        et = r.strip().upper()
        if et in ETICHETTE_X and i + 1 < len(righe):
            try:
                fuori[r.strip()] = float(righe[i + 1].strip())
            except ValueError:
                pass
    return fuori


def verifica(par: pathlib.Path, dat: pathlib.Path,
             tolleranza: float = 0.25) -> dict:
    """Il .par e' applicabile a questo modello?

    tolleranza = quota della larghezza del modello ammessa come sconfinamento
    (un limite di ricerca puo' legittimamente stare poco fuori dal profilo).
    """
    x0, x1, y0, y1 = estensione_modello(dat)
    largh = x1 - x0
    margine = max(largh * tolleranza, 1.0)
    prog = progressive_par(par)

    # 0.0 = campo non impostato, non "cerca all'origine"
    fuori = {k: v for k, v in prog.items()
             if v != 0.0 and not (x0 - margine <= v <= x1 + margine)}
    return {
        "ok": not fuori,
        "modello_x": (round(x0, 2), round(x1, 2)),
        "modello_y": (round(y0, 2), round(y1, 2)),
        "larghezza": round(largh, 2),
        "margine": round(margine, 2),
        "progressive_par": {k: round(v, 2) for k, v in prog.items()},
        "fuori_intervallo": {k: round(v, 2) for k, v in fuori.items()},
        "motivo": (
            "" if not fuori else
            f"il .par cerca a X={sorted(round(v,1) for v in fuori.values())} "
            f"ma il modello sta fra X={round(x0,1)} e {round(x1,1)} m: "
            f"la ricerca avverrebbe dove non c'e' pendio"
        ),
    }
