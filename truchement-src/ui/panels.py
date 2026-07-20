"""
ui/panels.py — Panneau de traduction texte (onglets 1 et 2)
=============================================================
build_panel(app, parent, idx) → construit un panneau et retourne
le dictionnaire de widgets à stocker dans app._tabs[idx].
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import C, F
from html_renderer import setup_html_tags


def build_panel(app: "TranslatorApp", parent: ttk.Frame, idx: int) -> dict:  # type: ignore[name-defined]
    """
    Construit le panneau de traduction texte pour l'onglet *idx*.
    Retourne un dict de widgets utilisé par TranslatorApp._tabs[idx].
    """
    outer = ttk.Frame(parent)
    outer.pack(fill="both", expand=True, padx=20, pady=16)
    outer.columnconfigure(0, weight=1)
    outer.columnconfigure(2, weight=1)
    outer.rowconfigure(1, weight=1)

    # ── Colonne source ────────────────────────────────────────────────────────
    sc = ttk.Frame(outer)
    sc.grid(row=0, column=0, rowspan=3, sticky="nsew")
    sc.columnconfigure(0, weight=1)
    sc.rowconfigure(1, weight=1)

    src_hdr = ttk.Frame(sc)
    src_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    src_hdr.columnconfigure(0, weight=1)

    lbl_s = ttk.Label(src_hdr, text="", font=F["head"])
    lbl_s.grid(row=0, column=0, sticky="w")

    def_src_btn = ttk.Button(
        src_hdr, text="", style="Def.TButton",
        command=lambda i=idx: app._define_selected(i, "src"),
    )
    def_src_btn.grid(row=0, column=1, sticky="e")

    sf = tk.Frame(sc, bg=C["card"],
                  highlightbackground=C["border"], highlightthickness=1)
    sf.grid(row=1, column=0, sticky="nsew")
    src_txt = tk.Text(
        sf, wrap="word", bg=C["card"], fg=C["text"],
        insertbackground=C["accent"], relief="flat",
        font=F["body"], padx=10, pady=10, undo=True,
        selectbackground=C["accent"],
    )
    src_txt.pack(fill="both", expand=True)
    src_txt.bind("<KeyRelease>", lambda e, i=idx: app._upd_chars(i))

    src_menu = _make_ctx_menu(app, src_txt, idx, "src")

    char_lbl = ttk.Label(sc, text="", style="Mu.TLabel")
    char_lbl.grid(row=2, column=0, sticky="e", pady=(4, 0))

    # ── Colonne centrale (bouton Traduire) ────────────────────────────────────
    mc = ttk.Frame(outer)
    mc.grid(row=0, column=1, rowspan=3, sticky="ns", padx=10)
    ttk.Frame(mc).pack(expand=True, fill="both")
    tr_btn = ttk.Button(
        mc, text="", style="Acc.TButton",
        command=lambda i=idx: app._translate(i),
    )
    tr_btn.pack()
    ttk.Frame(mc).pack(expand=True, fill="both")

    # ── Colonne cible ─────────────────────────────────────────────────────────
    tc = ttk.Frame(outer)
    tc.grid(row=0, column=2, rowspan=3, sticky="nsew")
    tc.columnconfigure(0, weight=1)
    tc.rowconfigure(1, weight=1)

    tgt_hdr = ttk.Frame(tc)
    tgt_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    tgt_hdr.columnconfigure(0, weight=1)

    lbl_t = ttk.Label(tgt_hdr, text="", font=F["head"])
    lbl_t.grid(row=0, column=0, sticky="w")

    def_tgt_btn = ttk.Button(
        tgt_hdr, text="", style="Def.TButton",
        command=lambda i=idx: app._define_selected(i, "tgt"),
    )
    def_tgt_btn.grid(row=0, column=1, sticky="e", padx=(0, 4))

    cp_btn = ttk.Button(
        tgt_hdr, text="", style="Ghost.TButton",
        command=lambda i=idx: app._copy(i),
    )
    cp_btn.grid(row=0, column=2, sticky="e")

    tf2 = tk.Frame(tc, bg=C["card"],
                   highlightbackground=C["border"], highlightthickness=1)
    tf2.grid(row=1, column=0, sticky="nsew")
    tgt_txt = tk.Text(
        tf2, wrap="word", bg=C["card"], fg=C["teal"],
        insertbackground=C["teal"], relief="flat",
        font=F["body"], padx=10, pady=10,
        selectbackground=C["accent"], state="disabled",
    )
    tgt_txt.pack(fill="both", expand=True)

    tgt_menu = _make_ctx_menu(app, tgt_txt, idx, "tgt")

    cl_btn = ttk.Button(
        tc, text="", style="Ghost.TButton",
        command=lambda i=idx: app._clear(i),
    )
    cl_btn.grid(row=2, column=0, sticky="e", pady=(4, 0))

    return {
        "src": src_txt, "tgt": tgt_txt,
        "tr_btn": tr_btn, "cl_btn": cl_btn,
        "cp_btn": cp_btn, "char": char_lbl,
        "lbl_s": lbl_s,   "lbl_t": lbl_t,
        "def_src_btn": def_src_btn, "def_tgt_btn": def_tgt_btn,
        "src_menu": src_menu,       "tgt_menu": tgt_menu,
    }


def _make_ctx_menu(app: "TranslatorApp", widget: tk.Text,  # type: ignore[name-defined]
                   idx: int, side: str) -> tk.Menu:
    """Crée un menu contextuel clic-droit pour un widget Text."""
    menu = tk.Menu(
        widget, tearoff=0,
        bg=C["card"], fg=C["text"],
        activebackground=C["accent"], activeforeground="#FFF",
        font=F["small"], bd=0,
    )
    menu.add_command(
        label="",
        command=lambda i=idx, s=side: app._define_selected(i, s),
    )
    widget.bind("<Button-3>", lambda e, m=menu: _show_ctx_menu(e, m))
    widget.bind("<Button-2>", lambda e, m=menu: _show_ctx_menu(e, m))   # macOS
    return menu


def _show_ctx_menu(event: tk.Event, menu: tk.Menu) -> None:
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()
