"""parse_results.py — legge esito verifica SSAP sulla sezione multistrato."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLKIT = HERE.parent.parent
sys.path.insert(0, str(TOOLKIT))

from modules.ssap_parser import parse_run_outputs  # noqa: E402


def main() -> int:
    work_dir = HERE / "output"
    out = parse_run_outputs(work_dir)

    print("=" * 70)
    print(f"VERIFICA SSAP - sezione multistrato")
    print(f"Cartella: {work_dir}")
    print("=" * 70)

    if out.dxf_path:
        sz = out.dxf_path.stat().st_size // 1024
        print(f"\nDXF risultato: {out.dxf_path.name} ({sz} KB)")

    print(f"\nFs rilevati nei testi DXF: {out.fs_values}")

    if out.critical_surface and out.critical_surface.fs is not None:
        cs = out.critical_surface
        print(f"\n--- SUPERFICIE CRITICA ---")
        print(f"  Fs minimo : {cs.fs}")
        print(f"  Metodo    : {cs.method or '(non rilevato)'}")
        if cs.points:
            print(f"  Punti     : {len(cs.points)}")
            xs = [p[0] for p in cs.points]
            ys = [p[1] for p in cs.points]
            print(f"  X range   : {min(xs):.2f} -> {max(xs):.2f}")
            print(f"  Y range   : {min(ys):.2f} -> {max(ys):.2f}")

    if out.anomalies:
        print(f"\n--- ANOMALY.LOG ({len(out.anomalies)} righe, prime 30) ---")
        for ln in out.anomalies[:30]:
            print(f"  {ln}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
