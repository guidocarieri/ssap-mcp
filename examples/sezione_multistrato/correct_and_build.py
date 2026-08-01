"""correct_and_build.py — Pipeline completa per sezione multistrato:

  1. Legge il DXF importato dal DWG
  2. Applica le 2 correzioni convenzioni SSAP:
     - ERR A: aggiunge nodo a comune tra topografica e primo punto strato 1 intersecante
     - ERR B: estende falda fino all'estremo destro della topografica
  3. Salva DXF corretto (per riapertura in CAD)
  4. Genera modello SSAP (.MOD/.DAT/.GEO/.FLD) a 3 strati + falda
  5. Plot di confronto prima/dopo

Convenzione strati:
  Strato 1 (top, copertura superficiale)  : sopra il tetto strato 2 (ex layer '1')
  Strato 2 (sub, substrato)              : tra tetto strato 2 e bottom modello
  Strato 3 (lente, materiale problematico): poligono chiuso interno (ex layer '2')
"""

from __future__ import annotations

import sys
from pathlib import Path

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
TOOLKIT = HERE.parent.parent
sys.path.insert(0, str(TOOLKIT))

from modules.ssap_writer import (  # noqa: E402
    Layer, Surface, SlopeModel, write_all,
)
from modules.dxf_analyzer import inspect_dxf  # noqa: E402


def find_segment_at_x(points: list[tuple[float, float]], x: float, tol: float = 0.5) -> int | None:
    """Trova l'indice del segmento [i, i+1] che contiene la X target.
    Restituisce None se X non è dentro alcun segmento."""
    for i in range(len(points) - 1):
        x1, x2 = points[i][0], points[i + 1][0]
        if x1 - tol <= x <= x2 + tol:
            return i
    return None


def interpolate_y(points: list[tuple[float, float]], x: float) -> float:
    """Interpolazione lineare Y dato X su una segmentata."""
    i = find_segment_at_x(points, x)
    if i is None:
        raise ValueError(f"X={x} fuori range della segmentata")
    x1, y1 = points[i]
    x2, y2 = points[i + 1]
    if abs(x2 - x1) < 1e-9:
        return y1
    return y1 + (x - x1) / (x2 - x1) * (y2 - y1)


def insert_node_in_polyline(points: list[tuple[float, float]],
                             new_pt: tuple[float, float]) -> list[tuple[float, float]]:
    """Inserisce un nuovo nodo nella posizione X corretta (mantiene ordinamento X crescente)."""
    new_x = new_pt[0]
    out = list(points)
    # Trova posizione di inserimento
    insert_at = None
    for i, (x, _) in enumerate(out):
        if x > new_x:
            insert_at = i
            break
    if insert_at is None:
        out.append(new_pt)
    else:
        out.insert(insert_at, new_pt)
    return out


def shift_to_origin(layers_pts: dict[str, list[tuple[float, float]]],
                     padding_y_below: float = 30.0,
                     padding_xy_left: float = 5.0) -> dict[str, list[tuple[float, float]]]:
    """Trasla tutte le polilinee in modo che X_min ≥ padding_xy_left e
    che ci sia padding_y_below sotto il punto Y minimo (per spazio superfici di scivolamento)."""
    all_x = [x for pts in layers_pts.values() for x, _ in pts]
    all_y = [y for pts in layers_pts.values() for _, y in pts]
    x_min, y_min = min(all_x), min(all_y)
    dx = padding_xy_left - x_min  # shift X
    dy = padding_y_below - y_min  # shift Y (per Y_min finale = padding_y_below)
    return {layer: [(x + dx, y + dy) for x, y in pts] for layer, pts in layers_pts.items()}


def write_corrected_dxf(layers_pts: dict[str, list[tuple[float, float]]], out_path: Path) -> None:
    """Scrive un DXF con le polilinee corrette (1 polilinea per layer)."""
    doc = ezdxf.new(dxfversion="R2010", setup=True)
    msp = doc.modelspace()
    layer_colors = {"0": 8, "1": 30, "2": 3, "f": 5}  # ACI: gray, orange, green, blue
    for layer_name, pts in layers_pts.items():
        if layer_name not in doc.layers:
            doc.layers.add(name=layer_name, color=layer_colors.get(layer_name, 7))
        closed = (layer_name == "2")  # solo la lente è chiusa
        msp.add_lwpolyline(pts, dxfattribs={"layer": layer_name},
                            close=closed)
    doc.saveas(out_path)


