"""SSAP MCP server — slope stability analysis pipeline.

Wraps the SSAP2010 toolkit modules (las_explorer, section_extractor,
ssap_writer, ssap_runner, ssap_parser) into MCP tools for automated
geotechnical slope stability verification.

Pipeline: LiDAR/DEM → section extraction → SSAP model → run → parse Fs
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ssap-mcp")

PACKAGE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = PACKAGE_DIR.parent.parent / "examples"


def _import_toolkit():
    """Lazy-import toolkit modules to avoid load-time dependency failures.

    The toolkit ships inside this package: no external path is required.
    """
    from .toolkit import (las_explorer, section_extractor, ssap_writer,
                          ssap_runner, ssap_parser, dxf_analyzer)
    return las_explorer, section_extractor, ssap_writer, ssap_runner, ssap_parser, dxf_analyzer



# ── Status ──

@mcp.tool()
def status() -> dict:
    """Check SSAP2010 installation and toolkit availability."""
    _, _, _, ssap_runner, _, _ = _import_toolkit()
    ok, msg = ssap_runner.check_ssap_install()
    tk = PACKAGE_DIR / "toolkit"
    modules = [f.stem for f in tk.glob("*.py") if f.stem != "__init__"]
    return {
        "ssap_installed": ok,
        "ssap_path": msg,
        "toolkit_path": str(tk),
        "toolkit_ok": tk.exists(),
        "modules": sorted(modules),
        "elevated": _is_elevated(),
        "note": "SSAP is GUI-driven and requires an interactive desktop session "
                "with elevation. This server is NOT headless.",
    }


# ── LAS Exploration ──

@mcp.tool()
def explore_point_cloud(
    las_file: str,
    sample_points: int = 0,
) -> dict:
    """Explore a LAS/LAZ point cloud: bounds, point count, Z range, CRS (header only, fast).
    With sample_points > 0 also loads a decimated sample and adds Z percentiles.
    Useful to understand the data before extracting a section."""
    las_explorer, _, _, _, _, _ = _import_toolkit()
    summary = las_explorer.header_summary(Path(las_file))
    result = {"ok": True, **summary}
    if sample_points and sample_points > 0:
        import numpy as np
        xyz = las_explorer.downsampled_xy(Path(las_file), target_points=sample_points)
        z = xyz[:, 2]
        result["sample"] = {
            "n_points": int(xyz.shape[0]),
            "z_p5": round(float(np.percentile(z, 5)), 2),
            "z_median": round(float(np.median(z)), 2),
            "z_p95": round(float(np.percentile(z, 95)), 2),
        }
    return result


# ── Section Extraction ──

@mcp.tool()
def extract_section_las(
    las_file: str,
    start_x: float, start_y: float,
    end_x: float, end_y: float,
    band_width: float = 4.0,
    bin_size: float = 0.5,
    skyline: str = "max",
    output_csv: str | None = None,
) -> dict:
    """Extract a 2D cross-section profile from a LAS/LAZ point cloud.
    Points within ±band_width/2 of the P1→P2 line are projected and binned
    along the chainage (bin_size, aggregation: max|median|min).
    NOTE: no classification filter is applied — pre-filter ground points
    (e.g. PDAL extract class 2) before calling if needed.
    Returns chainage-elevation pairs; optionally writes them to CSV (s,z)."""
    _, section_extractor, _, _, _, _ = _import_toolkit()
    result = section_extractor.extract_section(
        Path(las_file), (start_x, start_y), (end_x, end_y),
        band_width=band_width, bin_size=bin_size, skyline=skyline,
    )
    s, z = result["profile_s"], result["profile_z"]
    if output_csv:
        out = Path(output_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            "\n".join(f"{si:.3f},{zi:.3f}" for si, zi in zip(s, z)) + "\n",
            encoding="utf-8",
        )
    return {
        "ok": True,
        "n_bins_filled": result["n_bins_filled"],
        "n_points_in_band": result["n_points_in_band"],
        "length_m": round(result["length_m"], 2),
        "z_range": [round(min(z), 2), round(max(z), 2)] if z else [],
        "output_csv": output_csv,
        "profile_sample": list(zip(s[:10], z[:10])),
    }


@mcp.tool()
def extract_section_dem(
    dem_file: str,
    start_x: float, start_y: float,
    end_x: float, end_y: float,
    step: float = 1.0,
    output_csv: str | None = None,
) -> dict:
    """NOT IMPLEMENTED — the SSAP toolkit extracts sections from LAS/LAZ only.
    For DEM rasters use extract_section_las on the source cloud, or sample the
    DEM with GDAL-MCP (gdallocationinfo lungo la traccia) / PDAL pipeline."""
    return {
        "ok": False,
        "error": "extract_section_dem non supportato: il toolkit SSAP campiona solo "
                 "nuvole LAS/LAZ (section_extractor.extract_section). Usare "
                 "extract_section_las, oppure GDAL-MCP/PDAL-MCP per campionare il DEM.",
        "requested": {"dem_file": dem_file, "p1": [start_x, start_y],
                      "p2": [end_x, end_y], "step": step, "output_csv": output_csv},
    }


# ── Model Building ──

@mcp.tool()
def create_model(
    output_dir: str,
    model_name: str,
    layers: list[dict],
    profile_csv: str | None = None,
    profile_points: list[list[float]] | None = None,
    layer_surfaces: list[list[list[float]]] | None = None,
    water_table: list[list[float]] | None = None,
    surcharges: list[dict] | None = None,
) -> dict:
    """Create a complete SSAP model file set (.MOD + .DAT + .GEO + optional .FLD/.SVR)
    via the toolkit writer (ssap_writer.SlopeModel + write_all).

    layers: list of dicts — keys: name, phi (deg), c (kPa), cu (kPa), gamma,
            gamma_sat (kN/m3); Hoek-Brown: sigma_ci (MPa), gsi, mi, disturbance.
            Mohr-Coulomb: phi>0; Tresca: cu>0; Hoek-Brown: sigma_ci+gsi+mi>0.

    profile_csv: CSV file with chainage,elevation columns (output di extract_section_las)
    profile_points: alternativa inline [[x,z], ...] (superficie topografica)
    layer_surfaces: tetti degli strati sottostanti, uno per strato oltre il primo:
            [[[x,z],...], ...] (kind='normal', X crescenti)
    water_table: falda come spezzata [[x,z], ...] (scrive il .FLD)
    surcharges: [{x1,x2,q1,q2,angle_deg}] oppure legacy {x_start,x_end,load_kpa}
    """
    _, _, ssap_writer, _, _, _ = _import_toolkit()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    _LAYER_KEYS = {"name", "phi", "c", "cu", "gamma", "gamma_sat",
                   "sigma_ci", "gsi", "mi", "disturbance"}
    _ALIAS = {"GSI": "gsi", "D": "disturbance"}

    layer_objs = []
    for l in layers:
        norm = { _ALIAS.get(k, k): v for k, v in l.items() }
        unknown = set(norm) - _LAYER_KEYS
        if unknown:
            return {"ok": False,
                    "error": f"Chiavi layer non riconosciute: {sorted(unknown)}. "
                             f"Ammesse: {sorted(_LAYER_KEYS)} (MC: phi,c; Tresca: cu; "
                             f"Hoek-Brown: sigma_ci,gsi,mi,disturbance)."}
        layer_objs.append(ssap_writer.Layer(**norm))

    # superficie topografica dal CSV (s,z) o dai punti espliciti
    topo_pts: list[tuple[float, float]] = []
    if profile_points:
        topo_pts = [(float(p[0]), float(p[1])) for p in profile_points]
    elif profile_csv:
        for line in Path(profile_csv).read_text(encoding="utf-8-sig").splitlines():
            parts = line.replace(";", ",").split(",")
            if len(parts) >= 2:
                try:
                    topo_pts.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    continue  # header o riga non numerica
    if not topo_pts:
        return {"ok": False, "error": "Profilo topografico vuoto: fornire profile_csv "
                                      "(colonne s,z) oppure profile_points [[x,z],...]."}

    surfaces = [ssap_writer.Surface(points=topo_pts, kind="topo", name="topografia")]
    for i, pts in enumerate(layer_surfaces or []):
        surfaces.append(ssap_writer.Surface(
            points=[(float(p[0]), float(p[1])) for p in pts],
            kind="normal", name=f"tetto_strato_{i + 2}",
        ))

    warnings = ssap_writer.validate_topographic_surface(topo_pts)

    sur_objs = []
    for s in (surcharges or []):
        if "x1" in s:
            sur_objs.append(ssap_writer.Surcharge(**s))
        else:  # chiavi legacy x_start/x_end/load_kpa
            sur_objs.append(ssap_writer.Surcharge(
                x1=float(s["x_start"]), x2=float(s["x_end"]),
                q1=float(s["load_kpa"]), q2=float(s["load_kpa"]),
            ))

    wt = [(float(p[0]), float(p[1])) for p in water_table] if water_table else None

    model = ssap_writer.SlopeModel(
        name=model_name,
        surfaces=surfaces,
        layers=layer_objs,
        water_table=wt,
        surcharges=sur_objs,
    )

    paths = ssap_writer.write_all(model, out)
    return {
        "ok": True,
        "output_dir": str(out),
        "files": {k: str(p) for k, p in paths.items()},
        "n_layers": len(layer_objs),
        "n_surfaces_geo": len(surfaces),
        "validation_warnings": warnings,
        "engine_note": "Calculation method and search engine are NOT set here: "
                       "they live in the .PAR settings file. Use "
                       "`set_analysis_options` to choose them, then "
                       "`run_verification`. Always confirm what was actually "
                       "used by reading the final report (`read_report`).",
    }


# ── Run SSAP ──

@mcp.tool()
def run_analysis(
    mod_file: str,
    timeout: int = 1800,
    wait_for_output: bool = True,
) -> dict:
    """Launch SSAP2010 analysis on a .MOD file (ssap_runner.launch_with_model).
    SSAP requires UAC elevation — the GUI will open and the user must click AVVIO.
    With wait_for_output=True the tool monitors the .MOD folder for results
    (DXF, PDF, ANOMALY.LOG) until timeout; otherwise returns right after launch."""
    _, _, _, ssap_runner, _, _ = _import_toolkit()
    result = ssap_runner.launch_with_model(
        Path(mod_file), wait_for_output=wait_for_output, timeout_s=timeout,
    )
    return {
        "ok": result.started,
        "pid": result.pid,
        "work_dir": str(result.work_dir),
        "found_outputs": [str(f) for f in result.found_outputs],
        "anomaly_log": str(result.anomaly_log) if result.anomaly_log else None,
        "elapsed_s": round(result.elapsed_s, 1),
        "note": result.note,
    }


# ── Parse Results ──

@mcp.tool()
def parse_results(
    output_dir: str,
) -> dict:
    """Parse SSAP verification output: extract Fs values, critical surface geometry, anomalies.
    Reads DXF result, PDF report, and ANOMALY.LOG from the output directory."""
    _, _, _, _, ssap_parser, _ = _import_toolkit()
    result = ssap_parser.parse_run_outputs(Path(output_dir))
    return {
        "ok": True,
        "fs_values": result.fs_values,
        "fs_min": min(result.fs_values) if result.fs_values else None,
        "critical_surface": {
            "fs": result.critical_surface.fs,
            "method": result.critical_surface.method,
            "n_points": len(result.critical_surface.points),
        } if result.critical_surface else None,
        "anomalies": result.anomalies,
        "dxf_path": str(result.dxf_path) if result.dxf_path else None,
        "pdf_path": str(result.pdf_path) if result.pdf_path else None,
        "anomaly_log": str(result.anomaly_log) if result.anomaly_log else None,
        "notes": result.notes,
    }


# ── DXF Section Analysis ──

@mcp.tool()
def analyze_section_dxf(
    dxf_file: str,
) -> dict:
    """Analyze a DXF section file: extract polylines, identify layers/strata boundaries,
    measure distances and elevations. Useful for importing existing sections into SSAP."""
    _, _, _, _, _, dxf_analyzer = _import_toolkit()
    result = dxf_analyzer.inspect_dxf(Path(dxf_file))
    return {
        "ok": True,
        "file": result.get("file", dxf_file),
        "layer_count": result.get("n_layers", 0),
        "polyline_count": result.get("n_polylines", 0),
        "text_count": result.get("n_texts", 0),
        "bounds": result.get("bbox", {}),
        "layers": list(result.get("layers", {}).keys()),
        "polylines_summary": [
            {"layer": p["layer"], "n_points": p["n_points"],
             "closed": p["closed"], "x_min": p["x_min"], "x_max": p["x_max"],
             "y_min": p["y_min"], "y_max": p["y_max"]}
            for p in result.get("polylines", [])
        ],
    }


# ── Utility ──

@mcp.tool()
def list_examples() -> dict:
    """List available SSAP example projects bundled with this package."""
    examples_dir = Path(os.environ.get("SSAP_EXAMPLES", EXAMPLES_DIR))
    if not examples_dir.exists():
        return {"ok": False, "error": "Examples directory not found"}
    examples = []
    for d in examples_dir.iterdir():
        if d.is_dir():
            files = [f.name for f in d.iterdir()]
            examples.append({"name": d.name, "files": files})
    return {"ok": True, "examples": examples}


# ── Unattended verification (no human clicks) ──
#
# ⛔ NOT HEADLESS. SSAP is a GUI program: it needs an interactive desktop
# session and elevation. "No human clicks" is not the same as "no desktop".
# Four commands stay bound to the window (load model, load settings, start,
# make report) and are driven by Win32 messages (PostMessage/BM_CLICK) —
# never by synthetic mouse or keyboard input, so the machine stays usable.
#
# Why this exists next to `run_analysis`: that one only OPENS SSAP with the
# model and leaves the start to the user. This one runs the whole verification.
# Three findings make it possible, all measured on a real slope section:
#
#  1. The two buttons of the «AVVIO VERIFICA» group are OWNER-DRAWN: the label
#     is painted, the window text is EMPTY. Looking them up by caption never
#     finds them. They are located by GEOMETRY inside the group rectangle.
#  2. The end of the computation is read from the INVERSION of the button
#     states (running: global disabled + STOP enabled; finished: the other way
#     round). NOT from CPU time, and NOT from the "verification is running…"
#     hint, which stays on screen after the computation has stopped.
#  3. The result is read from the REPORT, never from the `.tmp` files or from
#     `temp_critzon.dxf`: those are MID-RUN SNAPSHOTS — a 0.018 difference on
#     Fs was measured between the temporary file and the report of the very
#     same verification.
#
# Elevation: SSAP runs elevated, and because of UIPI a non-elevated process
# cannot post messages to an elevated window. So either this server itself runs
# elevated (simplest: start your MCP client as administrator), or you point
# SSAP_ELEVATED_RUNNER at a helper that executes an elevated PowerShell script
# — which is how the author avoids a UAC prompt on every run. Optional.

SSAP_EXE = Path(os.environ.get("SSAP_EXE", r"C:\SSAP2010\ssap2010_64bit.exe"))
PYTHON_ELEVATO = os.environ.get("SSAP_PYTHON", sys.executable)

_runner_env = os.environ.get("SSAP_ELEVATED_RUNNER")
RUNNER = Path(_runner_env) if _runner_env else None
RUNNER_TASK = os.environ.get("SSAP_RUNNER_TASK", "SSAP-ElevatedRunner")


def _is_elevated() -> bool:
    """True if this process already has administrator rights."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _esegui_elevato(righe: list[str], timeout_s: int) -> dict:
    """Esegue PowerShell elevato via l'attivita' pianificata dello Studio.

    ⛔ `result.txt` viene AZZERATO prima di partire: un'uscita vecchia si legge
    identica a una nuova, ed e' cosi' che il 2026-07-28 ho preso l'output di
    sette minuti prima per la risposta a una domanda appena posta (il task e' a
    istanza singola e il mio avvio era stato RIFIUTATO, in silenzio).
    """
    import subprocess
    import time as _t

    if RUNNER is None:
        return {"ok": False, "error": "SSAP_ELEVATED_RUNNER is not configured"}
    cmd_ps = RUNNER / "command.ps1"
    res = RUNNER / "result.txt"
    if not cmd_ps.parent.exists():
        return {"ok": False, "error": f"elevated runner not found: {RUNNER}"}

    stato = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         f"(Get-ScheduledTask -TaskName '{RUNNER_TASK}').State"],
        capture_output=True, text=True)
    if "Running" in stato.stdout:
        return {"ok": False, "error": "il runner elevato e' gia' occupato "
                                      "(istanza singola): riprova a corsa finita"}

    res.write_text("", encoding="utf-8")
    cmd_ps.write_text("\n".join(righe) + "\n", encoding="utf-8")
    subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                    f"Start-ScheduledTask -TaskName '{RUNNER_TASK}'"],
                   capture_output=True, text=True)

    t0 = _t.time()
    while _t.time() - t0 < timeout_s:
        _t.sleep(5)
        if res.exists() and res.stat().st_size > 0:
            _t.sleep(2)
            return {"ok": True, "output": res.read_text(encoding="utf-8",
                                                        errors="replace"),
                    "elapsed_s": round(_t.time() - t0, 1)}
    return {"ok": False, "error": f"nessuna uscita entro {timeout_s} s"}


