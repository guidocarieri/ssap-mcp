# -*- coding: utf-8 -*-
"""Significato dei parametri di SSAP, come li dichiara SSAP stesso.

⛔ Nessuna voce di questo file e' dedotta o inferita. Ogni riga e' copiata dalla
sezione «LEGENDA SIMBOLI» che SSAP stampa a chiusura di ciascuna tabella nel
report di fine verifica. Il report e' la fonte autorevole — per il metodo di
calcolo, per il motore di ricerca e anche per il significato dei campi.

Perche' questo file esiste. Il manuale di riferimento e' fermo alla rel. 5.2
(feb 2023) mentre il programma e' alla 6.1, e per i file di modello NON elenca i
campi: del `.PAR` dice soltanto che «non richiede di essere editato». Chi scrive
quei file a programma resta senza documentazione, e finisce per indovinare: e'
successo con la settima colonna del `.TIR`, presa per un coefficiente di
sfilamento quando invece e' il coefficiente di riduzione della forza in testa.
Bastava leggere la legenda.

Aggiornare questo file e' facile e va fatto sui REPORT, non sul manuale:
`python -m ssap_mcp.glossario <cartella con report_*.txt>` ristampa le legende
trovate, cosi' si vede subito se una build nuova ha aggiunto o rinominato campi.
"""
from __future__ import annotations

import pathlib
import re
import sys

# ---------------------------------------------------------------------------
# Estratto VERBATIM dai report di verifica SSAP 6.1 (build 15998).
# ---------------------------------------------------------------------------

GLOSSARIO: dict[str, dict[str, str]] = {
    "TIRANTI/ANCORAGGI (.TIR)": {
        "N.": "Numero tirante/ancoraggio",
        "X (m)": "Coordinata X testa",
        "Y (m)": "Coordinata Y testa",
        "Beta (°)": "Inclinazione ancoraggio — angolo con l'orizzontale "
                    "(positivi in elevazione, negativi in depressione)",
        "L (m)": "Lunghezza",
        "T (kN/m)": "Tensione di progetto",
        "Lc (%)": "% lunghezza cementata",
        "K (-)": "Coefficiente riduzione Forza in Testa Ancoraggio",
    },
    "PALIFICATE (.PIL)": {
        "N. (-)": "Numero palificata",
        "X (m)": "Coordinata X testa",
        "Y (m)": "Coordinata Y testa",
        "L (m)": "Lunghezza pali L*",
        "D (m)": "Diametro pali",
        "D2 (m)": "Lunghezza apertura tra pali",
        "D1 (m)": "Lunghezza interasse tra pali",
        "fNTC (-)": "Fattore riduttivo resistenza palificata (NTC 2018)",
    },
    "GEOSINTETICI (.GRD)": {
        "Ngrid": "Numero geosintetico",
        "X (m)": "Coordinata X testa",
        "Y (m)": "Coordinata Y testa",
        "L (m)": "Lunghezza geosintetico",
        "T (kN/m)": "Resistenza a trazione di progetto",
        "fb (-)": "Fattore di interazione suolo/geosintetico",
        "fds (-)": "Fattore riduzione Direct Sliding",
        "Lws (m)": "Lunghezza risvolto a sinistra",
        "Lwd (m)": "Lunghezza risvolto a destra",
        "Omega (-)": "Coefficiente di mobilizzazione di T come reazione "
                     "orizzontale massima Th (kN/m)",
    },
    "SOVRACCARICHI IN SUPERFICIE (.SVR)": {
        "N.": "Numero sovraccarico",
        "X1 (m)": "Posizione carico da X1",
        "X2 (m)": "a X2",
        "SX1 (kPa)": "Carico in X1",
        "SX2 (kPa)": "Carico in X2",
        "Alpha (°)": "Inclinazione carico (gradi)",
        "WsH1, WsH2 (kN/m)": "Forza unitaria orizzontale (per metro di "
                             "proiezione verticale), da X1 a X2",
        "WsV1, WsV2 (kN/m)": "Forza unitaria verticale (per metro di "
                             "proiezione orizzontale), da X1 a X2",
    },
    "CONCI DELLA SUPERFICIE A MINOR FS": {
        "X (m)": "Ascissa sinistra concio",
        "dx (m)": "Larghezza concio",
        "alpha (°)": "Angolo pendenza base concio",
        "W (kN/m)": "Forza peso concio",
        "ru (-)": "Coefficiente locale pressione interstiziale",
        "U (kPa)": "Pressione totale dei pori base concio",
        "phi' (°)": "Angolo di attrito efficace base concio",
        "c'/Cu (kPa)": "Coesione efficace o resistenza al taglio in "
                       "condizioni non drenate",
    },
    "DIAGRAMMA DELLE FORZE": {
        "ht (m)": "Altezza linea di thrust dal nodo sinistro base concio",
        "yt (m)": "Coordinata Y linea di thrust",
        "yt' (-)": "Gradiente pendenza locale linea di thrust",
        "E(x) (kN/m)": "Forza normale interconcio",
        "T(x) (kN/m)": "Forza tangenziale interconcio",
        "E' (kN)": "Derivata forza normale interconcio",
        "Rho(x) (-)": "Fattore mobilizzazione resistenza al taglio verticale "
                      "interconcio, Zhu et al. (2003)",
        "FS_qFEM(x) (-)": "Fattore di sicurezza locale stimato (in X) by qFEM",
        "FS_p-qPATH(x) (-)": "Fattore di sicurezza locale stimato (in X) "
                             "by procedura p-qPATH",
    },
    "SFORZI DI TAGLIO LUNGO LA SUPERFICIE": {
        "dl (m)": "Lunghezza base concio",
        "TauStress (kPa)": "Sforzo di taglio su base concio",
        "TauF (kN/m)": "Forza di taglio su base concio",
        "TauStrength (kPa)": "Resistenza al taglio su base concio",
        "TauS (kN/m)": "Forza resistente al taglio su base concio",
    },
    "INTERAZIONI TIRANTI ↔ SUPERFICIE": {
        "NTir (-)": "Numero tirante",
        "X (m)": "Progressiva intersezione tra tirante e superficie di scivolamento",
        "Y (m)": "Quota intersezione tra tirante e superficie di scivolamento",
        "Tipo (-)": "Tipo tirante: 1 = PASSIVO, 2 = ATTIVO",
        "T (kN/m)": "Tensione di progetto",
        "Th_mob (kN/m)": "Reazione mobilitata — componente orizzontale",
        "Tv_mob (kN/m)": "Reazione mobilitata — componente verticale",
        "DeltaF (kN)": "Deficit massimo di forze lungo la superficie di "
                       "scivolamento, calcolato per arrivare a FS = 2.0",
        "alpha (°)": "Angolo pendenza locale della superficie nel punto "
                     "di intersezione",
        "beta (°)": "Angolo tirante",
        "F (-)": "Coefficiente distribuzione trazione lungo fondazione",
        "Omega (-)": "Coefficiente mobilizzazione tensione nominale di progetto",
    },
}

