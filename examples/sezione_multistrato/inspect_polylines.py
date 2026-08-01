"""inspect_polylines.py — dump dei punti reali delle 4 polilinee + check errori SSAP."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLKIT = HERE.parent.parent
sys.path.insert(0, str(TOOLKIT))

from modules.dxf_analyzer import inspect_dxf, shared_nodes  # noqa: E402

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main() -> int:
    dxf_path = HERE / "input" / "sezione_sbagliata.dxf"
    info = inspect_dxf(dxf_path)

    # Mappa per layer
    by_layer: dict[str, list[tuple[float, float]]] = {}
    for p in info["polylines"]:
        by_layer[p["layer"]] = p["points"]

    print("=" * 78)
    print("DUMP COMPLETO POLILINEE")
    print("=" * 78)

    for layer in sorted(by_layer.keys()):
        pts = by_layer[layer]
        print(f"\n--- LAYER '{layer}' ({len(pts)} punti) ---")
        for i, (x, y) in enumerate(pts):
            print(f"  pt{i:02d}: X={x:>10.3f}  Y={y:>10.3f}")

    # Verifica errori
    print("\n" + "=" * 78)
    print("CHECK ERRORI SSAP (App. L manuale)")
    print("=" * 78)

    topo = by_layer.get("0", [])
    strato1 = by_layer.get("1", [])
    lente = by_layer.get("2", [])
    falda = by_layer.get("f", [])

    # ERRORE A: strato intersecante con nodo iniziale NON a comune con topografica
    if topo and strato1:
        first_st = strato1[0]
        last_st = strato1[-1]
        # Cerco se primo o ultimo punto di strato1 sia a comune con la topografica
        match_first = None
        match_last = None
        for tp in topo:
            if abs(tp[0] - first_st[0]) <= 0.5 and abs(tp[1] - first_st[1]) <= 0.5:
                match_first = tp
            if abs(tp[0] - last_st[0]) <= 0.5 and abs(tp[1] - last_st[1]) <= 0.5:
                match_last = tp
        print(f"\n[strato 1 intersecante]")
        print(f"  Primo punto strato1: ({first_st[0]:.3f}, {first_st[1]:.3f})")
        print(f"    -> nodo a comune con topografica? {'SI ' + str(match_first) if match_first else 'NO !!!'}")
        print(f"  Ultimo punto strato1: ({last_st[0]:.3f}, {last_st[1]:.3f})")
        print(f"    -> nodo a comune con topografica? {'SI ' + str(match_last) if match_last else 'NO'}")

    # ERRORE B: falda non estesa per tutta la larghezza del pendio
    if topo and falda:
        topo_x_min, topo_x_max = topo[0][0], topo[-1][0]
        falda_x_min = min(p[0] for p in falda)
        falda_x_max = max(p[0] for p in falda)
        print(f"\n[falda 'f']")
        print(f"  Topografica X: [{topo_x_min:.3f}, {topo_x_max:.3f}]")
        print(f"  Falda      X: [{falda_x_min:.3f}, {falda_x_max:.3f}]")
        gap_left = falda_x_min - topo_x_min
        gap_right = topo_x_max - falda_x_max
        print(f"  Gap a sinistra: {gap_left:.3f} m  (deve essere <= 0)")
        print(f"  Gap a destra:   {gap_right:.3f} m  (deve essere <= 0)")
        if gap_right > 0.5 or gap_left > 0.5:
            print(f"  >>> ERRORE: falda NON copre tutta la larghezza del pendio!")

    # ERRORE C: lente - verifica senso rotazione (antiorario richiesto)
    if lente:
        # Calcolo segno area con shoelace
        area2 = 0.0
        for i in range(len(lente) - 1):
            area2 += lente[i][0] * lente[i+1][1] - lente[i+1][0] * lente[i][1]
        # Se area2 > 0 -> antiorario, < 0 -> orario
        first_eq_last = (abs(lente[0][0] - lente[-1][0]) < 0.5 and
                         abs(lente[0][1] - lente[-1][1]) < 0.5)
        print(f"\n[lente layer '2']")
        print(f"  Primo == ultimo punto? {first_eq_last}")
        print(f"  Area firmata (shoelace): {area2/2:.3f} m^2")
        print(f"  Senso: {'ANTIORARIO (corretto SSAP)' if area2 > 0 else 'ORARIO (NON CONFORME)'}")

    # Plot di riepilogo
    fig, ax = plt.subplots(figsize=(14, 6))
    colors = {"0": "saddlebrown", "1": "darkorange", "2": "darkgreen", "f": "blue"}
    labels = {"0": "Topografica (layer 0)", "1": "Strato 1 (layer 1)",
              "2": "Lente (layer 2)", "f": "Falda (layer f)"}
    for layer, pts in by_layer.items():
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, "-o", color=colors.get(layer, "gray"), markersize=3, lw=1.2,
                label=labels.get(layer, f"layer {layer}"))
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_title("Sezione importata da DWG - polilinee per layer")
    out_png = HERE / "input" / "sezione_dump.png"
    plt.tight_layout()
    plt.savefig(out_png, dpi=130)
    plt.close()
    print(f"\n[OK] plot -> {out_png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
