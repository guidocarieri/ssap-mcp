# -*- coding: utf-8 -*-
"""Una corsa SSAP dall'inizio alla fine, senza mani: modello -> Fs.

    modello .MOD + .par  ->  VERIFICA GLOBALE  ->  attesa  ->  REPORT  ->  Fs

E' l'unita' che mancava per cercare i parametri a Fs = 1 iterando: finora ogni
giro chiedeva l'occhio umano sul pannello.

⛔ Le quattro cose che rendono possibile il senza-mani, tutte pagate sul campo
il 2026-07-28:

 1. **I pulsanti di avvio sono OWNER-DRAWN**: la scritta e' disegnata, il testo
    della finestra e' VUOTO. Cercarli per didascalia non li trova mai — ed e'
    per questo che il pilota precedente si fermava con «VERIFICA GLOBALE
    assente». Si cercano per GEOMETRIA dentro il gruppo «AVVIO VERIFICA»:
    il primo dall'alto e' la globale, il secondo la singola.

 2. **La fine del calcolo si legge dai pulsanti, non dal tempo di CPU.** La CPU
    dice «il processo consuma»; il suggerimento «la verifica sta correndo…»
    resta scritto anche a calcolo fermo. Il segnale vero: durante la corsa
    VERIFICA GLOBALE e' SPENTA e STOP VERIFICA e' ACCESA; a fine corsa si
    invertono. E' il programma che dichiara il proprio stato.
    (Misurato: a 45 s dall'avvio la CPU era ferma a 1,4 s e ho concluso che non
    calcolasse; sette minuti dopo erano 76 s e la corsa era al 100%.)

 3. **I file `.tmp` e `temp_*.dxf` NON sono il risultato**: sono istantanee di
    meta' corsa. Misurato: a fine verifica il pannello dava Fs min 0,9578 e il
    `temp_critzon.dxf`, scritto un minuto prima, dava 0,9759. Il risultato si
    legge dal REPORT, che SSAP scrive solo su richiesta e a calcolo concluso.

 4. **SSAP apre DUE dialoghi di salvataggio** insieme: compilarne uno solo non
    scrive nulla e non da' errore.
"""
import ctypes
import os
import re
import sys
import time
from ctypes import wintypes

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ["SSAP_DIR"]
NOME = os.environ["SSAP_NOME"]
MOD = os.path.join(BASE, NOME + ".MOD")
PAR = os.path.join(BASE, NOME + ".par")
REPORT = os.path.join(BASE, f"report_{NOME}.txt")
MAX_SECONDI = int(os.environ.get("SSAP_MAX_SECONDI", "1800"))

u = ctypes.windll.user32
u.SendMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
u.SendMessageW.restype = wintypes.LPARAM
CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
WM_GETTEXT, WM_GETTEXTLENGTH, WM_SETTEXT, WM_CLOSE = 0x000D, 0x000E, 0x000C, 0x0010
WM_LBUTTONDOWN, WM_LBUTTONUP, BM_CLICK, MK_LBUTTON = 0x0201, 0x0202, 0x00F5, 0x0001
SW_RESTORE = 9  # ShowWindow: de-iconifica senza attivare a forza la finestra


