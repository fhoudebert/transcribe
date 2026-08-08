"""
ui/about_window.py — Fenêtre "À propos" de Truchement
=========================================================
Ouverte via le bouton ℹ en haut à droite de l'en-tête principal.

Adapté du modèle about_window.py fourni, mais branché sur les modules
propres à ce projet plutôt que sur app_config/app_styles :
  • Couleurs/polices : config.C / config.F
  • Chaînes localisées : i18n.I18N (clés about_*, déjà présentes en 4 langues)
  • Icône : assets/dico.png, via bootstrap.BASE_DIR (même logique que
    ui/app.py._load_header_icon, dupliquée ici en miniature pour rester
    autonome — voir _load_about_icon ci-dessous)
"""

from __future__ import annotations

import os
import webbrowser

import tkinter as tk
from tkinter import ttk

import bootstrap
from config import C, F


# Métadonnées de l'application — à éditer ici.
APP_META: dict = {
    "version": "0.3",
    "author":  "François Houdebert",
    "site":    "https://github.com/fhoudebert/transcribe",
    "components": [
        ("argos-translate", "https://github.com/argosopentech/argostranslate"),
    ],
}

_ICON_SZ = 48
_ICON_PATH = os.path.join(bootstrap.BASE_DIR, "assets", "dico.png")


