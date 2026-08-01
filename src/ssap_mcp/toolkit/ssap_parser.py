"""ssap_parser.py — Lettura output SSAP (DXF risultato, PDF report, ANOMALY.LOG).

Estrae:
- Fs minimo dalla prima riga del DXF risultato (testo etichetta)
- Geometria della superficie critica (LWPOLYLINE in layer dedicato)
- Anomalie da ANOMALY.LOG
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf


@dataclass
class CriticalSurface:
    fs: float | None = None
    method: str = ""
    points: list[tuple[float, float]] = field(default_factory=list)
    layer_name: str = ""


@dataclass
class VerificationOutput:
    dxf_path: Path | None = None
    pdf_path: Path | None = None
    anomaly_log: Path | None = None
    fs_values: list[float] = field(default_factory=list)
    critical_surface: CriticalSurface | None = None
    anomalies: list[str] = field(default_factory=list)
    raw_text_blocks: list[str] = field(default_factory=list)
    notes: str = ""


# regex per Fs nei testi DXF/PDF SSAP
FS_PATTERNS = [
    re.compile(r"\bFs\s*[=:]\s*([0-9]+\.[0-9]+)", re.IGNORECASE),
    re.compile(r"\bFS\s*[=:]\s*([0-9]+\.[0-9]+)"),
    re.compile(r"Fattore\s+di\s+sicurezza[^0-9]*([0-9]+\.[0-9]+)", re.IGNORECASE),
    re.compile(r"Safety\s+Factor[^0-9]*([0-9]+\.[0-9]+)", re.IGNORECASE),
]

METHOD_PATTERNS = [
    re.compile(r"(Spencer|Morgenstern[- ]Price|Janbu|Sarma|Bishop|Borselli|Chen[- ]Morgenstern)",
               re.IGNORECASE),
]


def parse_dxf(dxf_path: Path) -> VerificationOutput:
    """Estrae Fs, metodo e geometria superficie critica da DXF SSAP."""
    out = VerificationOutput(dxf_path=dxf_path)
    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        out.notes = f"DXF non leggibile: {e}"
        return out
    msp = doc.modelspace()

    # Estrai TUTTI i testi: TEXT + MTEXT
    texts: list[str] = []
    for ent in msp:
        try:
            if ent.dxftype() == "TEXT":
                t = ent.dxf.text
                texts.append(t)
            elif ent.dxftype() == "MTEXT":
                t = ent.text  # contiene le formattazioni MTEXT
                texts.append(t)
        except Exception:
            continue
    out.raw_text_blocks = texts

    fs_set: list[float] = []
    method = ""
    for t in texts:
        for pat in FS_PATTERNS:
            for m in pat.finditer(t):
                try:
                    fs_set.append(float(m.group(1)))
                except ValueError:
                    pass
        if not method:
            for pat in METHOD_PATTERNS:
                m = pat.search(t)
                if m:
                    method = m.group(1)
                    break
    # Fs minimo è quello più piccolo > 0
    valid = [f for f in fs_set if 0 < f < 100]
    if valid:
        out.fs_values = sorted(set(round(v, 4) for v in valid))

    # Cerca polilinee in layer "critic" / "FS_min" / simili (heuristica)
    critical: CriticalSurface | None = None
    for ent in msp:
        if ent.dxftype() != "LWPOLYLINE":
            continue
        layer = ent.dxf.layer.lower()
        if any(k in layer for k in ("critic", "fs_min", "minimum", "scivol")):
            pts = [(p[0], p[1]) for p in ent.get_points()]
            critical = CriticalSurface(
                fs=min(valid) if valid else None,
                method=method,
                points=pts,
                layer_name=ent.dxf.layer,
            )
            break

    if critical:
        out.critical_surface = critical
    elif valid:
        out.critical_surface = CriticalSurface(
            fs=min(valid), method=method, points=[], layer_name=""
        )

    return out


def parse_anomaly_log(log_path: Path) -> list[str]:
    """Estrae messaggi di anomalia leggibili dal file ANOMALY.LOG."""
    if not log_path.exists():
        return []
    try:
        text = log_path.read_text(encoding="latin-1", errors="ignore")
    except Exception as e:
        return [f"Errore lettura: {e}"]
    # split su righe non vuote/separatori
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines


def parse_run_outputs(work_dir: Path) -> VerificationOutput:
    """Scansiona la cartella di lavoro e ricostruisce l'esito di una verifica.

    Cerca:
      - *.dxf più recente (output verifica)
      - *.pdf più recente (report)
      - ANOMALY.LOG
    """
    work_dir = work_dir.resolve()
    dxfs = sorted(work_dir.glob("*.dxf"), key=lambda p: p.stat().st_mtime, reverse=True)
    pdfs = sorted(work_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    anomaly = work_dir / "ANOMALY.LOG"
    if not anomaly.exists():
        anomaly = work_dir / "anomaly.log"

    if dxfs:
        out = parse_dxf(dxfs[0])
    else:
        out = VerificationOutput(notes="Nessun DXF trovato nella cartella")

    if pdfs:
        out.pdf_path = pdfs[0]
    if anomaly.exists():
        out.anomaly_log = anomaly
        out.anomalies = parse_anomaly_log(anomaly)
    return out