# Righe di intestazione che il report stampa PRIMA della tabella tiranti e che
# dichiarano come vengono trattati gli ancoraggi nella verifica.
CONTESTO_TIRANTI = {
    "TIPO TIRANTI/ANCORAGGI": "Passivi | Attivi",
    "DISTRIBUZIONE FORZA RESISTENTE TIPO": "Trapezoidale | ...",
    "PROCEDURA AUTOMATICA CALCOLO MOBILIZZAZIONE FORZA TIRANTI": "Attivata | Disattivata",
}


def legende_dai_report(cartella: pathlib.Path) -> dict[str, dict[str, str]]:
    """Rilegge le «LEGENDA SIMBOLI» dai report presenti in una cartella.

    Serve a verificare che questo glossario sia ancora allineato al programma:
    una build nuova puo' aggiungere colonne, e il modo di accorgersene e'
    rileggere il report, non aspettare un manuale.
    """
    fuori: dict[str, dict[str, str]] = {}
    for rep in sorted(cartella.rglob("report_*.txt")):
        t = rep.read_bytes().decode("latin-1")
        for m in re.finditer(r"LEGENDA SIMBOLI\s*\n(.*?)(?:-{20,})", t, re.S):
            pre = t[:m.start()]
            tit = re.findall(r"(?:TABELLA|----- )([A-ZÀ-Ù /\.']{6,60})", pre)
            titolo = tit[-1].strip() if tit else rep.name
            voci = fuori.setdefault(titolo, {})
            for riga in m.group(1).splitlines():
                riga = riga.strip()
                if ":" in riga and len(riga) > 8 and not riga.startswith("-"):
                    k, v = riga.split(":", 1)
                    voci.setdefault(k.strip(), v.strip())
    return fuori


def main(argv: list[str]) -> int:
    if argv:
        trovate = legende_dai_report(pathlib.Path(argv[0]))
        if not trovate:
            print("nessun report_*.txt con LEGENDA SIMBOLI in quella cartella")
            return 1
        for tab, voci in trovate.items():
            print(f"\n### {tab}")
            for k, v in voci.items():
                print(f"    {k:24s} = {v}")
        return 0
    for tab, voci in GLOSSARIO.items():
        print(f"\n### {tab}")
        for k, v in voci.items():
            print(f"    {k:20s} = {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