def _load_about_icon() -> "tk.PhotoImage | None":
    """
    Charge assets/dico.png en 48×48 px pour l'en-tête de la fenêtre À propos.

    Taille strictement limitée à _ICON_SZ : avec Pillow, redimensionnement
    de qualité ; sans Pillow, repli sur un sous-échantillonnage entier qui
    garantit qu'on n'affiche jamais l'image native en pleine résolution.
    Ne lève jamais d'exception — retourne None si l'icône est absente.
    """
    if not os.path.isfile(_ICON_PATH):
        return None

    try:
        from PIL import Image, ImageTk
        img = Image.open(_ICON_PATH).convert("RGBA")
        w, h = img.size
        side = min(w, h)
        left, top = (w - side) // 2, (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((_ICON_SZ, _ICON_SZ), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except ImportError:
        pass
    except Exception:
        return None

    try:
        raw = tk.PhotoImage(file=_ICON_PATH)
        w_raw, h_raw = raw.width(), raw.height()
        if w_raw <= 0 or h_raw <= 0:
            return None
        factor = max(1, max(w_raw, h_raw) // _ICON_SZ)
        if factor > 1:
            raw = raw.subsample(factor, factor)
        return raw
    except Exception:
        return None


class AboutWindow(tk.Toplevel):
    """
    Fenêtre modale "À propos", centrée sur la fenêtre principale.
    """

    def __init__(self, parent: tk.Tk, t: dict) -> None:
        super().__init__(parent)
        self._t = t
        self.title(t.get("about_title", "About"))
        self.configure(bg=C["panel"])
        self.resizable(False, False)
        self.transient(parent)
        self.bind("<Map>", self._on_map)

        self.update_idletasks()
        w, h = 480, 560
        px = parent.winfo_rootx() + parent.winfo_width()  // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"{w}x{h}+{max(0, px - w//2)}+{max(0, py - h//2)}")

        self._build()

    def _on_map(self, _event=None) -> None:
        self.unbind("<Map>")
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()

    def _build(self) -> None:
        t = self._t

        # ── En-tête : icône 48×48 + titre + version ─────────────────────────
        hdr = tk.Frame(self, bg=C["accent"], pady=14)
        hdr.pack(fill="x")
        hdr_inner = tk.Frame(hdr, bg=C["accent"])
        hdr_inner.pack(padx=20, anchor="w")

        icon = _load_about_icon()
        self._about_icon = icon   # référence conservée : sinon le GC l'efface

        icon_frame = tk.Frame(hdr_inner, bg=C["accent"],
                              width=_ICON_SZ, height=_ICON_SZ)
        icon_frame.pack_propagate(False)
        icon_frame.pack(side="left", padx=(0, 14))

        if icon is not None:
            tk.Label(icon_frame, image=icon, bg=C["accent"], bd=0,
                     width=_ICON_SZ, height=_ICON_SZ).pack()
        else:
            cv = tk.Canvas(icon_frame, width=_ICON_SZ, height=_ICON_SZ,
                           bg=C["accent"], highlightthickness=0)
            cv.pack()
            cv.create_oval(3, 3, _ICON_SZ - 3, _ICON_SZ - 3,
                           fill=C["panel"], outline="")
            cv.create_text(_ICON_SZ // 2, _ICON_SZ // 2, text="T",
                           font=(F["title"][0], _ICON_SZ // 2 - 4, "bold"),
                           fill=C["accent"])

        titles = tk.Frame(hdr_inner, bg=C["accent"])
        titles.pack(side="left")
        tk.Label(titles, text=t.get("title", "Truchement"),
                 font=F["title"], bg=C["accent"], fg=C["panel"],
                 anchor="w").pack(anchor="w")
        tk.Label(
            titles,
            text=f"{t.get('about_version', 'Version')} {APP_META['version']}",
            font=F["small"], bg=C["accent"], fg=C["panel"], anchor="w",
        ).pack(anchor="w")

        # ── Auteur & site ────────────────────────────────────────────────────
        meta_row = tk.Frame(self, bg=C["card"], pady=6)
        meta_row.pack(fill="x")
        for key, val in [
            (t.get("about_author", "Author"), APP_META["author"]),
            (t.get("about_site", "Website"),  APP_META["site"]),
        ]:
            row = tk.Frame(meta_row, bg=C["card"])
            row.pack(fill="x", padx=20, pady=2)
            tk.Label(row, text=f"{key} :", bg=C["card"], fg=C["muted"],
                     font=(F["body"][0], F["body"][1], "bold"),
                     width=10, anchor="w").pack(side="left")
            lbl = tk.Label(row, text=val, bg=C["card"], fg=C["text"],
                           font=F["body"], anchor="w")
            lbl.pack(side="left")
            if val.startswith("http"):
                lbl.configure(fg=C["teal"], cursor="hand2")
                lbl.bind("<Button-1>", lambda e, u=val: self._open_url(u))

        # ── Description ──────────────────────────────────────────────────────
        body = tk.Frame(self, bg=C["panel"])
        body.pack(fill="both", expand=True, padx=20, pady=(14, 0))

        txt = tk.Text(
            body, bg=C["panel"], fg=C["text"], font=F["body"],
            relief="flat", bd=0, wrap="word",
            height=5, cursor="arrow",
            selectbackground=C["accent"],
        )
        txt.pack(fill="both", expand=True)
        txt.insert("end", t.get("about_description", ""))
        txt.configure(state="disabled")

        tk.Frame(self, height=1, bg=C["border"]).pack(fill="x", padx=20, pady=10)

        # ── Composants embarqués ─────────────────────────────────────────────
        comp_frame = tk.Frame(self, bg=C["panel"])
        comp_frame.pack(fill="x", padx=20)
        tk.Label(comp_frame, text=t.get("about_components", "Built with") + " :",
                 bg=C["panel"], fg=C["muted"],
                 font=(F["body"][0], F["body"][1], "bold"),
                 anchor="w").pack(fill="x")
        for name, url in APP_META["components"]:
            row = tk.Frame(comp_frame, bg=C["panel"])
            row.pack(fill="x", pady=2)
            lbl_name = tk.Label(row, text=f"  •  {name}",
                                bg=C["panel"], fg=C["accent"],
                                font=F["mono"], cursor="hand2", anchor="w")
            lbl_name.pack(side="left")
            lbl_url = tk.Label(row, text=url, bg=C["panel"], fg=C["muted"],
                               font=F["small"], cursor="hand2", anchor="w")
            lbl_url.pack(side="left", padx=(8, 0))
            for w in (lbl_name, lbl_url):
                w.bind("<Button-1>", lambda e, u=url: self._open_url(u))

        # ── Bouton Fermer ────────────────────────────────────────────────────
        tk.Frame(self, height=1, bg=C["border"]).pack(fill="x", pady=(14, 0))
        close_btn = tk.Button(
            self, text=t.get("about_close", "✕  Close"),
            command=self.destroy,
            bg=C["swap"], fg=C["text"], activebackground=C["border"],
            activeforeground=C["text"], relief="flat", bd=0,
            font=F["btn"], cursor="hand2", pady=8,
        )
        close_btn.pack(pady=12, padx=20, fill="x")

    @staticmethod
    def _open_url(url: str) -> None:
        webbrowser.open(url)
