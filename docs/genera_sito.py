# -*- coding: utf-8 -*-
"""Genera le pagine HTML del sito a partire dai due README.

Perche' esiste: su github.com **non e' possibile** marcare una parte del testo
come non traducibile. Misurato il 2026-08-02 ispezionando il DOM della pagina
renderizzata: il filtro HTML di GitHub rimuove `translate="no"`, rimuove la
classe `notranslate` e cancella del tutto l'elemento `<bdi>`. I nomi dei metodi
sono COGNOMI di autori — Price e' Vaughan Price — e un traduttore automatico li
rende «prezzo Morgentern» e «Sarca II», cioe' nomi di metodi che non esistono.

Queste pagine sono servite da GitHub Pages, che NON passa dal sanitizer del
markdown: qui `translate="no"` sopravvive e i nomi arrivano intatti in qualunque
lingua il lettore stia usando.

⛔ Le pagine si GENERANO, non si scrivono. Se le si scrivesse a mano
diventerebbero una terza copia della documentazione, e divergerebbe — che e' il
modo in cui la tabella dei metodi del README e' rimasta sbagliata per giorni
mentre quella del codice era giusta.

    python docs/genera_sito.py
"""
from __future__ import annotations

import pathlib
import re

import markdown

RADICE = pathlib.Path(__file__).resolve().parent.parent
DOCS = RADICE / "docs"

PAGINE = [
    ("README.md", "index.html", "en", "ssap-mcp — drive SSAP2010 from an AI assistant"),
    ("README.it.md", "it.html", "it", "ssap-mcp — pilotare SSAP2010 da un assistente IA"),
]

# Le tabelle che contengono questi termini sono fatte di nomi propri e numeri:
# ogni loro cella va sottratta alla traduzione automatica.
TABELLE_DA_PROTEGGERE = ("Sarma", "Random Search")

CSS = """
:root { color-scheme: light dark; }
body { max-width: 46rem; margin: 0 auto; padding: 2rem 1.2rem 6rem;
       font: 16px/1.65 -apple-system, "Segoe UI", system-ui, sans-serif;
       color: #1a1a1a; background: #fff; }
h1, h2, h3 { line-height: 1.25; margin-top: 2.2em; }
h1 { margin-top: .6em; }
code, pre { font-family: ui-monospace, "Cascadia Code", Consolas, monospace; font-size: .9em; }
code { background: #f2f1ef; padding: .1em .35em; border-radius: 4px; }
pre { background: #f2f1ef; padding: 1rem; border-radius: 8px; overflow-x: auto; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; display: block; overflow-x: auto; margin: 1.4em 0; }
th, td { border: 1px solid #d8d5d0; padding: .5em .7em; text-align: left; vertical-align: top; }
th { background: #f2f1ef; }
blockquote { border-left: 4px solid #d8d5d0; margin: 1.4em 0; padding: .2em 0 .2em 1rem; color: #555; }
a { color: #0a58ca; }
img { max-width: 100%; }
.lingue { font-size: .9em; margin-bottom: 2em; }
@media (prefers-color-scheme: dark) {
  body { color: #e8e6e3; background: #161614; }
  code, pre, th { background: #232320; }
  th, td { border-color: #3a3a37; }
  blockquote { border-left-color: #3a3a37; color: #b0aca6; }
  a { color: #7aa7ff; }
}
"""

SCHELETRO = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titolo}</title>
<style>{css}</style>
</head>
<body>
<p class="lingue">{lingue}</p>
{corpo}
</body>
</html>
"""

LINGUE = {
    "en": '<a href="it.html">Questa pagina in italiano</a> · '
          '<a href="https://github.com/guidocarieri/ssap-mcp">Repository on GitHub</a>',
    "it": '<a href="index.html">This page in English</a> · '
          '<a href="https://github.com/guidocarieri/ssap-mcp">Repository su GitHub</a>',
}


def proteggi_tabelle(html: str) -> str:
    """Marca `translate="no"` ogni cella delle tabelle di nomi propri."""
    def _una(m: re.Match) -> str:
        tabella = m.group(0)
        if not any(t in tabella for t in TABELLE_DA_PROTEGGERE):
            return tabella
        # solo <td>: le intestazioni ("code", "method") sono parole comuni e
        # possono essere tradotte senza danno.
        return tabella.replace("<td>", '<td translate="no">')
    return re.sub(r"<table>.*?</table>", _una, html, flags=re.DOTALL)


def sistema_collegamenti(html: str) -> str:
    """I README si linkano fra loro come file .md; qui sono pagine .html."""
    return (html.replace('href="README.it.md"', 'href="it.html"')
                .replace('href="README.md"', 'href="index.html"'))


def genera() -> list[pathlib.Path]:
    scritti = []
    for sorgente, uscita, lang, titolo in PAGINE:
        testo = (RADICE / sorgente).read_text(encoding="utf-8")
        corpo = markdown.markdown(
            testo, extensions=["tables", "fenced_code", "sane_lists"])
        corpo = proteggi_tabelle(sistema_collegamenti(corpo))
        pagina = SCHELETRO.format(lang=lang, titolo=titolo, css=CSS,
                                  lingue=LINGUE[lang], corpo=corpo)
        destinazione = DOCS / uscita
        destinazione.write_text(pagina, encoding="utf-8")
        scritti.append(destinazione)
    return scritti


if __name__ == "__main__":
    for p in genera():
        testo = p.read_text(encoding="utf-8")
        protette = testo.count('<td translate="no">')
        codici = testo.count('<code translate="no">')
        print(f"{p.name}: {len(testo):,} caratteri · "
              f"{protette} celle e {codici} nomi sottratti alla traduzione")
