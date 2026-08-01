# ssap-mcp

An [MCP](https://modelcontextprotocol.io) server that drives **SSAP2010** — the
*Slope Stability Analysis Program* by Prof. Lorenzo Borselli — so that an AI
assistant can prepare a model, choose the calculation method and the search
engine, run the verification and read the resulting factor of safety.

> **Not affiliated with the author of SSAP.** SSAP2010 is free software by
> Prof. Lorenzo Borselli (<https://www.ssap.eu>), it is *not* open source, and
> its redistribution is not permitted. This repository contains **no part of
> SSAP**: it drives a copy you install yourself.

---

## ⛔ Read this first: it is NOT headless

This is the single most important limitation, and the one most easily
misunderstood.

SSAP is a GUI program. It offers **no command line, no batch mode and no
scripting interface** in its public release — verified against the whole
511-page manual of rel. 5.2 and the official website. Therefore this server
needs, on the same machine:

- SSAP2010 **installed** (download it from <https://www.ssap.eu>);
- an **interactive desktop session** — a real, logged-in Windows desktop.
  It will not work on a headless server, in a container, or over a session
  with no window station;
- **elevation**: SSAP runs elevated, and because of Windows UIPI a
  non-elevated process cannot post messages to an elevated window.

"No human clicks" is **not** the same as "no desktop". Everything here happens
on a visible desktop; what the server removes is the need for a human to sit
in front of it.

What it does *not* do: it never simulates mouse clicks or keystrokes. The four
window-bound commands (load model, load settings, start verification, make
report) are driven with Win32 messages (`PostMessage`/`BM_CLICK`), so your
mouse, keyboard and focus stay yours while a run is in progress.

## How it works

The key is that **the channel is the file, not the GUI**. The calculation
method and the search engine are stored in clear text inside the `.PAR`
settings file: they can be written, and SSAP obeys.

```
create_model  →  set_analysis_options  →  run_verification  →  read_report
   .MOD/.DAT/.GEO     writes the .PAR       runs SSAP          Fs + what
                                                               was really used
```

⛔ **Always close the loop on the report.** A value the program does not accept
is ignored *silently* — no error, no warning. `read_report` extracts the
`METODO DI CALCOLO` and `MOTORE DI RICERCA` lines from the final report: those
are the only authoritative statement of what was actually used. Never trust the
file you wrote; trust the report SSAP wrote back.

⛔ **The `.tmp` files and `temp_*.dxf` are not results.** They are mid-run
snapshots. A difference of 0.018 on Fs was measured between a temporary file
and the report of the very same verification. The report is written only on
request, and only once the computation has finished.

## Install

```bash
git clone https://github.com/guidocarieri/ssap-mcp
cd ssap-mcp
uv sync
```

Register it with your MCP client (paths are examples):

```json
{
  "mcpServers": {
    "ssap": {
      "command": "uv",
      "args": ["--directory", "C:/path/to/ssap-mcp", "run", "ssap-mcp"]
    }
  }
}
```

**Start the client as administrator**, so the server inherits elevation. If you
would rather not see a UAC prompt on every run, point `SSAP_ELEVATED_RUNNER` at
your own helper that executes an elevated PowerShell script — optional, and not
required for the server to work.

### Environment variables

| variable | default | meaning |
|---|---|---|
| `SSAP_EXE` | `C:\SSAP2010\ssap2010_64bit.exe` | path to the SSAP executable |
| `SSAP_PYTHON` | the running interpreter | interpreter used for the run helper |
| `SSAP_ELEVATED_RUNNER` | *(unset)* | optional helper for elevation without UAC |
| `SSAP_EXAMPLES` | bundled `examples/` | where to look for example projects |

## Tools

| tool | what it does |
|---|---|
| `status` | SSAP install, bundled toolkit, whether this process is elevated |
| `explore_point_cloud` | inspect a LAS/LAZ cloud before extracting a section |
| `extract_section_las` / `extract_section_dem` | build a 2D profile from a cloud or a DEM |
| `analyze_section_dxf` | read polylines and layers from an existing DXF section |
| `create_model` | write the `.MOD` / `.DAT` / `.GEO` model files |
| `set_analysis_options` | **choose method and search engine** by writing the `.PAR` |
| `run_verification` | full run without human clicks, returns the minimum Fs |
| `run_analysis` | older path: opens SSAP with the model, you press start |
| `read_report` | authoritative Fs, method and engine, read from the report |
| `parse_results` | read DXF/PDF outputs of a run |
| `list_examples` | list the bundled example projects |

### Methods and engines

| method | | engine | |
|---|---|---|---|
| 1 | Spencer | 1 | Random Search |
| 2 | Sarma I | 2 | Convex Random Search |
| 3 | Morgenstern-Price | 3 | Sniff Random Search |
| 4 | Chen-Morgenstern | 4 | New Random Search |
| 5 | Sarma II | 5 | Mixed Engines Search |
| 6 | Janbu rigorous | | |
| 7 | Borselli 2016 | | |

⚠️ **Old `.PAR` files carry outdated label ranges.** A settings file produced by
SSAP 5.x declares fewer methods and engines than the current program accepts.
Regenerate it: load the `.MOD` in a current SSAP, save the settings again, and
use that file as your template.

## What this is for, and what it is not

The manual (§ 2.6.6) advises that *a complete and reliable verification may
require testing more than one search engine in succession*. By hand that means
one session per engine, which in practice nobody does. Automated, it is machine
time — and running every method and every engine, repeatedly, becomes routine.

Two cautions that matter more than the code:

- **Repetitions are not a luxury.** The surface search is pseudo-random: two
  identical runs do not return the same number. Conclusions drawn from a single
  run per configuration have been measured to reverse once repeated.
- **Automation does not improve the input.** A deterministic solver fed with
  unrealistic parameters returns a perfectly computed, perfectly wrong number —
  faster. The geologist's judgement on stratigraphy, parameters and groundwater
  is not something this tool provides, and the responsibility for accepting a
  result stays with whoever signs it.

## Credits

SSAP2010 is developed by **Prof. Lorenzo Borselli** (Instituto de Geología /
Facultad de Ingeniería, Universidad Autónoma de San Luis Potosí, Mexico) and is
distributed free of charge at <https://www.ssap.eu>. All credit for the
analysis engine belongs to him; this repository only automates its operation.

## Licence

MIT — see [LICENSE](LICENSE). The licence covers this code only, never SSAP.
