# ssap-mcp

*[Questa pagina in italiano](README.it.md) — SSAP is written by an Italian author
and most of its users are Italian, so this document exists in both languages.
Please read the Italian page rather than machine-translating this one: the method
names are surnames, and translation turns Price into a price.*

An [MCP](https://modelcontextprotocol.io) server that drives **SSAP2010** — the
*Slope Stability Analysis Program* by Prof. Lorenzo Borselli — so that an AI
assistant can prepare a model, choose the calculation method and the search
engine, run the verification and read the resulting factor of safety.

> **Not affiliated with the author of SSAP.** SSAP2010 is free software by
> Prof. Lorenzo Borselli (<https://www.ssap.eu>), it is *not* open source, and
> its redistribution is not permitted. This repository contains **no part of
> SSAP**: it drives a copy that you download and install yourself.

**Tested against SSAP's own models.** All **20** verification cases in
[`tests/CAMPAGNA.md`](tests/CAMPAGNA.md) reach a result — nineteen of them are
models shipped with SSAP2010, so anyone who has it installed can repeat the whole
campaign and check the numbers. Every factor of safety is read from the final
report, and the pairs behave as they should: anchors on a rock slope **+22.8%**,
liquefaction **−44.2%**, drained against undrained **−27.5%**. Where a comparison
is not sound it says so: two of them are marked *not valid* and one result
*unexplained*, instead of being quietly left out.

---

## ⛔ Read this first: this is **not** a way to run SSAP without a screen

This is the single most important limitation, and the one most easily
misunderstood, so it is stated in plain words before anything else.

In computing, a program is called **headless** when it can run with no screen and
nobody watching — you type a command, it works in the background, and it can
therefore run on a rented server, inside a container, or overnight on a machine
nobody is logged into. **SSAP is not such a program, and this server does not
make it one.**

SSAP is a graphical program. In its public release it has **no command line, no
batch mode and no scripting interface** — verified against the whole 511-page
manual of rel. 5.2 and the official website. Consequently this server needs, on
the same computer:

- SSAP2010 **installed** (download it from <https://www.ssap.eu>);
- a **real, logged-in Windows desktop**. Not a remote machine with nobody logged
  in, not a container, not a background service: SSAP's own window must actually
  exist somewhere on a screen, even if nobody is looking at it;
- **administrator rights**, for the reason explained in the table below.

So the promise here is *"nobody has to sit and click"*, **not** *"no screen is
needed"*. The two sound similar and are completely different. What disappears is
the human operator, not the desktop.

One thing it deliberately does **not** do: it never simulates mouse clicks or
keystrokes. The four operations that must go through SSAP's window (load model,
load settings, start verification, produce report) are performed by sending
Windows messages directly to the buttons (`PostMessage`/`BM_CLICK`). Your mouse,
your keyboard and your active window remain yours while a verification is
running — you can keep working on something else.

## How it works

The idea that makes this possible: **SSAP is instructed through its files, not
through its menus.** The calculation method and the search engine are stored as
plain text inside the `.PAR` settings file. They can be written there directly,
and SSAP obeys what it finds. The window is only used to press *start*.

```
create_model  →  set_analysis_options  →  run_verification  →  read_report
   .MOD/.DAT/.GEO     writes the .PAR       runs SSAP          Fs + which method
                                                               was really used
```

⛔ **Never trust the file you wrote — always check the report SSAP wrote back.**
If you put a value SSAP does not accept into the `.PAR`, it is ignored *in
silence*: no error message, no warning, and the verification runs with something
other than what you asked for. `read_report` therefore extracts the
`METODO DI CALCOLO` and `MOTORE DI RICERCA` lines from the final report, which
are the only trustworthy statement of what was actually used. Reading it back is
not a formality: it is the only way to know.

⛔ **The `.tmp` files and `temp_*.dxf` are not the results.** They are snapshots
taken while the computation is still running. On one and the same verification, a
temporary file and the final report differed by 0.018 on Fs. The real report is
written only when you ask for it, and only after the computation has finished.

## What you need before you start

This is not a program you download and double-click. It is a **server that an AI
assistant talks to**: on its own it has no window, no menu and no command line,
and it does nothing until an assistant calls it. Here is the complete chain of
things you need, stated in full so that nobody discovers a missing piece halfway
through.

| you need | why it is needed | note |
|---|---|---|
| **Windows** | SSAP2010 exists only for Windows, and this server does nothing but drive SSAP | no macOS, no Linux, not even inside a container |
| **SSAP2010, installed by you** | this repository does not include SSAP and is not allowed to: the author distributes it himself and does not permit redistribution. This server only drives a copy that is already on your computer | free download at <https://www.ssap.eu>. Developed and tested against **6.1 build 15998** |
| **a logged-in Windows desktop** | SSAP has no command line, so the only way to start a verification is to press a button in its window — and that window can only exist on a real desktop session | it will not work on a headless server, as a background service, or on a machine where nobody is logged in |
| **administrator rights** | SSAP runs with elevated privileges. Windows deliberately forbids a normal program from sending commands to the window of an elevated one (a protection called UIPI), so a non-elevated server simply cannot press SSAP's buttons | start your MCP client as administrator |
| **Python 3.12 or newer** | the server is written in Python | <https://www.python.org> |
| **uv** (or pip) | to install the dependencies | <https://docs.astral.sh/uv/> |
| **an MCP client** | MCP is a protocol: this server only answers requests, it never starts anything by itself. The client is the program that actually calls it | e.g. Claude Desktop, Claude Code, or any other program that speaks MCP |
| **an account with an AI assistant that supports MCP** | the client needs a model behind it to decide what to ask for | this normally means a **paid subscription**, and it is a real recurring cost |

⛔ **Be clear about the last two rows.** Without an MCP client *and* a model
behind it, this repository does nothing whatsoever — there is no interface of its
own to fall back on. And if all you want is to run a single verification, SSAP on
its own does it better and faster than any of this: it was designed for that, and
its own interface is the right tool. This project earns its keep only when you
have to run *many* verifications one after another — every method against every
engine, say, or the same slope with twenty parameter sets — or when the
verification has to sit inside a longer chain of processing that is already
automated.

Dependencies installed automatically: `mcp`, `ezdxf`, `numpy`, `laspy`,
`matplotlib`.

## Install

```bash
git clone https://github.com/guidocarieri/ssap-mcp
cd ssap-mcp
uv sync
```

Then register it with your MCP client (the paths below are examples — use your
own):

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

**Start the client as administrator**, so that the server inherits those rights
(see the table above for why they are needed). If you would rather not confirm a
Windows security prompt at every run, point `SSAP_ELEVATED_RUNNER` at a helper of
your own that executes an elevated PowerShell script — this is optional, and the
server works without it.

### Environment variables

| variable | default | meaning |
|---|---|---|
| `SSAP_EXE` | `C:\SSAP2010\ssap2010_64bit.exe` | where the SSAP executable is |
| `SSAP_PYTHON` | the interpreter in use | interpreter used for the run helper |
| `SSAP_ELEVATED_RUNNER` | *(not set)* | optional helper to obtain administrator rights without a prompt |
| `SSAP_EXAMPLES` | the bundled `examples/` | where to look for example projects |

## Tools

These are the operations the assistant can call. Names in `code` are the ones it
uses; you never type them yourself.

| tool | what it does |
|---|---|
| `status` | reports whether SSAP is installed, whether the toolkit loaded, and whether this process has administrator rights |
| `explore_point_cloud` | reads the header of a LAS/LAZ point cloud — extent, number of points, elevation range, coordinate system — before anything heavier is attempted |
| `extract_section_las` | cuts a 2D ground profile out of a point cloud, which becomes the geometry of the slope |
| `extract_section_dem` | the same from a raster elevation model — **not implemented**: it returns an explicit error and points at the GDAL/PDAL alternatives |
| `analyze_section_dxf` | reads polylines and layers from a section you already drew in CAD |
| `create_model` | writes the model files SSAP reads: `.MOD`, `.DAT`, `.GEO`, plus the optional ones for water table, surcharges, anchors and reinforcements |
| `set_analysis_options` | **chooses the calculation method and the search engine**, by writing them into the `.PAR` settings file |
| `run_verification` | the complete run, with no human clicks: it closes any open SSAP, checks that the settings belong to this model, starts a fresh instance, waits, and returns the minimum factor of safety |
| `run_analysis` | the older, half-manual route: it opens SSAP with the model loaded and leaves the *start* button to you |
| `read_report` | reads the final report and returns the factor of safety together with the method and engine **actually** used |
| `parameter_glossary` | explains what each parameter in the report means, quoting the legend SSAP itself prints under every table |
| `parse_results` | reads the DXF and PDF files produced by a run |
| `list_examples` | lists the example projects bundled here |

### Calculation methods and search engines

The numbers in the first column are the **codes** to pass to
`set_analysis_options` — the same numbers SSAP stores in the `.PAR` file. They
were verified one by one by running each and reading back the method name from
the report, because the labels written inside older settings files are wrong.

**`method` — the limit-equilibrium method used to compute Fs:**

| code | method | after |
|---|---|---|
| 1 | <code translate="no">Janbu rigorous</code> | Janbu, 1973 |
| 2 | <code translate="no">Spencer</code> | Spencer, 1973 |
| 3 | <code translate="no">Sarma I</code> | Sarma, 1973 |
| 4 | <code translate="no">Morgenstern-Price</code> | Morgenstern &amp; Price, 1965 |
| 5 | <code translate="no">Chen-Morgenstern</code> | Chen &amp; Morgenstern, 1983 |
| 6 | <code translate="no">Sarma II</code> | Sarma, 1979 |
| 7 | <code translate="no">Borselli</code> | Borselli, 2016 |

Note that **`Sarma I` and `Sarma II` are two different formulations by the same
author**, published six years apart — the year in the third column is what tells
them apart, and they are not interchangeable.

⚠️ **Do not read this table through an automatic translator.** Every name in the
middle column is a surname, and machine translation turns some of them into
ordinary words: `Morgenstern-Price` has been seen rendered into Italian as
*"prezzo Morgentern"*, as though **Price** were the cost of something rather than
the surname of Vaughan Price, and `Sarma` becomes *"Sarca"* or *"Sara"*. If the
page you are looking at shows anything other than the names above, you are
reading a translation, not this document.

**`engine` — the algorithm that searches for the critical surface:**

| code | search engine | after |
|---|---|---|
| 1 | <code translate="no">Random Search</code> | Siegel, 1981 |
| 2 | <code translate="no">Convex Random Search</code> | Chen, 1992 |
| 3 | <code translate="no">Sniff Random Search 3.4</code> | Borselli, 1997-2025 |
| 4 | <code translate="no">New Random Search 2.0</code> | Borselli, 2021-2025 |
| 5 | <code translate="no">Mixed Engines Search 2.0</code> | Borselli, 2025-2026 |

⚠️ **Settings files from older versions declare the wrong ranges.** A `.PAR`
produced by SSAP 5.x lists fewer methods and engines than the current program
accepts, so its own labels are misleading and cannot be used as a reference. If
in doubt, regenerate it: load the `.MOD` in a current SSAP, save the settings
again, and use that file as your template.

## What this is for, and what it is not

The manual (§ 2.6.6) advises that *a complete and reliable verification may
require testing more than one search engine in succession*. Done by hand that
means one session per engine, and in practice almost nobody does it. Done
automatically it costs machine time instead of human time, so running every
method against every engine, repeatedly, becomes something you can actually
afford to do.

Two warnings that matter more than any of the code:

- **Repeating a run is not a luxury.** The search for the critical surface is
  pseudo-random: two identical runs do not return exactly the same number. In
  this very campaign, two configurations differed by 0.004 — well inside that
  scatter — which means a single run per configuration cannot tell a real
  difference from noise. Conclusions drawn from one run have been measured to
  reverse when repeated.
- **Automation does not improve the input.** A solver fed with unrealistic
  parameters returns a perfectly computed, perfectly wrong number — only faster.
  Deciding the stratigraphy, the strength parameters and the groundwater
  conditions is the geologist's work, this tool does none of it, and whoever
  signs the result remains responsible for it.

## Credits

SSAP2010 is developed by **Prof. Lorenzo Borselli** (Instituto de Geología /
Facultad de Ingeniería, Universidad Autónoma de San Luis Potosí, Mexico) and is
distributed free of charge at <https://www.ssap.eu>. All the credit for the
analysis itself belongs to him; this repository only automates its operation.

## Licence

MIT — see [LICENSE](LICENSE). The licence covers this code only, never SSAP.