def T(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def txt(h):
    n = int(u.SendMessageW(h, WM_GETTEXTLENGTH, 0, 0))
    b = ctypes.create_unicode_buffer(n + 2)
    u.SendMessageW(h, WM_GETTEXT, n + 1, ctypes.addressof(b))
    return b.value


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def pid_of(h):
    p = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def rect(h):
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def tutte():
    o = []
    u.EnumWindows(CB(lambda h, l: (o.append(h), True)[1]), 0)
    return [h for h in o if u.IsWindowVisible(h)]


def tutte_anche_nascoste():
    """Come `tutte()`, ma SENZA il filtro sulla visibilita'.

    Serve per la finestra principale: una finestra ICONIFICATA ha
    `IsWindowVisible == False`, quindi `tutte()` non la vede e l'attesa scade
    su una finestra che esiste ed e' li'. Misurato il 2026-08-01: SSAP lasciato
    minimizzato da una sessione precedente -> «la finestra non e' comparsa»
    dopo 90 s, mentre `EnumWindows` la restituiva con titolo esatto.
    Per i DIALOGHI resta giusto `tutte()`: un dialogo non visibile non e' da
    sbrigare.
    """
    o = []
    u.EnumWindows(CB(lambda h, l: (o.append(h), True)[1]), 0)
    return o


def figli(h):
    o = []
    u.EnumChildWindows(h, CB(lambda c, l: (o.append(c), True)[1]), 0)
    return o


def premi(h):
    """Owner-drawn: SOLO i messaggi del mouse.

    ⛔ Niente `BM_CLICK` in coda. Mandare entrambi fa partire l'azione DUE
    volte: il 2026-07-28 sera SSAP e' sparito subito dopo la generazione del
    report, e il doppio colpo sulle conferme e' il sospetto principale.
    Sui pulsanti normali (dialoghi) si usa `premi_std`, che e' l'inverso.
    """
    x0, y0, x1, y1 = rect(h)
    lp = (((y1 - y0) // 2) << 16) | (((x1 - x0) // 2) & 0xFFFF)
    u.PostMessageW(h, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.08)
    u.PostMessageW(h, WM_LBUTTONUP, 0, lp)


def premi_std(h):
    """Pulsante normale di un dialogo: BM_CLICK e basta."""
    u.PostMessageW(h, BM_CLICK, 0, 0)


def attendi_finestra(secondi=90):
    """Aspetta la finestra VERA di SSAP, enumerando le top-level.

    ⛔ NON si usa `Get-Process ... MainWindowTitle`: per questo programma
    restituisce «ssap2010_64bit», cioe' la finestra-applicazione invisibile di
    Lazarus (0x0 px), non la finestra principale «SSAP 2010 (Release 6.1 -
    2026)». Misurato il 2026-07-28: tre riprese perse perche' chi lanciava
    controllava il titolo giusto sulla finestra sbagliata, e SSAP risultava
    «non aperto» mentre era li' davanti.

    ⛔ Si enumera SENZA il filtro sulla visibilita' e, se la finestra e'
    ICONIFICATA, la si RIPRISTINA prima di restituirla: minimizzata ha
    `IsWindowVisible == False` e i controlli figli non sono pilotabili.
    Misurato il 2026-08-01 su SSAP lasciato minimizzato da una sessione
    precedente: attesa scaduta su una finestra che esisteva col titolo esatto.
    """
    t0 = time.time()
    while time.time() - t0 < secondi:
        h = next((x for x in tutte_anche_nascoste() if "SSAP 2010" in txt(x)),
                 None)
        if h is not None:
            if u.IsIconic(h):
                T("finestra iconificata: la ripristino")
                u.ShowWindow(h, SW_RESTORE)
                for _ in range(20):
                    time.sleep(0.5)
                    if not u.IsIconic(h) and u.IsWindowVisible(h):
                        break
                else:
                    T("[ATTENZIONE] non e' tornata visibile dopo il ripristino")
            T(f"finestra trovata dopo {time.time()-t0:.0f} s: «{txt(h)[:50]}»")
            return h
        time.sleep(1)
    return None


MAIN = attendi_finestra(int(os.environ.get("SSAP_ATTESA_FINESTRA", "90")))
if MAIN is None:
    raise SystemExit("[STOP] la finestra di SSAP non e' comparsa entro l'attesa")
SPID = pid_of(MAIN)


def bott(nome):
    return next((h for h in figli(MAIN) if cls(h) == "Button" and txt(h) == nome), None)


def sbriga(dove, ferma_su_scelta=True):
    for h in tutte():
        if pid_of(h) != SPID or h == MAIN or cls(h) != "#32770":
            continue
        bs = [(c, txt(c).replace("&", "").strip().lower())
              for c in figli(h) if cls(c) == "Button" and u.IsWindowVisible(c)]
        et = sorted(x[1] for x in bs if x[1])
        if et == ["ok"]:
            T(f"   [{dove}] avviso solo-OK «{txt(h)[:50]}» -> confermo")
            premi_std(next(x[0] for x in bs if x[1] == "ok"))
            time.sleep(1.0)
        elif et and ferma_su_scelta:
            raise SystemExit(f"[FERMO] [{dove}] dialogo con scelta {et}: "
                             f"«{txt(h)[:60]}» — la decisione non la prende uno script")


def chiudi_audit():
    a = next((h for h in tutte() if pid_of(h) == SPID and "AUDIT" in txt(h).upper()), None)
    if a is None:
        return
    cand = [(rect(h), h) for h in figli(a) if cls(h) == "Button" and txt(h) == ""]
    if cand:
        premi(max(cand, key=lambda z: (z[0][1], z[0][0]))[1])
    else:
        u.PostMessageW(a, WM_CLOSE, 0, 0)
    for _ in range(20):
        time.sleep(0.5)
        if not u.IsWindow(a) or not u.IsWindowVisible(a):
            T("   audit chiusa")
            return
    u.PostMessageW(a, WM_CLOSE, 0, 0)
    time.sleep(1.5)


def apri(pulsante, percorso, titolo):
    b = bott(pulsante)
    if b is None or not u.IsWindowEnabled(b):
        raise SystemExit(f"[STOP] «{pulsante}» assente o spento")
    u.PostMessageW(b, BM_CLICK, 0, 0)
    d = None
    for _ in range(40):
        time.sleep(0.5)
        d = next((h for h in tutte() if pid_of(h) == SPID
                  and titolo.lower() in txt(h).lower()), None)
        if d:
            break
    if d is None:
        raise SystemExit(f"[STOP] dialogo «{titolo}» non comparso")
    ff = figli(d)
    ed = next((h for h in ff if cls(h) == "Edit" and u.GetDlgCtrlID(h) == 1148
               and u.IsWindowVisible(h)), None)
    ok = next((h for h in ff if cls(h) == "Button" and u.GetDlgCtrlID(h) == 1
               and u.IsWindowVisible(h)), None)
    buf = ctypes.create_unicode_buffer(percorso)
    u.SendMessageW(ed, WM_SETTEXT, 0, ctypes.addressof(buf))
    time.sleep(0.4)
    if txt(ed).strip().lower() != percorso.lower():
        raise SystemExit("[STOP] percorso non accettato dal dialogo")
    u.PostMessageW(ok, BM_CLICK, 0, 0)
    T(f"   «{pulsante}» -> {os.path.basename(percorso)}")
    time.sleep(2.5)


def pulsanti_avvio():
    """I due owner-drawn dentro «AVVIO VERIFICA», dall'alto: globale, singola."""
    g = bott("AVVIO VERIFICA")
    if g is None:
        raise SystemExit("[STOP] gruppo «AVVIO VERIFICA» non trovato")
    gx0, gy0, gx1, gy1 = rect(g)
    d = sorted((h for h in figli(MAIN)
                if cls(h) == "Button" and not txt(h)
                and gx0 <= rect(h)[0] and rect(h)[2] <= gx1
                and gy0 <= rect(h)[1] and rect(h)[3] <= gy1),
               key=lambda h: rect(h)[1])
    if len(d) < 2:
        raise SystemExit(f"[STOP] nel gruppo trovo {len(d)} pulsanti disegnati, servono 2")
    return d[0], d[1]


def compila_salvataggi(dest, giri=4):
    n = 0
    for _ in range(giri):
        dlg = [h for h in tutte() if pid_of(h) == SPID and cls(h) == "#32770"
               and any(cls(c) == "Edit" and u.IsWindowVisible(c) for c in figli(h))]
        if not dlg:
            break
        for d in dlg:
            ff = figli(d)
            ed = [h for h in ff if cls(h) == "Edit" and u.IsWindowVisible(h)]
            ok = [h for h in ff if cls(h) == "Button"
                  and u.GetDlgCtrlID(h) == 1 and u.IsWindowVisible(h)]
            if not ed or not ok:
                continue
            buf = ctypes.create_unicode_buffer(dest)
            u.SendMessageW(ed[0], WM_SETTEXT, 0, ctypes.addressof(buf))
            time.sleep(0.4)
            u.PostMessageW(ok[0], BM_CLICK, 0, 0)
            n += 1
            time.sleep(2.0)
    return n


def main():
    for f in (MOD, PAR):
        if not os.path.exists(f):
            raise SystemExit(f"[STOP] manca {f}")
    # un report vecchio si legge come nuovo: si toglie di mezzo PRIMA
    if os.path.exists(REPORT):
        os.remove(REPORT)
        T(f"tolto il report precedente ({os.path.basename(REPORT)})")

    sbriga("apertura")
    T("1) modello")
    apri("LEGGI MODELLO", MOD, "Lettura Modello Pendio")
    chiudi_audit()
    sbriga("dopo modello")

    T("2) impostazioni")
    apri("CARICA IMPOSTAZIONI PROGETTO", PAR, "impostazioni")
    chiudi_audit()
    sbriga("dopo impostazioni")

    globale, _ = pulsanti_avvio()
    stop_h = bott("STOP VERIFICA")
    T(f"3) avvio — VERIFICA GLOBALE hwnd={globale}")
    premi(globale)

    t0 = time.time()
    partita = False
    while time.time() - t0 < MAX_SECONDI:
        time.sleep(10)
        sbriga("in corsa", ferma_su_scelta=False)
        corre = (not u.IsWindowEnabled(globale)) and bool(u.IsWindowEnabled(stop_h))
        if corre and not partita:
            partita = True
            T(f"   {time.time()-t0:5.0f}s  la corsa e' PARTITA "
              f"(globale spenta, STOP acceso)")
        if partita and not corre:
            T(f"   {time.time()-t0:5.0f}s  FINITA "
              f"(globale riaccesa, STOP spento)")
            break
        if int(time.time() - t0) % 60 < 10:
            T(f"   {time.time()-t0:5.0f}s  in corso")
    else:
        raise SystemExit(f"[STOP] non finita entro {MAX_SECONDI} s")

    time.sleep(2)
    T("4) report")
    b = bott("GENERA REPORT VERIFICA")
    if b is None or not u.IsWindowEnabled(b):
        raise SystemExit("[STOP] GENERA REPORT VERIFICA spento: nessun risultato")
    premi(b)
    time.sleep(2.5)
    T(f"   dialoghi compilati: {compila_salvataggi(REPORT)}")
    sbriga("dopo report", ferma_su_scelta=False)
    time.sleep(1.5)

    if not os.path.exists(REPORT):
        raise SystemExit("[STOP] il report non e' stato scritto")
    t = open(REPORT, "rb").read().decode("latin-1")
    # il report DEVE parlare del modello che credo di aver girato: se SSAP
    # avesse in memoria un altro .MOD (capita: le impostazioni sopravvivono al
    # cambio di documento) leggerei l'Fs di un altro pendio senza accorgermene
    if NOME.lower() not in t.lower():
        raise SystemExit(f"[STOP] il report non nomina «{NOME}»: "
                         f"non e' il modello che credevo di aver girato")
    m = re.search(r"#FS_minimo\s*#Fattore di sicurezza\(FS\)=\s*([0-9.]+)", t)
    n = re.search(r"TOTALE SUPERFICI GENERATE\s*:\s*(\d+)", t)
    if not m:
        raise SystemExit("[STOP] Fs minimo non trovato nel report")

    # ⛔ La corsa si ARCHIVIA con un nome suo. Fino al 29/07 ogni corsa scriveva
    # `report_<NOME>.txt` e cancellava la precedente: cinque corse gemelle sono
    # diventate due, e la dispersione del motore — che e' UN RISULTATO, non un
    # dettaglio — si e' potuta solo ricordare, non rileggere. Il file canonico
    # resta (e' l'ultima corsa, e va tolto prima di ogni giro perche' la sua
    # assenza si veda); accanto si deposita la copia numerata che non si perde.
    i = 1
    while os.path.exists(os.path.join(BASE, f"report_{NOME}__{i:02d}.txt")):
        i += 1
    archivio = os.path.join(BASE, f"report_{NOME}__{i:02d}.txt")
    with open(archivio, "wb") as fh:
        fh.write(t.encode("latin-1"))
    T(f"   corsa archiviata: {os.path.basename(archivio)}")

    T(f"\nRISULTATO  {NOME}   Fs_min = {m.group(1)}   "
      f"superfici = {n.group(1) if n else '?'}")
    print(f"FS_MIN={m.group(1)}", flush=True)
    print(f"REPORT_ARCHIVIO={archivio}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
