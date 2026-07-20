"""
html_renderer.py — Rendu HTML léger dans un tk.Text
======================================================
Sans dépendance externe.  Balises interprétées :
  <b> <strong> <i> <em> <u> <s> <strike> <del>
  <sup> <sub> <code> <tt> <kbd>
  <h1> <h2> <h3>
  <br> <p> <div> <ul> <ol> <li> <hr>
  <a href="…">  (lien coloré, non cliquable)
  entités HTML : &amp; &lt; &gt; &nbsp; &quot; &apos; &#NNN; &#xNNN;

API publique :
    setup_html_tags(widget)          → à appeler UNE FOIS après création du Text
    render_html(widget, html_str)    → insère le HTML formaté dans widget
    is_html(text) → bool             → heuristique rapide
"""

from __future__ import annotations

import re
import tkinter as tk
from html.parser import HTMLParser as _HTMLParser

from config import C, F


# ─── Configuration des tags Tkinter ────────────────────────────────────────────

def setup_html_tags(widget: tk.Text) -> None:
    """Configure les tags Tkinter nécessaires au rendu HTML sur *widget*."""
    fam = F["body"][0]
    sz  = F["body"][1]
    widget.tag_configure("html:b",      font=(fam, sz, "bold"))
    widget.tag_configure("html:i",      font=(fam, sz, "italic"))
    widget.tag_configure("html:bi",     font=(fam, sz, "bold italic"))
    widget.tag_configure("html:u",      underline=True)
    widget.tag_configure("html:s",      overstrike=True)
    widget.tag_configure("html:code",   font=("Consolas", sz - 1),
                         background=C["border"], foreground=C["text"])
    widget.tag_configure("html:sup",    font=(fam, sz - 3), offset=4)
    widget.tag_configure("html:sub",    font=(fam, sz - 3), offset=-4)
    widget.tag_configure("html:h1",     font=(fam, sz + 5, "bold"),
                         foreground=C["teal"], spacing3=6)
    widget.tag_configure("html:h2",     font=(fam, sz + 3, "bold"),
                         foreground=C["teal"], spacing3=4)
    widget.tag_configure("html:h3",     font=(fam, sz + 1, "bold"),
                         foreground=C["acc_hi"], spacing3=2)
    widget.tag_configure("html:a",      foreground=C["accent"], underline=True)
    widget.tag_configure("html:hr",     foreground=C["border"])
    widget.tag_configure("html:p",      spacing1=6)
    widget.tag_configure("html:li",     lmargin1=20, lmargin2=30)
    widget.tag_configure("html:b+code", font=("Consolas", sz - 1, "bold"),
                         background=C["border"])


# ─── Parseur HTML → tk.Text ────────────────────────────────────────────────────

class _HtmlRenderer(_HTMLParser):
    """
    Parseur HTML minimaliste qui écrit directement dans un tk.Text.
    Utiliser render_html(widget, html_str) plutôt qu'instancier directement.
    """

    _TAG_MAP = {
        "b": "html:b", "strong": "html:b",
        "i": "html:i", "em":     "html:i",
        "u": "html:u",
        "s": "html:s", "strike": "html:s", "del": "html:s",
        "code": "html:code", "tt": "html:code", "kbd": "html:code",
        "sup": "html:sup",
        "sub": "html:sub",
        "h1": "html:h1", "h2": "html:h2", "h3": "html:h3",
        "a":  "html:a",
    }
    _BLOCK_CLOSE = {"p", "div", "blockquote", "h1", "h2", "h3"}
    _SKIP_TAGS   = {"style", "script", "head"}

    def __init__(self, widget: tk.Text) -> None:
        super().__init__(convert_charrefs=True)
        self._w      = widget
        self._stack: list[str]       = []
        self._marks: dict[str, str]  = {}
        self._skip   = 0
        self._ol_ctr = 0
        self._in_li  = False

    def _insert(self, text: str, *extra_tags: str) -> None:
        if self._skip:
            return
        tags = tuple(self._stack) + extra_tags
        self._w.insert("end", text, tags if tags else "")

    def _open_tag(self, tk_tag: str) -> None:
        mark = f"m_{tk_tag}_{len(self._marks)}"
        self._w.mark_set(mark, "end-1c")
        self._marks[f"{tk_tag}#{mark}"] = mark
        self._stack.append(tk_tag)

    def _close_tag(self, tk_tag: str) -> None:
        key = next(
            (k for k in reversed(list(self._marks)) if k.startswith(f"{tk_tag}#")),
            None,
        )
        if key is None:
            return
        mark = self._marks.pop(key)
        try:
            self._w.tag_add(tk_tag, mark, "end")
            self._w.mark_unset(mark)
        except tk.TclError:
            pass
        for j in range(len(self._stack) - 1, -1, -1):
            if self._stack[j] == tk_tag:
                self._stack.pop(j)
                break

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self._skip += 1
            return
        if self._skip:
            return
        if tag in self._TAG_MAP:
            self._open_tag(self._TAG_MAP[tag])
        if tag == "br":
            self._insert("\n")
        elif tag == "hr":
            self._insert("\n" + "\u2500" * 72 + "\n", "html:hr")
        elif tag in ("p", "div", "blockquote"):
            idx = self._w.index("end-1c")
            if idx != "1.0" and self._w.get("end-2c", "end-1c") != "\n":
                self._insert("\n")
        elif tag == "ul":
            self._insert("\n")
        elif tag == "ol":
            self._ol_ctr = 0
            self._insert("\n")
        elif tag == "li":
            self._in_li = True
            if self._ol_ctr > 0 or self._get_attr(attrs, "type", "") in ("1", "a", "A"):
                self._ol_ctr += 1
                self._insert(f"\n  {self._ol_ctr}. ", "html:li")
            else:
                self._insert("\n  \u2022 ", "html:li")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in self._TAG_MAP:
            self._close_tag(self._TAG_MAP[tag])
        if tag in self._BLOCK_CLOSE:
            if self._w.get("end-2c", "end-1c") != "\n":
                self._insert("\n")
        if tag == "li":
            self._in_li = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        cleaned = " ".join(data.split()) if data.strip() else data
        if cleaned:
            self._insert(cleaned)

    @staticmethod
    def _get_attr(attrs: list, name: str, default: str = "") -> str:
        for k, v in attrs:
            if k == name:
                return v or default
        return default


# ─── API publique ──────────────────────────────────────────────────────────────

def render_html(widget: tk.Text, html_str: str) -> None:
    """
    Interprète *html_str* et l'insère dans *widget* avec mise en forme.
    setup_html_tags(widget) doit avoir été appelé au préalable.
    """
    if not html_str:
        return
    _HtmlRenderer(widget).feed(html_str)


def is_html(text: str) -> bool:
    """Heuristique rapide : le texte contient-il une balise HTML ?"""
    return bool(re.search(r'<[a-zA-Z][^>]*>', text))
