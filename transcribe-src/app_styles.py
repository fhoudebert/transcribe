"""
app_styles.py  —  Palette, polices, widgets helpers, style TTK.
Importe tkinter mais pas les autres modules du projet.
"""

import tkinter as tk
from tkinter import ttk
from app_config import IS_WINDOWS

# ── Palette ───────────────────────────────────────────────────
BG     = "#0d1117"
BG2    = "#161b22"
BG3    = "#21262d"
BG4    = "#30363d"
ACCENT = "#388bfd"
GREEN  = "#3fb950"
WARN   = "#d29922"
DANGER = "#f85149"
TEAL   = "#39c5cf"
FG     = "#e6edf3"
FG2    = "#8b949e"
BORDER = "#30363d"

# ── Polices ───────────────────────────────────────────────────
FONT_MONO  = ("Consolas", 9)           if IS_WINDOWS else ("Monospace", 9)
FONT_UI    = ("Segoe UI", 10)          if IS_WINDOWS else ("Helvetica Neue", 10)
FONT_H1    = ("Segoe UI", 14, "bold")  if IS_WINDOWS else ("Helvetica Neue", 14, "bold")
FONT_H2    = ("Segoe UI", 10, "bold")  if IS_WINDOWS else ("Helvetica Neue", 10, "bold")
FONT_SMALL = ("Segoe UI",  8)          if IS_WINDOWS else ("Helvetica Neue",  8)
FONT_INFO  = ("Consolas",  9)          if IS_WINDOWS else ("Monospace", 9)


# ── Helpers couleur ───────────────────────────────────────────

def _adj(hex_color: str, d: int) -> str:
    """Éclaircit (d>0) ou assombrit (d<0) une couleur hex."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, r+d)),
        max(0, min(255, g+d)),
        max(0, min(255, b+d)),
    )


# ── Widgets helpers ───────────────────────────────────────────

def mkbtn(parent, text: str, command, color=ACCENT, fg=FG, **kw) -> tk.Button:
    """Bouton flat stylisé avec effet hover."""
    b = tk.Button(
        parent, text=text, command=command,
        bg=color, fg=fg,
        activebackground=_adj(color, 28), activeforeground=fg,
        disabledforeground=BG4,
        relief="flat", bd=0, cursor="hand2",
        font=FONT_H2, padx=14, pady=7, **kw,
    )
    b.bind("<Enter>", lambda e, c=color: b.config(bg=_adj(c, 28)))
    b.bind("<Leave>", lambda e, c=color: b.config(
        bg=c if str(b.cget("state")) != "disabled" else _adj(c, -20)))
    return b


def section(parent, text: str, color=ACCENT):
    """Label de section avec barre colorée verticale."""
    f = tk.Frame(parent, bg=BG)
    f.pack(fill="x", pady=(10, 3))
    tk.Frame(f, width=3, bg=color).pack(side="left", fill="y", padx=(0, 8))
    tk.Label(f, text=text, font=FONT_H2, bg=BG, fg=FG).pack(side="left")


def hdivider(parent):
    """Séparateur horizontal."""
    tk.Frame(parent, height=1, bg=BORDER).pack(fill="x", pady=4)


def checkbox(parent, text: str, var, **kw) -> tk.Checkbutton:
    """Case à cocher stylisée."""
    return tk.Checkbutton(
        parent, text=text, variable=var,
        bg=BG, fg=FG2, selectcolor=BG3,
        activebackground=BG, activeforeground=FG,
        font=FONT_UI, cursor="hand2", **kw,
    )


def lang_combobox(parent, var: tk.StringVar, values: list[str],
                  width: int = 20) -> ttk.Combobox:
    """Combobox langue standardisée (readonly, style TCombobox)."""
    cb = ttk.Combobox(parent, textvariable=var,
                      values=values, width=width, state="readonly")
    return cb


# ── Style TTK (appelé une seule fois sur la racine Tk) ────────

def apply_ttk_style(root: tk.Tk):
    """
    Configure le style TTK global.
    Doit être appelé APRÈS root.mainloop() start (donc dans __init__).
    Le s.map() est indispensable sous Windows pour éviter le fond jaune
    des Combobox en état readonly (clam mappe sur SystemHighlight sinon).
    """
    s = ttk.Style(root)
    s.theme_use("clam")

    for style_name, sel_fg in [
        ("TCombobox",      "#ffffff"),   # texte blanc sur fond ACCENT
        ("Dark.TCombobox", "#000000"),   # texte noir sur fond ACCENT
    ]:
        s.configure(
            style_name,
            fieldbackground=BG3, background=BG3,
            foreground=FG,
            selectbackground=ACCENT,
            selectforeground=sel_fg,
            bordercolor=BORDER, lightcolor=BG3,
            darkcolor=BG3, arrowcolor=FG2,
            insertcolor=FG,
        )
        s.map(
            style_name,
            fieldbackground=[("readonly",       BG3),
                             ("readonly focus", BG3),
                             ("focus",          BG3),
                             ("active",         BG3),
                             ("!disabled",      BG3)],
            foreground     =[("readonly",       FG),
                             ("readonly focus", FG),
                             ("focus",          FG),
                             ("disabled",       BG4)],
            selectbackground=[("readonly",      ACCENT),
                              ("focus",         ACCENT)],
            selectforeground=[("readonly",      sel_fg),
                              ("focus",         sel_fg)],
            background     =[("readonly",       BG3),
                             ("active",         BG3)],
        )

    s.configure("Horizontal.TProgressbar",
                troughcolor=BG3, background=ACCENT, bordercolor=BG3)