def _run_here(model_dir: Path, model_name: str, timeout_s: int) -> dict:
    """Run the verification in this process tree (already elevated)."""
    import subprocess
    import time as _t

    t0 = _t.time()
    try:
        chk = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq ssap2010_64bit.exe"],
            capture_output=True, text=True)
        if "ssap2010_64bit" not in chk.stdout:
            if not SSAP_EXE.exists():
                return {"ok": False, "error": f"SSAP not found: {SSAP_EXE}"}
            subprocess.Popen([str(SSAP_EXE)], cwd=str(SSAP_EXE.parent))
            _t.sleep(12)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"cannot start SSAP: {e}"}

    env = dict(os.environ)
    env["SSAP_DIR"] = str(model_dir)
    env["SSAP_NOME"] = model_name
    env["SSAP_MAX_SECONDI"] = str(timeout_s)
    try:
        p = subprocess.run(
            [str(PYTHON_ELEVATO), str(PACKAGE_DIR / "corsa.py")],
            env=env, capture_output=True, text=True, timeout=timeout_s + 120)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"no result within {timeout_s + 120} s"}
    return {"ok": True,
            "output": (p.stdout or "") + (p.stderr or ""),
            "elapsed_s": round(_t.time() - t0, 1)}


# ── Analysis options: the .PAR is the channel ──