def main() -> int:
    dxf_path = HERE / "input" / "sezione_sbagliata.dxf"
    out_dir = HERE / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # === 1. CARICAMENTO POLILINEE ===
    info = inspect_dxf(dxf_path)
    by_layer: dict[str, list[tuple[float, float]]] = {p["layer"]: p["points"] for p in info["polylines"]}
    topo = list(by_layer["0"])
    strato2_top = list(by_layer["1"])  # diventerà tetto strato 2
    lente = list(by_layer["2"])
    falda = list(by_layer["f"])

    print("=" * 70)
    print("CORREZIONE DXF - sezione multistrato")
    print("=" * 70)
    print(f"  Topografica (orig)  : {len(topo)} pt, X[{topo[0][0]:.2f} -> {topo[-1][0]:.2f}]")
    print(f"  Strato 2 top (orig) : {len(strato2_top)} pt")
    print(f"  Lente (orig)        : {len(lente)} pt")
    print(f"  Falda (orig)        : {len(falda)} pt")

    # === 2. CORREZIONE ERRORE A: nodo a comune ===
    print("\n--- ERRORE A: nodo a comune topografica/strato_2_top ---")
    first_st = strato2_top[0]
    y_topo_at_first = interpolate_y(topo, first_st[0])
    print(f"  Primo nodo strato_2_top : ({first_st[0]:.3f}, {first_st[1]:.3f})")
    print(f"  Y topo interpolata a X  : {y_topo_at_first:.3f}")
    delta_y = abs(y_topo_at_first - first_st[1])
    print(f"  Delta Y                 : {delta_y:.3f} m")

    if delta_y < 1.0:
        # Il nodo è geometricamente sulla topografica, manca solo l'esplicitazione
        new_node = (first_st[0], y_topo_at_first)
        topo_corrected = insert_node_in_polyline(topo, new_node)
        # Sostituisco anche primo punto strato_2_top con esattamente il nuovo nodo (per coerenza esatta)
        strato2_top_corrected = [new_node] + strato2_top[1:]
        print(f"  CORREZIONE: aggiunto nodo {new_node} alla topografica")
        print(f"  Topografica ora ha {len(topo_corrected)} punti")
    else:
        topo_corrected = topo
        strato2_top_corrected = strato2_top
        print("  (skip: delta troppo grande, serve revisione manuale)")

    # === 3. CORREZIONE ERRORE B: falda estesa ===
    print("\n--- ERRORE B: falda estesa per tutta larghezza ---")
    topo_x_max = topo_corrected[-1][0]
    falda_x_max = max(p[0] for p in falda)
    falda_corrected = list(falda)
    if topo_x_max - falda_x_max > 0.5:
        # estendo orizzontalmente con Y dell'ultimo punto
        last_y = falda[-1][1]
        falda_corrected.append((topo_x_max, last_y))
        print(f"  Aggiunto punto finale falda: ({topo_x_max:.3f}, {last_y:.3f})")

    # Idem a sinistra (per sicurezza)
    topo_x_min = topo_corrected[0][0]
    falda_x_min = min(p[0] for p in falda)
    if falda_x_min - topo_x_min > 0.5:
        first_y = falda[0][1]
        falda_corrected.insert(0, (topo_x_min, first_y))
        print(f"  Aggiunto punto iniziale falda: ({topo_x_min:.3f}, {first_y:.3f})")

    # === 3-bis. CORREZIONE ERRORE C: tetto strato 2 fino estremo destro topografica ===
    # Manuale App. L fig. L.4: lo strato intersecante deve avere il nodo estremo destro
    # coincidente con l'estremo destro della topografica (esce dal modello sul lato dx)
    print("\n--- ERRORE C: estensione strato 2 intersecante fino estremo destro topografica ---")
    last_st = strato2_top_corrected[-1]
    if abs(last_st[0] - topo_x_max) > 0.5:
        # estendo orizzontalmente con Y dell'ultimo punto
        strato2_top_corrected.append((topo_x_max, last_st[1]))
        print(f"  Ultimo nodo strato 2 era: ({last_st[0]:.3f}, {last_st[1]:.3f})")
        print(f"  Aggiunto nodo: ({topo_x_max:.3f}, {last_st[1]:.3f})")
        print(f"  -> strato 2 ora ha {len(strato2_top_corrected)} punti, X massima = topografica")
    else:
        print("  (già coincidente)")

    # === 4. CHIUSURA LENTE (assicuro primo == ultimo punto) ===
    print("\n--- Verifica lente: primo == ultimo? ---")
    lente_corrected = list(lente)
    first_l = lente_corrected[0]
    last_l = lente_corrected[-1]
    if abs(first_l[0] - last_l[0]) > 0.01 or abs(first_l[1] - last_l[1]) > 0.01:
        lente_corrected.append(first_l)
        print(f"  Aggiunto primo punto come ultimo per chiudere: {first_l}")
    else:
        print("  Lente già chiusa.")

    # === 5. TRASLAZIONE COORDINATE PER SSAP (origine vicina) ===
    layers_corrected = {
        "0": topo_corrected,
        "1": strato2_top_corrected,
        "2": lente_corrected,
        "f": falda_corrected,
    }
    layers_shifted = shift_to_origin(layers_corrected, padding_y_below=30.0, padding_xy_left=5.0)
    print("\n--- Traslazione coordinate per SSAP ---")
    print(f"  Origine X traslata: padding 5.0 m da X_min")
    print(f"  Padding Y: 30 m sotto Y_min (spazio per superfici scivolamento)")
    new_xs = [x for pts in layers_shifted.values() for x, _ in pts]
    new_ys = [y for pts in layers_shifted.values() for _, y in pts]
    print(f"  X range nuovo: [{min(new_xs):.2f}, {max(new_xs):.2f}]")
    print(f"  Y range nuovo: [{min(new_ys):.2f}, {max(new_ys):.2f}]")

    # === 6. SALVATAGGIO DXF CORRETTO ===
    dxf_out = out_dir / "sezione_corretta.dxf"
    write_corrected_dxf(layers_shifted, dxf_out)
    print(f"\n[OK] DXF corretto -> {dxf_out}")

    # === 7. PLOT CONFRONTO PRIMA/DOPO ===
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 11))
    colors = {"0": "saddlebrown", "1": "darkorange", "2": "darkgreen", "f": "blue"}
    labels = {"0": "Topografica", "1": "Tetto strato 2", "2": "Lente (chiusa)", "f": "Falda"}

    for ax, layers, title in [(ax1, by_layer, "PRIMA - DXF importato (con errori)"),
                                (ax2, layers_shifted, "DOPO - corretto e traslato per SSAP")]:
        for layer, pts in layers.items():
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            ax.plot(xs, ys, "-o", color=colors[layer], markersize=3, lw=1.3,
                    label=labels[layer])
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left")
        ax.set_title(title)
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")

    plt.tight_layout()
    fig_out = out_dir / "confronto_prima_dopo.png"
    plt.savefig(fig_out, dpi=130)
    plt.close()
    print(f"[OK] confronto -> {fig_out}")

    # === 8. GENERAZIONE MODELLO SSAP ===
    print("\n" + "=" * 70)
    print("GENERAZIONE MODELLO SSAP")
    print("=" * 70)

    # SSAP non accetta più di 100 punti per superficie
    def truncate(pts, n_max=80):
        if len(pts) <= n_max:
            return pts
        step = len(pts) / n_max
        idx = sorted(set([int(i * step) for i in range(n_max)] + [0, len(pts) - 1]))
        return [pts[i] for i in idx]

    topo_ssap = truncate(layers_shifted["0"])
    strato2_ssap = truncate(layers_shifted["1"])
    lente_ssap = layers_shifted["2"]  # lente già piccola, non tronco
    falda_ssap = truncate(layers_shifted["f"])

    # Definizione strati con parametri scelti
    layer_1_copertura = Layer(
        name="Copertura detritico-colluviale",
        phi=28.0, c=5.0, cu=0.0, gamma=19.0, gamma_sat=20.0,
    )
    layer_2_substrato = Layer(
        name="Substrato (argilla compatta o roccia alterata)",
        phi=32.0, c=25.0, cu=0.0, gamma=21.0, gamma_sat=22.0,
    )
    layer_3_lente = Layer(
        name="Lente argilla limosa (materiale problematico)",
        phi=22.0, c=12.0, cu=0.0, gamma=18.0, gamma_sat=19.0,
    )

    model = SlopeModel(
        name="sezione_multistrato",
        # Ordine SSAP: superficie 1 = topografica, sup 2 = tetto strato 2 intersecante, sup 3 = lente
        surfaces=[
            Surface(points=topo_ssap, kind="topo", name="topografica"),
            Surface(points=strato2_ssap, kind="normal", name="tetto_strato2"),
            Surface(points=lente_ssap, kind="lens", name="lente_strato3"),
        ],
        layers=[layer_1_copertura, layer_2_substrato, layer_3_lente],
        water_table=falda_ssap,
        notes=("Sezione multistrato corretta da DWG sbagliato. "
               "ERR A risolto: nodo a comune topo/strato2_top inserito. "
               "ERR B risolto: falda estesa fino a estremo destro topografica."),
    )

    paths = write_all(model, out_dir)
    print("\nFile SSAP generati:")
    for kind, p in paths.items():
        print(f"  .{kind.upper():3s}: {p.name}  ({p.stat().st_size} bytes)")

    print(f"\nContenuto .MOD:")
    print(paths["mod"].read_text(encoding="ascii"))

    print("\nIstruzioni:")
    print(f"  1. Apri SSAP2010 (Esegui come amministratore)")
    print(f"  2. MODELLO PENDIO -> CARICA -> {paths['mod']}")
    print(f"  3. Verifica preprocessing FASE 1 + FASE 2 (deve dare OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
