# -*- coding: utf-8 -*-
"""Regression tests for defects found by running SSAP on real models.

Every test here corresponds to a defect that actually occurred on 2026-08-01,
with the data that revealed it. None of them needs SSAP installed: they cover
the parts that can be checked without a desktop session. The ones that DO need
SSAP live in tests/integrazione/.

Run:  python -m pytest tests/ -v      (or: python tests/test_difetti_trovati.py)
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from ssap_mcp import server  # noqa: E402
from ssap_mcp.congruenza import verifica  # noqa: E402


# --------------------------------------------------------------------------
# Defect 1 — command injection through single quotes in a path
# --------------------------------------------------------------------------

def test_quoting_ordinary_path():
    assert server._psq(r"C:\lavori\sezione") == r"'C:\lavori\sezione'"


def test_quoting_apostrophe_in_folder_name():
    """The realistic case is not an attack: `l'argine`, `Sant'Anna`.

    A single-quoted PowerShell string ends at the first quote and the rest is
    parsed as CODE — in a command that runs elevated.
    """
    assert server._psq(r"C:\lavori\l'argine") == r"'C:\lavori\l''argine'"


def test_quoting_neutralises_injection():
    out = server._psq(r"C:\a'; calc.exe; '")
    # every inner quote doubled -> the whole thing stays one literal string
    assert out.startswith("'") and out.endswith("'")
    assert "''" in out
    inner = out[1:-1]
    assert inner.count("'") % 2 == 0, "odd number of quotes would break the string"


# --------------------------------------------------------------------------
# Defect 4 — the calculation-method table was wrong for six values out of seven
# --------------------------------------------------------------------------

def test_method_table_matches_what_ssap_reports():
    """Measured by running each value and reading the report back.

    The earlier hand-written table started at Spencer; SSAP numbers Janbu
    rigorous first. Asking for Janbu would have been answered "Spencer" — and
    Janbu returns about 2.5% lower than the other six, so the number changed too.
    """
    atteso = {
        1: "janbu", 2: "spencer", 3: "sarma i",
        4: "morgenstern-price", 5: "chen-morgenstern",
        6: "sarma ii", 7: "borselli",
    }
    for numero, frammento in atteso.items():
        assert frammento in server.METHODS[numero].lower(), (
            f"method {numero} should be {frammento}, "
            f"got {server.METHODS[numero]}")


def test_engine_table():
    for numero, frammento in {1: "random search", 2: "convex",
                              3: "sniff", 4: "new random",
                              5: "mixed engines"}.items():
        assert frammento in server.ENGINES[numero].lower()


def test_set_analysis_options_rejects_out_of_range():
    with tempfile.TemporaryDirectory() as d:
        par = pathlib.Path(d) / "x.par"
        par.write_text("METODO DI CALCOLO [1 2 3 4 5 6 7]\n2\n"
                       "MOTORE DI RICERCA [1 2 3 4]\n3\n", encoding="latin-1")
        assert server.set_analysis_options(str(par), 8, 3)["ok"] is False
        assert server.set_analysis_options(str(par), 2, 9)["ok"] is False


def test_set_analysis_options_writes_the_line_after_the_label():
    """Format is LABEL\\nVALUE: the line AFTER the label is rewritten.

    Replacing by blind line number would hit whatever comes first — and the
    .par contains a second label starting the same way, METODO DI CALCOLO
    PALIFICATE, which is a different parameter entirely.
    """
    with tempfile.TemporaryDirectory() as d:
        par = pathlib.Path(d) / "x.par"
        par.write_text(
            "METODO DI CALCOLO [1 2 3 4 5 6 7]\n1\n"
            "MOTORE DI RICERCA [1 2 3 4]\n1\n"
            "METODO DI CALCOLO PALIFICATE[1,2]\n1\n", encoding="latin-1")
        r = server.set_analysis_options(str(par), 6, 4)
        assert r["ok"], r
        righe = par.read_text(encoding="latin-1").splitlines()
        assert righe[1] == "6", "calculation method not written"
        assert righe[3] == "4", "search engine not written"
        assert righe[5] == "1", "PALIFICATE method must NOT be touched"


def test_set_analysis_options_refuses_a_file_without_both_labels():
    with tempfile.TemporaryDirectory() as d:
        par = pathlib.Path(d) / "x.par"
        originale = "METODO DI CALCOLO [1 2 3 4 5 6 7]\n1\n"
        par.write_text(originale, encoding="latin-1")
        r = server.set_analysis_options(str(par), 3, 2)
        assert r["ok"] is False
        assert par.read_text(encoding="latin-1") == originale, \
            "the file must be left untouched when the labels are incomplete"


# --------------------------------------------------------------------------
# Defect 3 — a .PAR belongs to its model: it carries the search window
# --------------------------------------------------------------------------

def _scrivi(d: pathlib.Path, x0: float, x1: float,
            lim1: float, lim2: float):
    dat = d / "m.dat"
    dat.write_text(
        "intestazione 1\nintestazione 2\nintestazione 3\n"
        f"{x0:.2f} 10.00\n{(x0+x1)/2:.2f} 15.00\n{x1:.2f} 20.00\n",
        encoding="latin-1")
    par = d / "m.par"
    par.write_text(
        f"LIMITE1 superiore  m\n{lim1:.2f}\n"
        f"LIMITE2 superiore- m\n{lim2:.2f}\n", encoding="latin-1")
    return par, dat


def test_par_of_another_model_is_rejected():
    """The exact case of 2026-08-01: limits at X~1974..2036 on a slope from
    10 to 35 m. SSAP raised «Invalid floating point operation» and offered to
    "ignore and risk data corruption"."""
    with tempfile.TemporaryDirectory() as d:
        par, dat = _scrivi(pathlib.Path(d), 10, 35, 1973.63, 2035.61)
        g = verifica(par, dat)
        assert g["ok"] is False
        assert "non c'e' pendio" in g["motivo"]


def test_par_of_its_own_model_is_accepted():
    with tempfile.TemporaryDirectory() as d:
        par, dat = _scrivi(pathlib.Path(d), 40, 110, 48.40, 108.60)
        assert verifica(par, dat)["ok"] is True


def test_zero_is_not_a_chainage():
    """0.00 means "not set", not "search at the origin". Treating it as a
    coordinate rejected legitimate example files."""
    with tempfile.TemporaryDirectory() as d:
        par, dat = _scrivi(pathlib.Path(d), 20, 54, 0.0, 53.18)
        assert verifica(par, dat)["ok"] is True


def test_run_verification_stops_before_launching_ssap():
    """The check must fire BEFORE opening SSAP, not be discovered downstream."""
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        par, dat = _scrivi(p, 10, 35, 1973.63, 2035.61)
        (p / "caso.MOD").write_text("1 0 0 0 0 0 0 0 0\nm.dat\nm.geo\n",
                                    encoding="latin-1")
        (p / "caso.par").write_text(par.read_text(encoding="latin-1"),
                                    encoding="latin-1")
        r = server.run_verification(model_dir=str(p), model_name="caso",
                                    timeout=5)
        assert r["ok"] is False
        assert "non appartiene a questo modello" in r["error"]
        assert "rimedio" in r


# --------------------------------------------------------------------------
# Defect 7 — anchors were unreachable: write_tir() existed, create_model
#            never exposed it
# --------------------------------------------------------------------------

def test_create_model_writes_anchors():
    with tempfile.TemporaryDirectory() as d:
        r = server.create_model(
            output_dir=d, model_name="m",
            layers=[{"name": "a", "phi": 30.0, "c": 5.0},
                    {"name": "b", "cu": 40.0},
                    {"name": "r", "sigma_ci": 25.0, "gsi": 45.0, "mi": 10.0}],
            profile_points=[[0, 10], [20, 16], [40, 22]],
            layer_surfaces=[[[0, 8], [20, 14], [40, 20]],
                            [[0, 5], [20, 11], [40, 17]]],
            anchors=[{"x": 20.0, "y": 16.0, "beta_deg": -15.0,
                      "length": 14.0, "T_design": 80.0}],
        )
        assert r["ok"], r
        assert r["n_anchors"] == 1
        tir = pathlib.Path(d) / "m.tir"
        assert tir.exists(), "the .TIR file was not written"
        assert "-15.00" in tir.read_text(encoding="latin-1")
        # the .MOD must DECLARE anchors: 4th of the nine flags
        mod = next(pathlib.Path(d).glob("*.MOD"))
        flag = mod.read_text(encoding="latin-1").splitlines()[0].split()
        assert flag[3] == "1", f"anchors not declared in the .MOD: {flag}"


def test_geo_writes_three_material_kinds():
    """Mohr-Coulomb 5 columns; Tresca phi=c=0 cu>0; Hoek-Brown 9 columns."""
    with tempfile.TemporaryDirectory() as d:
        server.create_model(
            output_dir=d, model_name="m",
            layers=[{"name": "incoerente", "phi": 33.0, "c": 0.0},
                    {"name": "non drenato", "cu": 42.0},
                    {"name": "roccia", "sigma_ci": 25.0, "gsi": 45.0,
                     "mi": 10.0}],
            profile_points=[[0, 10], [40, 22]],
            layer_surfaces=[[[0, 8], [40, 20]], [[0, 5], [40, 17]]],
        )
        righe = [r.split() for r in
                 (pathlib.Path(d) / "m.geo").read_text(
                     encoding="latin-1").splitlines() if r.split()]
        assert len(righe[0]) == 5 and float(righe[0][0]) == 33.0
        assert len(righe[1]) == 5 and float(righe[1][2]) == 42.0
        assert len(righe[2]) == 9, "Hoek-Brown must have 9 columns"
        assert float(righe[2][0]) == 0.0 and float(righe[2][5]) == 25.0


if __name__ == "__main__":
    falliti = 0
    for nome, fn in sorted(globals().items()):
        if not nome.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"  OK   {nome}")
        except AssertionError as e:
            falliti += 1
            print(f"  FAIL {nome}: {e}")
        except Exception as e:  # noqa: BLE001
            falliti += 1
            print(f"  ERR  {nome}: {type(e).__name__}: {e}")
    print(f"\n{'tutti passati' if not falliti else str(falliti) + ' falliti'}")
    raise SystemExit(1 if falliti else 0)