METHODS = {1: "Spencer", 2: "Sarma I", 3: "Morgenstern-Price",
           4: "Chen-Morgenstern", 5: "Sarma II", 6: "Janbu rigorous",
           7: "Borselli 2016"}
ENGINES = {1: "Random Search", 2: "Convex Random Search",
           3: "Sniff Random Search", 4: "New Random Search",
           5: "Mixed Engines Search"}


@mcp.tool()
def set_analysis_options(par_file: str, method: int, engine: int) -> dict:
    """Choose calculation method and search engine by writing the .PAR file.

    This is the channel that makes batch work possible: method and engine are
    stored in the .PAR settings file in clear text, so they can be written and
    SSAP obeys. Everything else in the file is left untouched.

    Format is `LABEL\\n VALUE`: the label line is located and the FOLLOWING line
    is rewritten. Replacing by blind line number would overwrite whatever comes
    first, which may be a different parameter.

    ⛔ A value the program does not accept is ignored SILENTLY. Never trust this
    call alone: after the run, read the final report with `read_report` and
    compare `metodo` / `motore_ricerca` with what you asked for. The report is
    the only authoritative statement of what was actually used.

    ⚠️ Old .PAR files (SSAP 5.x) carry outdated label ranges. Regenerate the
    file by loading the .MOD in a current SSAP and saving the settings again.
    """
    if method not in METHODS:
        return {"ok": False, "error": f"method must be one of {sorted(METHODS)}"}
    if engine not in ENGINES:
        return {"ok": False, "error": f"engine must be one of {sorted(ENGINES)}"}

    p = Path(par_file)
    if not p.exists():
        return {"ok": False, "error": f"not found: {p}"}

    lines = p.read_text(encoding="latin-1").splitlines()
    touched = 0
    for i, line in enumerate(lines):
        if line.startswith("METODO DI CALCOLO [") and i + 1 < len(lines):
            lines[i + 1] = str(method)
            touched += 1
        elif line.startswith("MOTORE DI RICERCA [") and i + 1 < len(lines):
            lines[i + 1] = str(engine)
            touched += 1
    if touched != 2:
        return {"ok": False,
                "error": f"found {touched} of the 2 expected labels in {p.name}; "
                         f"file left untouched"}
    p.write_text("\n".join(lines) + "\n", encoding="latin-1")
    return {"ok": True, "par_file": str(p),
            "method": method, "method_name": METHODS[method],
            "engine": engine, "engine_name": ENGINES[engine],
            "verify": "read_report() after the run and compare — a rejected "
                      "value is ignored without any error"}


