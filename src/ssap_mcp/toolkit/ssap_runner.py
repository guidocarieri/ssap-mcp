"""ssap_runner.py — Lancio SSAP via file association con monitoring output.

SSAP non ha CLI documentata e richiede UAC RUNASADMIN. Il runner:
  1. Verifica esistenza .MOD e file dipendenti
  2. Lancia ssap2010_64bit.exe con il .MOD come argomento (file association)
  3. Monitora la cartella di lavoro per la comparsa di output (DXF, PDF, ANOMALY.LOG)
  4. Restituisce risultato (timeout, files prodotti)

L'utente deve interagire con la GUI per impostare verifica e cliccare RUN.
Il runner si limita a lanciare e raccogliere output.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

SSAP_EXE = Path(r"C:\SSAP2010\ssap2010_64bit.exe")
DEFAULT_TIMEOUT_S = 1800  # 30 minuti


@dataclass
class RunResult:
    started: bool
    pid: int | None
    work_dir: Path
    found_outputs: list[Path]
    anomaly_log: Path | None
    elapsed_s: float
    note: str = ""


def check_ssap_install() -> tuple[bool, str]:
    """Verifica installazione SSAP."""
    if not SSAP_EXE.exists():
        return False, f"SSAP non trovato in {SSAP_EXE}"
    return True, str(SSAP_EXE)


def launch_with_model(mod_path: Path, wait_for_output: bool = False,
                       timeout_s: int = DEFAULT_TIMEOUT_S,
                       poll_interval_s: float = 5.0) -> RunResult:
    """Lancia SSAP con il file .MOD passato come argomento.

    Se wait_for_output=True, monitora la cartella per comparsa file output (DXF, PDF, .LOG)
    fino a timeout. Altrimenti torna subito dopo il lancio.
    """
    mod_path = mod_path.resolve()
    if not mod_path.exists():
        raise FileNotFoundError(mod_path)

    work_dir = mod_path.parent
    files_before = {p.name for p in work_dir.iterdir() if p.is_file()}
    t0 = time.monotonic()

    # Lancio con verb open (rispetta file association). Su Windows l'app GUI gira
    # senza ereditare la console; non blocca.
    cmd = ["cmd", "/c", "start", "", str(mod_path)]
    proc = subprocess.Popen(cmd, cwd=str(work_dir), shell=False)

    pid = proc.pid
    note = f"Lanciato cmd start con .MOD={mod_path.name} (pid wrapper {pid})"

    if not wait_for_output:
        return RunResult(
            started=True, pid=pid, work_dir=work_dir,
            found_outputs=[], anomaly_log=None,
            elapsed_s=time.monotonic() - t0, note=note,
        )

    # Polling sulla cartella per nuovi file (DXF, PDF, LOG)
    new_outputs: list[Path] = []
    anomaly: Path | None = None
    deadline = t0 + timeout_s
    while time.monotonic() < deadline:
        time.sleep(poll_interval_s)
        cur = {p.name for p in work_dir.iterdir() if p.is_file()}
        new_files = cur - files_before
        for fn in new_files:
            p = work_dir / fn
            ext = p.suffix.lower()
            if ext in {".dxf", ".pdf", ".log", ".txt", ".sin", ".par", ".bmp", ".png"}:
                if fn not in {n.name for n in new_outputs}:
                    new_outputs.append(p)
                if fn.lower() == "anomaly.log":
                    anomaly = p
        # heuristic: se vedo almeno 1 DXF + 1 PDF la verifica è completa
        if any(p.suffix.lower() == ".dxf" for p in new_outputs) and \
           any(p.suffix.lower() == ".pdf" for p in new_outputs):
            note += " | Verifica probabilmente completata"
            break

    return RunResult(
        started=True, pid=pid, work_dir=work_dir,
        found_outputs=new_outputs, anomaly_log=anomaly,
        elapsed_s=time.monotonic() - t0, note=note,
    )


def kill_running_ssap() -> int:
    """Termina tutte le istanze ssap2010_64bit attive. Ritorna numero processi chiusi."""
    try:
        out = subprocess.run(
            ["taskkill", "/IM", "ssap2010_64bit.exe", "/F"],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode == 0:
            # Conta righe "SUCCESS"
            return out.stdout.count("SUCCESS")
        return 0
    except Exception:
        return 0


def copy_model_to_local(mod_path: Path, dest_dir: Path) -> Path:
    """Copia il modello e tutti i file dipendenti in una cartella locale.

    Utile se i file originali sono su rete e si vuole isolare il workflow.
    Restituisce path del nuovo .MOD.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    src_dir = mod_path.parent
    # Leggo il .MOD per scoprire i file dipendenti
    lines = mod_path.read_text(encoding="ascii", errors="ignore").splitlines()
    deps = [ln.strip() for ln in lines[1:] if ln.strip()]
    new_mod = dest_dir / mod_path.name
    shutil.copy2(mod_path, new_mod)
    for dep in deps:
        src = src_dir / dep
        if src.exists():
            shutil.copy2(src, dest_dir / dep)
    return new_mod
