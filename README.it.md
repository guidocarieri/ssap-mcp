# ssap-mcp

*[This page in English](README.md)*

📖 Se leggi queste pagine con un traduttore automatico, usa il
[sito della documentazione](https://guidocarieri.github.io/ssap-mcp/it.html):
stesso testo, ma lì i nomi degli autori sono marcati in modo che il traduttore
non li tocchi. Da un README di GitHub quella marcatura viene rimossa — misurato —
e il traduttore rende `Morgenstern-Price` come «prezzo Morgentern», come se
**Price** fosse un prezzo invece del cognome di Vaughan Price. Un metodo con quel
nome non esiste.

Un server [MCP](https://modelcontextprotocol.io) che pilota **SSAP2010** — lo
*Slope Stability Analysis Program* del Prof. Lorenzo Borselli — in modo che un
assistente IA possa preparare un modello, scegliere il metodo di calcolo e il
motore di ricerca, lanciare la verifica e leggere il fattore di sicurezza che ne
risulta.

> **Non affiliato all'autore di SSAP.** SSAP2010 è software gratuito del Prof.
> Lorenzo Borselli (<https://www.ssap.eu>), *non* è open source, e non ne è
> permessa la ridistribuzione. Questo repository non contiene **nessuna parte di
> SSAP**: pilota una copia che scarichi e installi tu.

**Provato sui modelli di SSAP stesso.** Tutti i **20** casi di verifica in
[`tests/CAMPAGNA.md`](tests/CAMPAGNA.md) arrivano a un risultato — diciannove
sono modelli distribuiti insieme a SSAP2010, quindi chiunque lo abbia installato
può rifare l'intera campagna e controllare i numeri. Ogni fattore di sicurezza è
letto dalla relazione finale, e le coppie si comportano come devono: tiranti su
scarpata rocciosa **+22,8%**, liquefazione **−44,2%**, condizioni drenate contro
non drenate **−27,5%**. Dove un confronto non regge, sta scritto: due sono
marcati *non validi* e un risultato *non spiegato*, invece di essere tolti in
silenzio.

---

## ⛔ Leggi prima questo: non è un modo di far girare SSAP senza schermo

È il limite più importante, e quello che si fraintende più facilmente, perciò sta
scritto in parole povere prima di ogni altra cosa.

In informatica un programma si dice **headless** (letteralmente «senza testa»)
quando può girare senza schermo e senza nessuno davanti: lo si lancia da riga di
comando, lavora in secondo piano, e può quindi girare su un server affittato,
dentro un container, o di notte su una macchina dove nessuno ha fatto l'accesso.
**SSAP non è un programma di quel tipo, e questo server non lo rende tale.**

SSAP è un programma con interfaccia grafica. Nella versione pubblica **non ha né
riga di comando, né modalità batch, né interfaccia di scripting** — verificato
sull'intero manuale di 511 pagine della rel. 5.2 e sul sito ufficiale. Di
conseguenza a questo server servono, sullo stesso computer:

- SSAP2010 **installato** (si scarica da <https://www.ssap.eu>);
- una **sessione desktop di Windows con l'utente collegato**. Non una macchina
  remota dove nessuno ha fatto l'accesso, non un container, non un servizio in
  background: la finestra di SSAP deve esistere davvero su uno schermo, anche se
  nessuno la sta guardando;
- **privilegi di amministratore**, per il motivo spiegato nella tabella più sotto.

La promessa, quindi, è *«nessuno deve stare lì a cliccare»*, **non** *«non serve
uno schermo»*. Le due cose si somigliano e sono completamente diverse. Ciò che
sparisce è l'operatore umano, non il desktop.

Una cosa che deliberatamente **non** fa: non simula mai clic del mouse né
pressioni di tasti. Le quattro operazioni che devono per forza passare dalla
finestra di SSAP (carica modello, carica impostazioni, avvia verifica, produci
relazione) sono eseguite mandando messaggi di Windows direttamente ai pulsanti
(`PostMessage`/`BM_CLICK`). Il mouse, la tastiera e la finestra attiva restano
tuoi mentre una verifica è in corso: puoi continuare a lavorare ad altro.

## Come funziona

L'idea che rende possibile tutto il resto: **a SSAP si danno istruzioni
attraverso i suoi file, non attraverso i suoi menu.** Il metodo di calcolo e il
motore di ricerca sono scritti in chiaro dentro il file di impostazioni `.PAR`.
Si possono scrivere lì direttamente, e SSAP obbedisce a quello che trova. La
finestra serve soltanto a premere *avvio*.

```
create_model  →  set_analysis_options  →  run_verification  →  read_report
   .MOD/.DAT/.GEO    scrive il .PAR       lancia SSAP        Fs + quale metodo
                                                             è stato davvero usato
```

⛔ **Non fidarti mai del file che hai scritto: controlla la relazione che SSAP ti
ha riscritto.** Se metti nel `.PAR` un valore che SSAP non accetta, viene
ignorato *in silenzio*: nessun messaggio d'errore, nessun avviso, e la verifica
gira con qualcosa di diverso da ciò che avevi chiesto. Per questo `read_report`
estrae le righe `METODO DI CALCOLO` e `MOTORE DI RICERCA` dalla relazione finale,
che sono l'unica dichiarazione attendibile di ciò che è stato realmente usato.
Rileggerle non è una formalità: è l'unico modo di saperlo.

⛔ **I file `.tmp` e `temp_*.dxf` non sono i risultati.** Sono istantanee prese
mentre il calcolo è ancora in corso. Su una stessa identica verifica, un file
temporaneo e la relazione finale differivano di 0,018 sul valore di Fs. La
relazione vera viene scritta solo quando la si chiede, e solo dopo che il calcolo
è finito.

## Cosa serve prima di cominciare

Questo non è un programma che si scarica e si apre con un doppio clic. È un
**server con cui parla un assistente IA**: da solo non ha finestre, non ha menu e
non ha riga di comando, e non fa nulla finché un assistente non lo chiama. Qui
sotto c'è la catena completa di ciò che serve, scritta per intero perché nessuno
scopra a metà strada che gli manca un pezzo.

| cosa serve | perché serve | nota |
|---|---|---|
| **Windows** | SSAP2010 esiste solo per Windows, e questo server non fa altro che pilotare SSAP | niente macOS, niente Linux, nemmeno dentro un container |
| **SSAP2010, installato da te** | questo repository non comprende SSAP e non gli è consentito comprenderlo: l'autore lo distribuisce di persona e non ne permette la ridistribuzione. Questo server pilota soltanto una copia che è già sul tuo computer | download gratuito su <https://www.ssap.eu>. Sviluppato e provato sulla **6.1 build 15998** |
| **una sessione Windows con l'utente collegato** | SSAP non ha riga di comando, quindi l'unico modo di avviare una verifica è premere un pulsante nella sua finestra — e quella finestra può esistere solo su una sessione desktop vera | non funziona su un server senza schermo, come servizio in background, o su una macchina dove nessuno ha fatto l'accesso |
| **privilegi di amministratore** | SSAP gira con privilegi elevati. Windows vieta deliberatamente a un programma normale di mandare comandi alla finestra di uno elevato (è una protezione che si chiama UIPI), perciò un server non elevato semplicemente non riesce a premere i pulsanti di SSAP | avvia il tuo client MCP come amministratore |
| **Python 3.12 o successivo** | il server è scritto in Python | <https://www.python.org> |
| **uv** (oppure pip) | per installare le dipendenze | <https://docs.astral.sh/uv/> |
| **un client MCP** | MCP è un protocollo: questo server risponde soltanto a richieste, non avvia mai niente da sé. Il client è il programma che lo chiama davvero | per esempio Claude Desktop, Claude Code, o qualunque altro programma che parli MCP |
| **un account presso un assistente IA che supporti MCP** | al client serve un modello dietro, che decida cosa chiedere | normalmente significa un **abbonamento a pagamento**, ed è un costo ricorrente reale |

⛔ **Sulle ultime due righe è bene essere chiari.** Senza un client MCP *e* un
modello dietro, questo repository non fa assolutamente nulla: non ha un'interfaccia
propria su cui ripiegare. E se quello che ti serve è eseguire una singola verifica,
SSAP da solo la fa meglio e più in fretta di tutto questo: è stato progettato per
quello, e la sua interfaccia è lo strumento giusto. Questo progetto si ripaga solo
quando devi eseguire *molte* verifiche una dietro l'altra — ogni metodo contro ogni
motore, per dire, oppure lo stesso pendio con venti insiemi di parametri — o quando
la verifica deve stare dentro una filiera di elaborazione più lunga che è già
automatizzata.

Dipendenze installate in automatico: `mcp`, `ezdxf`, `numpy`, `laspy`,
`matplotlib`.

## Installazione

```bash
git clone https://github.com/guidocarieri/ssap-mcp
cd ssap-mcp
uv sync
```

Poi registralo presso il tuo client MCP (i percorsi qui sotto sono esempi — usa i
tuoi):

```json
{
  "mcpServers": {
    "ssap": {
      "command": "uv",
      "args": ["--directory", "C:/percorso/di/ssap-mcp", "run", "ssap-mcp"]
    }
  }
}
```

**Avvia il client come amministratore**, così il server eredita quei privilegi
(nella tabella sopra c'è il perché servono). Se preferisci non confermare un
avviso di sicurezza di Windows a ogni esecuzione, punta `SSAP_ELEVATED_RUNNER` a
un tuo programma di appoggio che esegua uno script PowerShell elevato — è
facoltativo, e il server funziona anche senza.

### Variabili d'ambiente

| variabile | valore predefinito | significato |
|---|---|---|
| `SSAP_EXE` | `C:\SSAP2010\ssap2010_64bit.exe` | dove si trova l'eseguibile di SSAP |
| `SSAP_PYTHON` | l'interprete in uso | interprete usato per il programma di appoggio |
| `SSAP_ELEVATED_RUNNER` | *(non impostata)* | programma facoltativo per ottenere i privilegi di amministratore senza avviso |
| `SSAP_EXAMPLES` | la cartella `examples/` inclusa | dove cercare i progetti di esempio |

## Strumenti

Sono le operazioni che l'assistente può chiamare. I nomi in `codice` sono quelli
che usa lui; tu non li digiti mai.

| strumento | cosa fa |
|---|---|
| `status` | dice se SSAP è installato, se il toolkit si è caricato, e se questo processo ha i privilegi di amministratore |
| `explore_point_cloud` | legge l'intestazione di una nuvola di punti LAS/LAZ — estensione, numero di punti, intervallo di quote, sistema di riferimento — prima di tentare qualcosa di più pesante |
| `extract_section_las` | ritaglia da una nuvola di punti un profilo del terreno in 2D, che diventa la geometria del pendio |
| `extract_section_dem` | lo stesso a partire da un modello digitale raster — **non implementato**: restituisce un errore esplicito e indica le alternative GDAL/PDAL |
| `analyze_section_dxf` | legge polilinee e livelli da una sezione che hai già disegnato in CAD |
| `create_model` | scrive i file del modello che SSAP legge: `.MOD`, `.DAT`, `.GEO`, più quelli facoltativi per falda, sovraccarichi, tiranti e rinforzi |
| `set_analysis_options` | **sceglie il metodo di calcolo e il motore di ricerca**, scrivendoli nel file di impostazioni `.PAR` |
| `run_verification` | l'esecuzione completa, senza clic umani: chiude l'eventuale SSAP aperto, controlla che le impostazioni appartengano a questo modello, avvia un'istanza pulita, attende, e restituisce il fattore di sicurezza minimo |
| `run_analysis` | la strada più vecchia, semi-manuale: apre SSAP con il modello caricato e lascia a te il pulsante di *avvio* |
| `read_report` | legge la relazione finale e restituisce il fattore di sicurezza insieme al metodo e al motore **realmente** usati |
| `parameter_glossary` | spiega cosa significa ciascun parametro della relazione, citando la legenda che SSAP stesso stampa sotto ogni tabella |
| `parse_results` | legge i file DXF e PDF prodotti da un'esecuzione |
| `list_examples` | elenca i progetti di esempio inclusi qui |

### Metodi di calcolo e motori di ricerca

I numeri della prima colonna sono i **codici** da passare a
`set_analysis_options` — gli stessi numeri che SSAP memorizza nel file `.PAR`.
Sono stati verificati uno per uno lanciando ciascun valore e rileggendo il nome
del metodo dalla relazione, perché le etichette scritte dentro i file di
impostazioni più vecchi sono sbagliate.

**`method` — il metodo all'equilibrio limite con cui si calcola Fs:**

| codice | metodo | secondo |
|---|---|---|
| 1 | <code translate="no">Janbu rigorous</code> | Janbu, 1973 |
| 2 | <code translate="no">Spencer</code> | Spencer, 1973 |
| 3 | <code translate="no">Sarma I</code> | Sarma, 1973 |
| 4 | <code translate="no">Morgenstern-Price</code> | Morgenstern &amp; Price, 1965 |
| 5 | <code translate="no">Chen-Morgenstern</code> | Chen &amp; Morgenstern, 1983 |
| 6 | <code translate="no">Sarma II</code> | Sarma, 1979 |
| 7 | <code translate="no">Borselli</code> | Borselli, 2016 |

**`engine` — l'algoritmo che cerca la superficie critica:**

| codice | motore di ricerca | secondo |
|---|---|---|
| 1 | <code translate="no">Random Search</code> | Siegel, 1981 |
| 2 | <code translate="no">Convex Random Search</code> | Chen, 1992 |
| 3 | <code translate="no">Sniff Random Search 3.4</code> | Borselli, 1997-2025 |
| 4 | <code translate="no">New Random Search 2.0</code> | Borselli, 2021-2025 |
| 5 | <code translate="no">Mixed Engines Search 2.0</code> | Borselli, 2025-2026 |

Si noti che **`Sarma I` e `Sarma II` sono due formulazioni diverse dello
stesso autore**, pubblicate a sei anni di distanza: è l'anno nella terza colonna
a distinguerle, e non sono intercambiabili.

⚠️ **I file di impostazioni delle versioni più vecchie dichiarano intervalli
sbagliati.** Un `.PAR` prodotto da SSAP 5.x elenca meno metodi e meno motori di
quanti il programma attuale ne accetti, quindi le sue etichette sono fuorvianti e
non si possono usare come riferimento. Nel dubbio, rigeneralo: carica il `.MOD` in
un SSAP aggiornato, salva di nuovo le impostazioni, e usa quel file come modello.

## A cosa serve, e a cosa non serve

Il manuale (§ 2.6.6) avverte che *una verifica completa e affidabile può
richiedere di provare più motori di ricerca in successione*. Fatto a mano
significa una sessione per motore, e in pratica non lo fa quasi nessuno. Fatto in
automatico costa tempo macchina invece di tempo umano, così provare ogni metodo
contro ogni motore, ripetutamente, diventa una cosa che ci si può permettere.

Due avvertenze che contano più di tutto il codice:

- **Ripetere una corsa non è un lusso.** La ricerca della superficie critica è
  pseudo-casuale: due esecuzioni identiche non restituiscono esattamente lo stesso
  numero. In questa stessa campagna due configurazioni differivano di 0,004 — ben
  dentro quella dispersione — il che significa che una sola corsa per
  configurazione non può distinguere una differenza vera dal rumore. Conclusioni
  tratte da una corsa sola si sono misurate ribaltarsi una volta ripetute.
- **L'automazione non migliora i dati in ingresso.** Un solutore alimentato con
  parametri irrealistici restituisce un numero calcolato perfettamente e
  perfettamente sbagliato — solo più in fretta. Decidere la stratigrafia, i
  parametri di resistenza e le condizioni idrauliche è lavoro del geologo, questo
  strumento non ne fa nulla, e chi firma il risultato ne resta responsabile.

## Riconoscimenti

SSAP2010 è sviluppato dal **Prof. Lorenzo Borselli** (Instituto de Geología /
Facultad de Ingeniería, Universidad Autónoma de San Luis Potosí, Messico) ed è
distribuito gratuitamente su <https://www.ssap.eu>. Tutto il merito dell'analisi
in sé è suo; questo repository ne automatizza soltanto l'uso.

## Licenza

MIT — vedi [LICENSE](LICENSE). La licenza copre solo questo codice, mai SSAP.