@mcp.tool()
def run_verification(
    model_dir: str,
    model_name: str,
    timeout: int = 1800,
) -> dict:
    """Esegue una VERIFICA GLOBALE SSAP dall'inizio alla fine, SENZA CLICK UMANI.

    Carica <model_name>.MOD e <model_name>.par dalla cartella indicata, avvia la
    verifica globale, attende che il programma dichiari di aver finito, genera il
    report e ne estrae l'Fs minimo. Avvia SSAP se non e' gia' aperto.

    A differenza di `run_analysis` (che apre e basta), qui non serve nessuno
    davanti allo schermo. Richiede il runner elevato dello Studio.

    Ritorna: fs_min, n_superfici, report_path, log della corsa.
    """
    import re as _re

    d = Path(model_dir)
    if not (d / f"{model_name}.MOD").exists():
        return {"ok": False, "error": f"manca {model_name}.MOD in {d}"}
    if not (d / f"{model_name}.par").exists():
        return {"ok": False, "error": f"manca {model_name}.par in {d} "
                                      f"(le impostazioni sono obbligatorie)"}

    if _is_elevated():
        r = _run_here(d, model_name, timeout)
    elif RUNNER is not None:
        righe = [
            f"if (-not (Get-Process ssap2010_64bit -ErrorAction SilentlyContinue)) {{",
            f"  Start-Process -FilePath '{SSAP_EXE}' "
            f"-WorkingDirectory '{SSAP_EXE.parent}' -WindowStyle Minimized",
            f"  Start-Sleep -Seconds 12",
            f"}}",
            f"$env:SSAP_DIR = '{d}'",
            f"$env:SSAP_NOME = '{model_name}'",
            f"$env:SSAP_MAX_SECONDI = '{timeout}'",
            f"& '{PYTHON_ELEVATO}' '{PACKAGE_DIR / 'corsa.py'}' 2>&1",
        ]
        r = _esegui_elevato(righe, timeout + 120)
    else:
        return {
            "ok": False,
            "error": "SSAP runs elevated and, because of UIPI, a non-elevated "
                     "process cannot drive its window. Either start this MCP "
                     "server as administrator, or set SSAP_ELEVATED_RUNNER to "
                     "a helper that runs an elevated PowerShell script.",
            "elevated": False,
        }
    if not r.get("ok"):
        return r

    out = r["output"]
    m = _re.search(r"FS_MIN=([0-9.]+)", out)
    n = _re.search(r"superfici = (\d+)", out)
    rep = d / f"report_{model_name}.txt"
    return {
        "ok": m is not None,
        "fs_min": float(m.group(1)) if m else None,
        "n_superfici": int(n.group(1)) if n else None,
        "report_path": str(rep) if rep.exists() else None,
        "elapsed_s": r["elapsed_s"],
        "log": out,
        "nota": "Fs letto dal REPORT di fine corsa, non dai file temporanei",
    }


