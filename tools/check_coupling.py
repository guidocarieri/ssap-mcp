# -*- coding: utf-8 -*-
"""Check whether this server can still drive the SSAP you have installed.

Run this after every SSAP update, BEFORE trusting the server on real work.
It takes about a minute: it opens SSAP, looks at the things the server depends
on, and closes it again. It never runs a verification.

    python tools/check_coupling.py

Why it exists: a campaign of twenty models takes half an hour and tells you
whether it worked *this time*. This tells you WHAT the server is holding on to,
so that when a future release moves one of those things you learn it here
instead of halfway through a real job.

⛔ Must run ELEVATED. SSAP runs elevated, and Windows UIPI forbids a normal
process from sending messages to an elevated window: without elevation the
button checks report failures that are not real.

⛔ Nota per chi legge il codice: i sei nomi dei pulsanti sono in ITALIANO perche'
il pilota li cerca per uguaglianza esatta. Se l'interfaccia di SSAP e' impostata
in inglese quei nomi non esistono e il server non trova nulla: questo controllo
lo dice invece di lasciartelo scoprire su un lavoro vero.
"""
from __future__ import annotations

import ctypes
import os
import pathlib
import re
import subprocess
import sys
import time
from ctypes import wintypes

SSAP_EXE = pathlib.Path(os.environ.get("SSAP_EXE", r"C:\SSAP2010\ssap2010_64bit.exe"))

# ── ciò a cui il server è agganciato ────────────────────────────────────────
TITOLO = "SSAP 2010"
PULSANTI = [
    "LEGGI MODELLO",
    "CARICA IMPOSTAZIONI PROGETTO",
    "SALVA IMPOSTAZIONI PROGETTO",
    "AVVIO VERIFICA",
    "STOP VERIFICA",
    "GENERA REPORT VERIFICA",
]
ETICHETTE_PAR = ["METODO DI CALCOLO [", "MOTORE DI RICERCA ["]
PATTERN_REPORT = {
    "minimum Fs": r"#FS_minimo\s*#Fattore di sicurezza\(FS\)=\s*([0-9.]+)",
    "surfaces generated": r"TOTALE SUPERFICI GENERATE\s*:\s*(\d+)",
    "method used": r"METODO DI CALCOLO\s*:\s*(.+)",
    "engine used": r"MOTORE DI RICERCA\s*:\s*(.+)",
}

u = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
SW_RESTORE = 9

esiti: list[tuple[str, bool | None, str]] = []


def segna(voce: str, ok: bool | None, nota: str = "") -> None:
    esiti.append((voce, ok, nota))
    simbolo = {True: "OK  ", False: "FAIL", None: "  ? "}[ok]
    print(f"  [{simbolo}] {voce}{('  — ' + nota) if nota else ''}", flush=True)


def txt(h) -> str:
    b = ctypes.create_unicode_buffer(1024)
    u.GetWindowTextW(h, b, 1024)
    return b.value


def cls(h) -> str:
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def finestre() -> list:
    out = []
    u.EnumWindows(CB(lambda h, _: (out.append(h), True)[1]), 0)
    return out


def figli(h) -> list:
    out = []
    u.EnumChildWindows(h, CB(lambda c, _: (out.append(c), True)[1]), 0)
    return out


def elevato() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def trova_finestra(secondi: int = 60):
    """La finestra VERA, non la prima che porta quel nome.

    ⛔ Misurato il 2026-08-04, alla prima prova di questo stesso strumento: SSAP
    espone PIU' finestre col titolo «SSAP 2010», fra cui quella-applicazione di
    Lazarus, larga 0x0 e SENZA controlli. Agganciando quella, il controllo
    dichiarava mancanti tutti e sei i pulsanti su una build che il server stava
    pilotando correttamente in quel momento — un falso allarme, cioe' il difetto
    peggiore per uno strumento diagnostico: chi lo riceve smette di usarlo.

    Il criterio non e' il nome ma il CONTENUTO: si accetta solo la finestra che
    ha davvero dei pulsanti dentro. Cosi' si attende anche che il programma
    finisca di aprirsi, invece di leggerlo a meta' avvio.
    """
    t0 = time.time()
    migliore, quanti_max = None, 0
    while time.time() - t0 < secondi:
        for h in finestre():
            if TITOLO not in txt(h):
                continue
            if u.IsIconic(h):
                u.ShowWindow(h, SW_RESTORE)
                time.sleep(1.0)
            quanti = sum(1 for c in figli(h) if cls(c) == "Button")
            if quanti > quanti_max:
                migliore, quanti_max = h, quanti
        if quanti_max >= 5:          # la finestra operativa ne ha decine
            return migliore
        time.sleep(1)
    return migliore                  # meglio la migliore trovata che nessuna


