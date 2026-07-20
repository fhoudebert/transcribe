"""
ui/styles.py — Construction du thème ttk
==========================================
La fonction build_style(root) configure tous les styles ttk de l'application.
Elle est appelée UNE SEULE FOIS dans TranslatorApp.__init__().
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import C, F


def build_style(root: tk.Tk) -> None:
    """Applique le thème sombre à *root* et enregistre tous les styles ttk."""
    root.configure(bg=C["bg"])
    s = ttk.Style(root)
    s.theme_use("clam")

    # Frames
    s.configure("TFrame",     background=C["bg"])
    s.configure("P.TFrame",   background=C["panel"])

    # Labels
    s.configure("TLabel",     background=C["bg"],    foreground=C["text"],  font=F["body"])
    s.configure("P.TLabel",   background=C["panel"], foreground=C["text"],  font=F["body"])
    s.configure("PH.TLabel",  background=C["panel"], foreground=C["text"],  font=F["head"])
    s.configure("Mu.TLabel",  background=C["bg"],    foreground=C["muted"], font=F["small"])
    s.configure("PMu.TLabel", background=C["panel"], foreground=C["muted"], font=F["small"])
    s.configure("Ti.TLabel",  background=C["panel"], foreground=C["text"],  font=F["title"])
    s.configure("Sub.TLabel", background=C["panel"], foreground=C["muted"], font=F["subtitle"])

    # Combobox
    s.configure(
        "TCombobox",
        fieldbackground=C["card"], background=C["card"],
        foreground=C["text"],      arrowcolor=C["accent"],
        bordercolor=C["border"],   lightcolor=C["border"],
        darkcolor=C["border"],     font=F["body"],
    )
    s.map(
        "TCombobox",
        fieldbackground=[("readonly", C["card"])],
        foreground=[("readonly", C["text"])],
        selectbackground=[("readonly", C["accent"])],
        selectforeground=[("readonly", "#FFF")],
    )

    # Dropdown listbox colours (option_add — global pour toutes instances)
    root.option_add("*TCombobox*Listbox.background",       C["card"])
    root.option_add("*TCombobox*Listbox.foreground",       C["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", C["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#FFF")

    # Boutons
    def _btn(name: str, bg: str, fg: str, hover: str) -> None:
        s.configure(
            f"{name}.TButton",
            background=bg, foreground=fg,
            font=F["btn"], borderwidth=0, relief="flat",
            focuscolor=bg, padding=(14, 7),
        )
        s.map(
            f"{name}.TButton",
            background=[("active", hover), ("pressed", bg)],
            foreground=[("active", fg)],
        )

    _btn("Acc",    C["accent"], "#FFF",      C["acc_hi"])
    _btn("Swap",   C["swap"],   C["teal"],   C["border"])
    _btn("Ghost",  C["panel"],  C["muted"],  C["border"])
    _btn("Def",    C["card"],   C["teal"],   C["border"])
    _btn("Search", C["accent"], "#FFF",      C["acc_hi"])

    # Notebook
    s.configure(
        "TNotebook",
        background=C["bg"], borderwidth=0, tabmargins=[0, 0, 0, 0],
    )
    s.configure(
        "TNotebook.Tab",
        background=C["panel"], foreground=C["muted"],
        font=F["body"], padding=[18, 7], borderwidth=0,
    )
    s.map(
        "TNotebook.Tab",
        background=[("selected", C["accent"])],
        foreground=[("selected", "#FFF")],
    )

    # Divers
    s.configure("TSeparator", background=C["border"])
    s.configure("TProgressbar", troughcolor=C["card"],
                background=C["accent"], borderwidth=0)