@mcp.tool()
def read_report(report_file: str) -> dict:
    """Legge un report di verifica SSAP (.txt) ed estrae i valori che contano.

    E' la fonte AUTOREVOLE dell'Fs: `parse_results` legge DXF/PDF, che durante
    una verifica globale sono istantanee parziali e riportano un Fs diverso da
    quello finale.
    """
    import re as _re

    p = Path(report_file)
    if not p.exists():
        return {"ok": False, "error": f"non esiste: {p}"}
    t = p.read_bytes().decode("latin-1")

    fs = _re.search(r"#FS_minimo\s*#Fattore di sicurezza\(FS\)=\s*([0-9.]+)", t)
    lam = _re.search(r"#FS_minimo.*?#Lambda=\s*([0-9.\-]+)", t)
    tot = _re.search(r"TOTALE SUPERFICI GENERATE\s*:\s*(\d+)", t)
    met = _re.search(r"METODO DI CALCOLO\s*:\s*(.+)", t)
    mot = _re.search(r"MOTORE DI RICERCA:\s*(.+)", t)
    kh = _re.search(r"COEFFICIENTE SISMICO UTILIZZATO Kh\s*:\s*([0-9.]+)", t)
    tutti = [float(x) for x in _re.findall(
        r"#Fattore di sicurezza\(FS\)=\s*([0-9.]+)", t)]

    return {
        "ok": fs is not None,
        "fs_min": float(fs.group(1)) if fs else None,
        "lambda": float(lam.group(1)) if lam else None,
        "fs_10_peggiori": sorted(tutti) if tutti else [],
        "n_superfici_generate": int(tot.group(1)) if tot else None,
        "metodo": met.group(1).strip() if met else None,
        "motore_ricerca": mot.group(1).strip() if mot else None,
        "kh": float(kh.group(1)) if kh else None,
        "report_path": str(p),
    }


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