def main() -> int:
    print("SSAP coupling check — what this server holds on to\n")

    if not elevato():
        print("  ⚠ NOT ELEVATED. SSAP runs elevated and Windows UIPI will hide its")
        print("    controls from this process: button results below are meaningless.")
        print("    Re-run this from an elevated prompt.\n")

    # 1 — l'eseguibile e la sua versione
    if not SSAP_EXE.exists():
        segna("SSAP executable", False, f"not found: {SSAP_EXE}")
        return 2
    try:
        ver = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Item '{SSAP_EXE}').VersionInfo.FileVersion"],
            capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        ver = "?"
    segna("SSAP executable", True, f"{SSAP_EXE.name}  version {ver or '?'}")

    # 2 — la finestra: cercata come SOTTOSTRINGA, quindi regge i cambi di release
    gia_aperto = trova_finestra(2) is not None
    if not gia_aperto:
        subprocess.Popen([str(SSAP_EXE)], cwd=str(SSAP_EXE.parent))
    main_h = trova_finestra(60)
    if main_h is None:
        segna(f"main window containing «{TITOLO}»", False,
              "not found: a new release may have renamed it")
        return 2
    segna(f"main window containing «{TITOLO}»", True, f"«{txt(main_h)[:46]}»")

    # 3 — i sei pulsanti, cercati per UGUAGLIANZA ESATTA: è l'aggancio più fragile
    presenti = {txt(c) for c in figli(main_h) if cls(c) == "Button"}
    mancanti = [n for n in PULSANTI if n not in presenti]
    for n in PULSANTI:
        segna(f"button «{n}»", n in presenti)
    if mancanti:
        inglese = any(re.search(r"\b(READ|LOAD|SAVE|START|STOP|REPORT)\b", p or "")
                      for p in presenti)
        segna("button names", False,
              "SSAP's interface may be set to ENGLISH: the pilot looks for the "
              "ITALIAN names above and will not find them"
              if inglese else
              f"{len(mancanti)} of {len(PULSANTI)} missing — the pilot cannot drive this build")

    # 4 — le etichette del .PAR: cercate per PREFISSO, quindi reggono il contenuto fra parentesi
    par = next((p for p in (SSAP_EXE.parent / "pendii").rglob("*.par")), None)
    if par is None:
        segna(".PAR labels", None, "no sample .PAR found under pendii/")
    else:
        testo = par.read_text(encoding="latin-1", errors="replace")
        for et in ETICHETTE_PAR:
            riga = next((r for r in testo.splitlines() if r.startswith(et)), None)
            segna(f".PAR label «{et}…»", riga is not None,
                  riga.strip() if riga else f"absent from {par.name}")

    # 5 — le stringhe del report: si controllano su un report già prodotto
    rep = next((p for p in (SSAP_EXE.parent / "pendii").rglob("report_*.txt")), None)
    if rep is None:
        segna("report patterns", None,
              "no report_*.txt to check against — run one verification, then re-run this")
    else:
        t = rep.read_text(encoding="latin-1", errors="replace")
        for nome, pat in PATTERN_REPORT.items():
            m = re.search(pat, t)
            segna(f"report field «{nome}»", m is not None,
                  (m.group(1).strip()[:40] if m else "pattern no longer matches"))

    if not gia_aperto:
        subprocess.run(["taskkill", "/F", "/IM", SSAP_EXE.name],
                       capture_output=True)

    falliti = [v for v, ok, _ in esiti if ok is False]
    ignoti = [v for v, ok, _ in esiti if ok is None]
    print()
    if falliti:
        print(f"RESULT: {len(falliti)} coupling point(s) BROKEN — "
              f"do not trust the server on this build until fixed:")
        for v in falliti:
            print(f"  - {v}")
        return 1
    print("RESULT: every coupling point still holds on this build."
          + (f"  ({len(ignoti)} not checked)" if ignoti else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
