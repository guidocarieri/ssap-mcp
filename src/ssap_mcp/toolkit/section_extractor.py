"""section_extractor.py — Estrazione profilo topografico 2D da nuvola LAS lungo una traccia.

Workflow:
  1. Definisce traccia (P1, P2) in coordinate XY assolute
  2. Calcola progressiva s e distanza ortogonale d per ogni punto
  3. Filtra punti entro band_width/2 dalla traccia
  4. Proietta su piano (s, Z) traslando l'origine a P1
  5. Bin lungo s -> quota MAX per bin (skyline) o mediana
  6. Output: array (s, Z) decimato pronto per SSAP .DAT
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import laspy
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def project_to_section(xy: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Restituisce (s, d) — progressiva lungo P1->P2 e distanza ortogonale firmata."""
    v = p2 - p1
    L = np.linalg.norm(v)
    if L < 1e-9:
        raise ValueError("P1 e P2 coincidono")
    u = v / L  # versore traccia
    n = np.array([-u[1], u[0]])  # normale (sx)
    rel = xy - p1
    s = rel @ u
    d = rel @ n
    return s, d


def extract_section(
    las_path: Path,
    p1_xy: tuple[float, float],
    p2_xy: tuple[float, float],
    band_width: float = 4.0,
    bin_size: float = 0.5,
    skyline: str = "max",  # "max" | "median" | "min"
) -> dict:
    """Estrae profilo topografico lungo P1->P2.

    band_width: ampiezza fascia (m) — punti entro ±band_width/2 dalla traccia
    bin_size: dimensione bin lungo progressiva (m)
    skyline: come aggregare quote nel bin
    """
    p1 = np.asarray(p1_xy, dtype=float)
    p2 = np.asarray(p2_xy, dtype=float)
    L = float(np.linalg.norm(p2 - p1))
    half_band = band_width / 2.0

    # Streaming: leggo a chunk e filtro per non saturare RAM
    s_all, z_all = [], []
    n_total = 0
    n_kept = 0
    with laspy.open(str(las_path)) as f:
        for chunk in f.chunk_iterator(2_000_000):
            n_total += len(chunk.x)
            xy = np.column_stack([np.asarray(chunk.x), np.asarray(chunk.y)])
            z = np.asarray(chunk.z)
            s, d = project_to_section(xy, p1, p2)
            mask = (np.abs(d) <= half_band) & (s >= 0) & (s <= L)
            if mask.any():
                s_all.append(s[mask])
                z_all.append(z[mask])
                n_kept += int(mask.sum())

    if not s_all:
        raise RuntimeError("Nessun punto nella fascia di sezione")
    s_arr = np.concatenate(s_all)
    z_arr = np.concatenate(z_all)

    # Binning lungo progressiva
    n_bins = int(np.ceil(L / bin_size))
    edges = np.linspace(0, L, n_bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    profile_s, profile_z = [], []

    bin_idx = np.clip(np.searchsorted(edges, s_arr) - 1, 0, n_bins - 1)
    for i in range(n_bins):
        m = bin_idx == i
        if not m.any():
            continue
        zs = z_arr[m]
        if skyline == "max":
            zv = float(np.max(zs))
        elif skyline == "min":
            zv = float(np.min(zs))
        else:
            zv = float(np.median(zs))
        profile_s.append(float(centers[i]))
        profile_z.append(zv)

    return {
        "p1_xy": list(p1),
        "p2_xy": list(p2),
        "length_m": L,
        "band_width": band_width,
        "bin_size": bin_size,
        "skyline": skyline,
        "n_total_points": int(n_total),
        "n_points_in_band": int(n_kept),
        "n_bins_filled": len(profile_s),
        "profile_s": profile_s,
        "profile_z": profile_z,
    }


def smooth_profile(s: list[float], z: list[float], window: int = 5) -> list[float]:
    """Media mobile centrata. window dispari."""
    if window <= 1 or len(z) <= window:
        return list(z)
    arr = np.asarray(z)
    half = window // 2
    out = arr.copy()
    for i in range(half, len(arr) - half):
        out[i] = float(np.mean(arr[i - half : i + half + 1]))
    return out.tolist()


def to_ssap_origin(profile_s: list[float], profile_z: list[float]) -> tuple[list[float], list[float]]:
    """Trasla quota in modo che min(z) -> Y_offset >= 5.0 (SSAP esige tutte coords positive
    con un minimo "spazio" sotto il pendio per generare le superfici di scivolamento)."""
    z_min = min(profile_z)
    # Lascio 1.5x il dislivello sotto il punto più basso per dare spazio alle superfici
    z_range = max(profile_z) - z_min
    y_offset_below = max(20.0, 1.5 * z_range)
    y_shift = z_min - y_offset_below  # nuovo Y=0 sta y_offset_below sotto z_min
    new_z = [zz - y_shift for zz in profile_z]
    return list(profile_s), new_z


def plot_section(result: dict, out_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(result["profile_s"], result["profile_z"], "-", lw=1.2, color="saddlebrown")
    ax.fill_between(result["profile_s"], result["profile_z"], min(result["profile_z"]) - 5,
                     color="tan", alpha=0.3)
    ax.set_xlabel("Progressiva s [m]")
    ax.set_ylabel("Quota Z [m s.l.m.]")
    ax.set_title(f"Sezione {result['length_m']:.1f} m | banda ±{result['band_width']/2:.1f} m | bin {result['bin_size']:.2f} m")
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal")
    plt.tight_layout()
    plt.savefig(out_png, dpi=130)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("las_path", type=Path)
    ap.add_argument("--p1", type=float, nargs=2, required=True, metavar=("X1", "Y1"))
    ap.add_argument("--p2", type=float, nargs=2, required=True, metavar=("X2", "Y2"))
    ap.add_argument("--band", type=float, default=4.0)
    ap.add_argument("--bin", dest="bin_size", type=float, default=0.5)
    ap.add_argument("--skyline", choices=["max", "median", "min"], default="max")
    ap.add_argument("--smooth", type=int, default=0, help="finestra media mobile (0=off)")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--name", type=str, default="section")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Estrazione sezione P1={tuple(args.p1)} -> P2={tuple(args.p2)}")
    res = extract_section(args.las_path, tuple(args.p1), tuple(args.p2),
                          band_width=args.band, bin_size=args.bin_size, skyline=args.skyline)

    if args.smooth > 0:
        res["profile_z"] = smooth_profile(res["profile_s"], res["profile_z"], window=args.smooth)
        res["smoothing_window"] = args.smooth

    # Salvataggio versione "raw" e "ssap" (con Y traslato)
    s_ssap, z_ssap = to_ssap_origin(res["profile_s"], res["profile_z"])
    res["profile_s_ssap"] = s_ssap
    res["profile_z_ssap"] = z_ssap

    out_json = args.out_dir / f"{args.name}.json"
    out_json.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] profilo JSON -> {out_json}")
    print(f"     punti banda: {res['n_points_in_band']:,} / {res['n_total_points']:,}")
    print(f"     bins compilati: {res['n_bins_filled']}")
    print(f"     range Z (assoluta): {min(res['profile_z']):.2f} -> {max(res['profile_z']):.2f}")
    print(f"     range Y (SSAP): {min(z_ssap):.2f} -> {max(z_ssap):.2f}")

    out_png = args.out_dir / f"{args.name}.png"
    plot_section({**res, "profile_z": z_ssap}, out_png)
    print(f"[OK] grafico -> {out_png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
