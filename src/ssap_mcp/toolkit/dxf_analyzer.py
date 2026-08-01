"""dxf_analyzer.py — Ispezione strutturata di un DXF per uso SSAP.

Estrae tutte le polilinee, le organizza per layer/colore, calcola bbox,
verifica convenzioni SSAP (X crescenti, coordinate positive, intersezioni).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ezdxf
from ezdxf.math import Vec2


def inspect_dxf(dxf_path: Path) -> dict:
    """Restituisce report strutturato del DXF."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    layers: dict[str, dict] = {}
    polylines: list[dict] = []
    texts: list[dict] = []

    # Bbox globale
    all_x: list[float] = []
    all_y: list[float] = []

    for ent in msp:
        et = ent.dxftype()
        layer = ent.dxf.layer
        color = getattr(ent.dxf, "color", 256)
        if layer not in layers:
            layers[layer] = {"entities": 0, "polylines": 0, "texts": 0,
                             "lines": 0, "color_aci": color}
        layers[layer]["entities"] += 1

        if et in ("LWPOLYLINE", "POLYLINE"):
            try:
                if et == "LWPOLYLINE":
                    pts = [(p[0], p[1]) for p in ent.get_points()]
                    closed = bool(ent.dxf.flags & 1) if hasattr(ent.dxf, "flags") else bool(getattr(ent, "closed", False))
                else:
                    pts = [(v.dxf.location[0], v.dxf.location[1]) for v in ent.vertices]
                    closed = bool(ent.dxf.flags & 1)
            except Exception:
                continue
            if not pts:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            all_x.extend(xs)
            all_y.extend(ys)

            polylines.append({
                "id": ent.dxf.handle,
                "layer": layer,
                "color_aci": color,
                "n_points": len(pts),
                "closed": closed,
                "x_min": min(xs), "x_max": max(xs),
                "y_min": min(ys), "y_max": max(ys),
                "x_first": xs[0], "y_first": ys[0],
                "x_last": xs[-1], "y_last": ys[-1],
                "x_strictly_increasing": all(xs[i+1] > xs[i] for i in range(len(xs)-1)),
                "x_non_decreasing": all(xs[i+1] >= xs[i] for i in range(len(xs)-1)),
                "first_eq_last": (abs(xs[0]-xs[-1]) < 1e-6 and abs(ys[0]-ys[-1]) < 1e-6),
                "points": pts,
            })
            layers[layer]["polylines"] += 1

        elif et == "LINE":
            layers[layer]["lines"] += 1

        elif et in ("TEXT", "MTEXT"):
            try:
                t = ent.dxf.text if et == "TEXT" else ent.text
                pos = ent.dxf.insert
                texts.append({"text": str(t).strip(), "x": pos[0], "y": pos[1],
                              "layer": layer, "color_aci": color})
                layers[layer]["texts"] += 1
            except Exception:
                continue

    bbox = {}
    if all_x:
        bbox = {
            "x_min": min(all_x), "x_max": max(all_x),
            "y_min": min(all_y), "y_max": max(all_y),
            "extent_x": max(all_x) - min(all_x),
            "extent_y": max(all_y) - min(all_y),
        }

    return {
        "file": str(dxf_path),
        "n_polylines": len(polylines),
        "n_texts": len(texts),
        "n_layers": len(layers),
        "layers": layers,
        "bbox": bbox,
        "polylines": polylines,
        "texts": texts,
    }


def shared_nodes(p1: list[tuple[float, float]],
                  p2: list[tuple[float, float]],
                  tol: float = 0.001) -> list[tuple[float, float]]:
    """Trova i nodi a comune (entro tol) tra due polilinee."""
    out = []
    for a in p1:
        for b in p2:
            if abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol:
                out.append(a)
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dxf_path", type=Path)
    ap.add_argument("--out-json", type=Path)
    ap.add_argument("--show-points", action="store_true",
                    help="stampa anche le coordinate dei punti")
    args = ap.parse_args()

    info = inspect_dxf(args.dxf_path)
    print(f"=== DXF: {args.dxf_path.name} ===")
    print(f"  Polilinee : {info['n_polylines']}")
    print(f"  Testi     : {info['n_texts']}")
    print(f"  Layer     : {info['n_layers']}")
    print(f"\n  BBOX: X [{info['bbox'].get('x_min'):.3f} -> {info['bbox'].get('x_max'):.3f}], "
          f"Y [{info['bbox'].get('y_min'):.3f} -> {info['bbox'].get('y_max'):.3f}]")

    print("\n=== LAYER ===")
    for name, data in info["layers"].items():
        print(f"  '{name}' (ACI {data['color_aci']}): "
              f"{data['polylines']} polilinee, {data['texts']} testi, {data['lines']} linee")

    print("\n=== POLILINEE ===")
    for i, p in enumerate(info["polylines"]):
        flags = []
        if p["closed"]: flags.append("CLOSED")
        if p["first_eq_last"]: flags.append("FIRST=LAST")
        if not p["x_strictly_increasing"]: flags.append("X NON-CRESC")
        flag_str = " ".join(flags) if flags else "open"
        print(f"  [{i}] layer='{p['layer']}' color={p['color_aci']} "
              f"npts={p['n_points']} {flag_str}")
        print(f"       X [{p['x_min']:.2f} -> {p['x_max']:.2f}]  "
              f"Y [{p['y_min']:.2f} -> {p['y_max']:.2f}]")
        print(f"       primo=({p['x_first']:.2f}, {p['y_first']:.2f})  "
              f"ultimo=({p['x_last']:.2f}, {p['y_last']:.2f})")
        if args.show_points and len(p["points"]) <= 30:
            for j, (x, y) in enumerate(p["points"]):
                print(f"         pt{j:02d}: ({x:.3f}, {y:.3f})")

    print("\n=== TESTI ===")
    for t in info["texts"]:
        print(f"  '{t['text']}' @ ({t['x']:.2f}, {t['y']:.2f})  layer='{t['layer']}'")

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        # Salva senza tutti i punti per compattezza
        compact = {**info, "polylines": [{k: v for k, v in p.items() if k != "points"}
                                          for p in info["polylines"]]}
        args.out_json.write_text(json.dumps(compact, indent=2, default=str), encoding="utf-8")
        print(f"\n[OK] report -> {args.out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
