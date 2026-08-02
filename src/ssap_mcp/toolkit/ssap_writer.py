"""ssap_writer.py — Generatore file di input nativi SSAP2010.

Scrive .DAT (geometrie), .GEO (parametri geomeccanici), .FLD (falda), .MOD (master),
rispettando le convenzioni del manuale rel. 5.2 (cap. 3).

Convenzioni SSAP applicate:
- Coordinate XY in metri, sempre POSITIVE, origine basso-sx
- Strati numerati top -> bottom (1 = strato più alto / superficie topografica)
- Lenti numerate > strato che le ingloba
- File .DAT richiede 3 righe header obbligatorie
- File .MOD: prima riga = 9 flag (n_strati, falda, sovraccarichi, tiranti,
  geogriglie, palificate, liquefazione, JRC, wiremesh), poi lista file in ordine fisso
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# ============================================================================
#                        DATACLASSES MODELLO
# ============================================================================

@dataclass
class Layer:
    """Strato geomeccanico — Mohr-Coulomb / Tresca / Hoek-Brown.

    - Mohr-Coulomb (drenato):  phi>0, c>=0, cu=0
    - Tresca (non drenato):    phi=0, c=0, cu>0
    - Hoek-Brown (ammasso):    phi=0, c=0, cu=0, sigma_ci>0, GSI>0, mi>0, D in [0,1]
    """
    name: str = ""
    phi: float = 0.0          # angolo attrito efficace (gradi)
    c: float = 0.0            # coesione efficace (kPa)
    cu: float = 0.0           # coesione non drenata (kPa)
    gamma: float = 20.0       # peso unitario fuori falda (kN/m^3)
    gamma_sat: float = 21.0   # peso unitario saturo (kN/m^3)
    # Hoek-Brown
    sigma_ci: float = 0.0     # MPa
    gsi: float = 0.0
    mi: float = 0.0
    disturbance: float = 0.0  # D, 0..1

    def is_hoek(self) -> bool:
        return self.sigma_ci > 0 and self.gsi > 0 and self.mi > 0


@dataclass
class Surface:
    """Profilo di una superficie come segmentata XY.

    kind:
      'topo'   -> superficie topografica (profilo del pendio)
      'normal' -> tetto di strato sottostante (X crescenti)
      'lens'   -> lente chiusa (poligono antiorario, primo=ultimo)
    """
    points: list[tuple[float, float]]
    kind: str = "topo"  # 'topo' | 'normal' | 'lens'
    name: str = ""


@dataclass
class Surcharge:
    """Sovraccarico distribuito trapezoidale (file .SVR)."""
    x1: float
    x2: float
    q1: float            # carico estremo sx (kPa)
    q2: float            # carico estremo dx (kPa)
    angle_deg: float = 90.0  # 90 = verticale


@dataclass
class Anchor:
    """Tirante / chiodo (file .TIR)."""
    x: float            # x testa
    y: float            # y testa
    beta_deg: float     # angolo orizzontale (positivo = elevazione)
    length: float       # lunghezza totale (m)
    T_design: float     # T  — tensione di progetto (kN/m)
    cemented_pct: float = 20.0  # Lc — % lunghezza cementata
    # K — Coefficiente di riduzione della Forza in Testa all'Ancoraggio (-).
    #
    # 7a colonna del .TIR, scritta da SSAP 6.1 e NON documentata nel manuale
    # rel. 5.2. Il significato NON si deduce dai file: e' dichiarato dal
    # PROGRAMMA nella «LEGENDA SIMBOLI» che chiude la TABELLA TIRANTI/ANCORAGGI
    # di ogni report di verifica —
    #     K(-) : Coefficiente riduzione Forza in Testa Ancoraggio
    # ⛔ Una precedente ipotesi (coefficiente di sfilamento, analogo al `fb`
    # dei geosintetici) era SBAGLIATA: dedotta per analogia invece che letta.
    # Il report e' la fonte, come per il metodo e il motore di ricerca.
    K_riduzione_testa: float = 0.60


@dataclass
class SlopeModel:
    """Modello completo di un pendio per SSAP."""
    name: str
    surfaces: list[Surface] = field(default_factory=list)  # ordinate top->bottom
    layers: list[Layer] = field(default_factory=list)
    water_table: list[tuple[float, float]] | None = None
    surcharges: list[Surcharge] = field(default_factory=list)
    anchors: list[Anchor] = field(default_factory=list)
    notes: str = ""


# ============================================================================
#                        SCRITTORI FILE NATIVI
# ============================================================================

def write_dat(model: SlopeModel, out_dir: Path) -> Path:
    """Scrive il file .DAT con tutte le superfici/lenti/strati.

    Convenzione: 3 righe di header obbligatorie + blocchi `## N ----`
    """
    out = out_dir / f"{model.name}.dat"
    lines: list[str] = [
        f"|| file : {model.name}.dat",
        f"|| Modello: {model.notes or model.name}",
        "|",
    ]
    for i, surf in enumerate(model.surfaces, start=1):
        lines.append(f"## {i} ---------------------------")
        for x, y in surf.points:
            if x < 0 or y < 0:
                raise ValueError(f"SSAP non accetta coordinate negative: ({x}, {y})")
            lines.append(f"  {x:>10.4f} {y:>10.4f}")
    out.write_text("\n".join(lines) + "\n", encoding="ascii")
    return out


def write_fld(model: SlopeModel, out_dir: Path) -> Path | None:
    """Scrive il file .FLD per la superficie freatica/piezometrica."""
    if not model.water_table:
        return None
    out = out_dir / f"{model.name}.fld"
    lines = [f"  {x:>10.4f} {y:>10.4f}" for x, y in model.water_table]
    out.write_text("\n".join(lines) + "\n", encoding="ascii")
    return out


def write_geo(model: SlopeModel, out_dir: Path) -> Path:
    """Scrive il file .GEO con parametri geomeccanici degli strati.

    Colonne base: phi  c  cu  gamma  gamma_sat
    +Hoek (col 6-9): sigma_ci  GSI  mi  D
    """
    if not model.layers:
        raise ValueError("Modello senza strati")
    out = out_dir / f"{model.name}.geo"
    lines: list[str] = []
    for L in model.layers:
        if L.is_hoek():
            row = (f"{0.0:>8.2f} {0.0:>8.2f} {0.0:>8.2f} "
                   f"{L.gamma:>8.2f} {L.gamma_sat:>8.2f} "
                   f"{L.sigma_ci:>8.2f} {L.gsi:>6.1f} {L.mi:>6.1f} {L.disturbance:>6.2f}")
        else:
            row = (f"{L.phi:>8.2f} {L.c:>8.2f} {L.cu:>8.2f} "
                   f"{L.gamma:>8.2f} {L.gamma_sat:>8.2f}")
        lines.append(row)
    out.write_text("\n".join(lines) + "\n", encoding="ascii")
    return out


def write_svr(model: SlopeModel, out_dir: Path) -> Path | None:
    if not model.surcharges:
        return None
    out = out_dir / f"{model.name}.svr"
    lines = [
        f"  {s.x1:>10.4f} {s.x2:>10.4f} {s.q1:>10.2f} {s.q2:>10.2f} {s.angle_deg:>8.2f}"
        for s in model.surcharges
    ]
    out.write_text("\n".join(lines) + "\n", encoding="ascii")
    return out


def write_tir(model: SlopeModel, out_dir: Path) -> Path | None:
    """Scrive il file .TIR dei tiranti / chiodi.

    ⛔ SETTE colonne, non sei. Il manuale rel. 5.2 ne documenta 6 (la sesta e'
    la percentuale di lunghezza cementata), ma SSAP 6.1 ne scrive SETTE.

    Misurato il 2026-08-02 su tre commesse reali diverse (09/2025, 03/2025,
    12/2024-10/2025): tutti i file dal dic 2024 in poi hanno 7 colonne, tutti
    quelli fino al 2022 ne hanno 6.

    La settima colonna e' **K — Coefficiente di riduzione della Forza in Testa
    all'Ancoraggio**. Non e' nel manuale: lo dichiara il PROGRAMMA, nella
    «LEGENDA SIMBOLI» che chiude la TABELLA TIRANTI/ANCORAGGI di ogni report:
        K(-) : Coefficiente riduzione Forza in Testa Ancoraggio
    Non e' un default da lasciare com'e': si sceglie con criterio, come T e Lc.

    ⛔ Prima di leggere il report l'avevo dedotto per ANALOGIA (coefficiente di
    sfilamento, come il `fb` dei geosintetici) — ed era sbagliato. Le colonne
    non si indovinano dai valori: si leggono dalla legenda che SSAP stampa.
    """
    if not model.anchors:
        return None
    out = out_dir / f"{model.name}.tir"
    lines = [
        f"  {a.x:>10.4f} {a.y:>10.4f} {a.beta_deg:>8.2f} "
        f"{a.length:>8.2f} {a.T_design:>10.2f} {a.cemented_pct:>6.1f} "
        f"{a.K_riduzione_testa:>6.2f}"
        for a in model.anchors
    ]
    out.write_text("\n".join(lines) + "\n", encoding="ascii")
    return out


def write_mod(model: SlopeModel, out_dir: Path,
              dat_path: Path, geo_path: Path,
              fld_path: Path | None = None,
              svr_path: Path | None = None,
              tir_path: Path | None = None,
              grd_path: Path | None = None,
              pil_path: Path | None = None,
              liq_path: Path | None = None,
              jrc_path: Path | None = None,
              wrm_path: Path | None = None,
              utm_path: Path | None = None) -> Path:
    """Scrive il file master .MOD con flag e lista file.

    ⛔ DIECI flag, non nove. Il manuale rel. 5.2 (feb 2023) ne documenta 9, ma
    SSAP 6.1 ne scrive DIECI: il decimo dichiara il file **.UTM** con le
    coordinate georeferenziate.

    Accertato per differenza il 2026-08-02 su due modelli gemelli di una
    commessa reale (SP 8, ott 2025): quello con il decimo flag a 1 elenca un
    file in piu', `3003.utm` (EPSG:3003), l'altro no. Tutti i .MOD di tre
    commesse diverse dal dic 2024 in poi hanno dieci flag; tutti quelli fino al
    2022 ne hanno nove.

    La fonte autorevole del formato NON e' il manuale: e' cio' che il programma
    genera oggi. Il manuale e' fermo mentre il software e' andato avanti.
    """
    n_strati = len(model.layers)
    flags = [
        n_strati,
        1 if fld_path else 0,
        1 if svr_path else 0,
        1 if tir_path else 0,
        1 if grd_path else 0,
        1 if pil_path else 0,
        1 if liq_path else 0,
        1 if jrc_path else 0,
        1 if wrm_path else 0,
        1 if utm_path else 0,
    ]
    lines: list[str] = [" ".join(str(f) for f in flags)]
    # Ordine FISSO da manuale sez. 3.5.1:
    # 1.dat  2.fld  3.geo  4.svr  5.tir  6.grd  7.pil  8.liq  9.jrc  10.wrm
    lines.append(dat_path.name)
    if fld_path:
        lines.append(fld_path.name)
    lines.append(geo_path.name)
    if svr_path:
        lines.append(svr_path.name)
    if tir_path:
        lines.append(tir_path.name)
    if grd_path:
        lines.append(grd_path.name)
    if pil_path:
        lines.append(pil_path.name)
    if liq_path:
        lines.append(liq_path.name)
    if jrc_path:
        lines.append(jrc_path.name)
    if wrm_path:
        lines.append(wrm_path.name)
    if utm_path:
        lines.append(utm_path.name)

    out = out_dir / f"{model.name}.MOD"
    out.write_text("\n".join(lines) + "\n", encoding="ascii")
    return out


def write_all(model: SlopeModel, out_dir: Path) -> dict[str, Path]:
    """Scrive l'intero set di file per il modello. Restituisce dict path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    paths["dat"] = write_dat(model, out_dir)
    paths["geo"] = write_geo(model, out_dir)
    fld = write_fld(model, out_dir)
    if fld:
        paths["fld"] = fld
    svr = write_svr(model, out_dir)
    if svr:
        paths["svr"] = svr
    tir = write_tir(model, out_dir)
    if tir:
        paths["tir"] = tir
    paths["mod"] = write_mod(
        model, out_dir,
        dat_path=paths["dat"],
        geo_path=paths["geo"],
        fld_path=paths.get("fld"),
        svr_path=paths.get("svr"),
        tir_path=paths.get("tir"),
    )
    return paths


# ============================================================================
#                        VALIDATORI
# ============================================================================

def validate_topographic_surface(points: list[tuple[float, float]]) -> list[str]:
    """Controlli di base sulla superficie topografica (X strettamente crescenti)."""
    errors: list[str] = []
    if len(points) < 2:
        errors.append("Servono almeno 2 punti")
    for i in range(1, len(points)):
        if points[i][0] < points[i-1][0]:
            errors.append(f"X non crescenti tra punto {i-1} e {i}: {points[i-1][0]} -> {points[i][0]}")
    if any(x < 0 or y < 0 for x, y in points):
        errors.append("Coordinate negative non ammesse")
    if len(points) > 100:
        errors.append(f"SSAP ammette max 100 punti per superficie (trovati {len(points)})")
    return errors
