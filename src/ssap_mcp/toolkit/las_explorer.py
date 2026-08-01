"""las_explorer.py — Esplorazione metadati nuvola LAS senza caricamento integrale.

Legge l'header, calcola bbox/statistiche, e produce una vista in pianta decimata
(point density map) per supportare la scelta della traccia di sezione.
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


def header_summary(path: Path) -> dict:
    """Legge header LAS e ritorna metadati essenziali (no point loading)."""
    with laspy.open(str(path)) as f:
        h = f.header
        return {
            "file": str(path),
            "size_MB": round(path.stat().st_size / 1024 / 1024, 1),
            "point_count": int(h.point_count),
            "point_format_id": int(h.point_format.id),
            "version": f"{h.version.major}.{h.version.minor}",
            "scales": [float(s) for s in h.scales],
            "offsets": [float(o) for o in h.offsets],
            "x_min": float(h.mins[0]),
            "y_min": float(h.mins[1]),
            "z_min": float(h.mins[2]),
            "x_max": float(h.maxs[0]),
            "y_max": float(h.maxs[1]),
            "z_max": float(h.maxs[2]),
            "extent_x_m": round(float(h.maxs[0] - h.mins[0]), 2),
            "extent_y_m": round(float(h.maxs[1] - h.mins[1]), 2),
            "extent_z_m": round(float(h.maxs[2] - h.mins[2]), 2),
            "crs_wkt": _try_get_crs(h),
        }


def _try_get_crs(header) -> str:
    """Estrae CRS dal LAS se presente in VLR/EVLR."""
    try:
        vlrs = list(header.vlrs)
        for v in vlrs:
            wkt = getattr(v, "string", None) or getattr(v, "parsed_record", None)
            if wkt and "PROJCS" in str(wkt):
                return str(wkt)[:200]
    except Exception:
        pass
    return ""


def downsampled_xy(path: Path, target_points: int = 200_000) -> np.ndarray:
    """Carica una versione decimata della nuvola (solo XY+Z) per overview rapida.

    Usa chunking laspy: legge a blocchi e prende 1 punto ogni stride per
    rimanere sotto target_points totali."""
    with laspy.open(str(path)) as f:
        total = f.header.point_count
        stride = max(1, total // target_points)
        out = []
        for chunk in f.chunk_iterator(2_000_000):
            xs = np.asarray(chunk.x)
            ys = np.asarray(chunk.y)
            zs = np.asarray(chunk.z)
            out.append(np.column_stack([xs[::stride], ys[::stride], zs[::stride]]))
        return np.vstack(out)


def plot_overview(xyz: np.ndarray, out_png: Path, title: str = "") -> None:
    """Salva PNG vista in pianta colorata per quota."""
    fig, ax = plt.subplots(figsize=(10, 10))
    sc = ax.scatter(xyz[:, 0], xyz[:, 1], c=xyz[:, 2], s=0.3, cmap="terrain")
    plt.colorbar(sc, ax=ax, label="Z [m]")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_aspect("equal")
    ax.set_title(title or out_png.stem)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_png, dpi=120)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("las_path", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--target-points", type=int, default=200_000)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    info = header_summary(args.las_path)
    info_path = args.out_dir / "header.json"
    info_path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] header -> {info_path}")
    print(json.dumps({k: v for k, v in info.items() if k != "crs_wkt"}, indent=2))

    xyz = downsampled_xy(args.las_path, args.target_points)
    print(f"[OK] decimato a {len(xyz)} punti")
    overview = args.out_dir / "overview.png"
    plot_overview(xyz, overview, title=args.las_path.stem)
    print(f"[OK] overview -> {overview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
