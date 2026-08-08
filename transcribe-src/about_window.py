"""
about_window.py  —  Fenêtre "À propos" de l'application.
Dépendances internes : app_config, app_styles, i18n
"""
import os
import re
import sys
import shutil
import threading
import datetime
import tempfile
import subprocess

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from app_config import (
    IS_WINDOWS, NO_WINDOW, MODELS,
    ALL_LANGUAGES, LANG_NAMES, lang_label, lang_code,
)
from i18n import t
from app_styles import (
    BG, BG2, BG3, BG4, ACCENT, GREEN, WARN, DANGER, FG, FG2, BORDER,
    FONT_MONO, FONT_UI, FONT_H1, FONT_H2, FONT_SMALL,
    mkbtn, _adj,
)


# Métadonnées de l'application
APP_META = {
    "version": "0.3",
    "author":  "François Houdebert",
    "site":    "https://github.com/fhoudebert/transcribe/",
    "components": [
        ("ffmpeg",          "https://ffmpeg.org"),
        ("whisper.cpp",     "https://github.com/ggerganov/whisper.cpp"),
        ("argos-translate", "https://github.com/argosopentech/argos-translate"),
        ("yt-dlp",          "https://github.com/yt-dlp/yt-dlp"),
    ],
}


class AboutWindow(tk.Toplevel):
    """
    Fenêtre modale "À propos".
    Ouverte via le bouton ℹ dans le bandeau de la fenêtre principale.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title(t("about_title"))
        self.configure(bg=BG2)
        self.resizable(False, False)
        self.grab_set()
        self.focus_set()

        self.update_idletasks()
        w, h = 540, 680
        px = parent.winfo_x() + parent.winfo_width()  // 2
        py = parent.winfo_y() + parent.winfo_height() // 2
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

        self._build()

    def _build(self):
        # ── En-tête : icône 48×48 + titre ────────────────────
        # Taille STRICTEMENT limitée à 48×48.
        # subsample calculé depuis la taille réelle du PNG
        # pour garantir qu'on n'affiche jamais l'image native 512×512.
        ICON_SZ = 48
        about_icon = None
        assets_dir = os.path.join(self.master.root_dir, "assets")
        for png in ("icone.png", "icon.png"):
            p = os.path.join(assets_dir, png)
            if not os.path.isfile(p):
                continue
            try:
                from PIL import Image, ImageTk
                img = Image.open(p).resize((ICON_SZ, ICON_SZ), Image.LANCZOS)
                about_icon = ImageTk.PhotoImage(img)
                self._about_icon = about_icon
            except ImportError:
                try:
                    raw = tk.PhotoImage(file=p)
                    # Subsample forcé pour toujours obtenir ≤ ICON_SZ px
                    w_raw = raw.width()
                    h_raw = raw.height()
                    factor = max(1, max(w_raw, h_raw) // ICON_SZ)
                    if factor > 1:
                        raw = raw.subsample(factor, factor)
                    about_icon = raw
                    self._about_icon = raw
                except Exception:
                    pass
            except Exception:
                pass
            if about_icon:
                break

        hdr = tk.Frame(self, bg=ACCENT, pady=12)
        hdr.pack(fill="x")
        hdr_inner = tk.Frame(hdr, bg=ACCENT)
        hdr_inner.pack(padx=20, anchor="w")

        # Canvas fixe 48×48 pour l'icône — garantit la taille même sans image
        icon_frame = tk.Frame(hdr_inner, bg=ACCENT,
                              width=ICON_SZ, height=ICON_SZ)
        icon_frame.pack_propagate(False)   # taille rigide
        icon_frame.pack(side="left", padx=(0, 14))

        if about_icon:
            tk.Label(icon_frame, image=about_icon,
                     bg=ACCENT, bd=0,
                     width=ICON_SZ, height=ICON_SZ).pack()
        else:
            c = tk.Canvas(icon_frame, width=ICON_SZ, height=ICON_SZ,
                          bg=ACCENT, highlightthickness=0)
            c.pack()
            c.create_oval(3, 3, ICON_SZ-3, ICON_SZ-3, fill=BG2, outline="")
            c.create_text(ICON_SZ//2, ICON_SZ//2, text="T",
                          font=(FONT_H1[0], ICON_SZ//2-4, "bold"), fill=ACCENT)

        titles = tk.Frame(hdr_inner, bg=ACCENT)
        titles.pack(side="left")
        tk.Label(titles, text=t("app_title"),
                 font=FONT_H1, bg=ACCENT, fg=BG2,
                 anchor="w").pack(anchor="w")
        tk.Label(titles,
                 text=f"{t('about_version')} {APP_META['version']}",
                 font=FONT_SMALL, bg=ACCENT, fg=BG2,
                 anchor="w").pack(anchor="w")

        # ── Auteur & site (sous l'en-tête, bien visibles) ────
        meta_row = tk.Frame(self, bg=BG3, pady=6)
        meta_row.pack(fill="x")
        for key, val in [
            (t("about_author"), APP_META["author"]),
            (t("about_site"),   APP_META["site"]),
        ]:
            row = tk.Frame(meta_row, bg=BG3)
            row.pack(fill="x", padx=20, pady=1)
            tk.Label(row, text=f"{key} :", bg=BG3, fg=FG2,
                     font=(FONT_UI[0], FONT_UI[1], "bold"),
                     width=10, anchor="w").pack(side="left")
            lbl = tk.Label(row, text=val, bg=BG3, fg=FG,
                           font=FONT_UI, anchor="w")
            lbl.pack(side="left")
            if val.startswith("http"):
                lbl.config(fg=ACCENT, cursor="hand2")
                lbl.bind("<Button-1>",
                         lambda e, u=val: self._open_url(u))

        # ── Description ───────────────────────────────────────
        body = tk.Frame(self, bg=BG2)
        body.pack(fill="both", expand=True, padx=20, pady=(10, 0))

        txt = tk.Text(
            body, bg=BG2, fg=FG, font=FONT_UI,
            relief="flat", bd=0, wrap="word",
            height=9, cursor="arrow",
            selectbackground=ACCENT)
        vsb = tk.Scrollbar(body, command=txt.yview,
                           bg=BG3, troughcolor=BG3, width=8)
        txt.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        txt.insert("end", t("about_description"))
        txt.configure(state="disabled")

        tk.Frame(self, height=1, bg=BORDER).pack(fill="x", padx=20,
                                                  pady=8)

        # ── Composants embarqués ──────────────────────────────
        comp_frame = tk.Frame(self, bg=BG2)
        comp_frame.pack(fill="x", padx=20)
        tk.Label(comp_frame, text=t("about_components") + " :",
                 bg=BG2, fg=FG2,
                 font=(FONT_UI[0], FONT_UI[1], "bold"),
                 anchor="w").pack(fill="x")
        for name, url in APP_META["components"]:
            row = tk.Frame(comp_frame, bg=BG2)
            row.pack(fill="x", pady=1)
            lbl_name = tk.Label(row, text=f"  •  {name}",
                                bg=BG2, fg=ACCENT,
                                font=FONT_MONO, cursor="hand2", anchor="w")
            lbl_name.pack(side="left")
            lbl_url = tk.Label(row, text=url, bg=BG2, fg=FG2,
                               font=FONT_SMALL, cursor="hand2", anchor="w")
            lbl_url.pack(side="left", padx=(8, 0))
            for w in (lbl_name, lbl_url):
                w.bind("<Button-1>", lambda e, u=url: self._open_url(u))

        # ── Bouton Fermer ─────────────────────────────────────
        tk.Frame(self, height=1, bg=BORDER).pack(fill="x", pady=(10, 0))
        mkbtn(self, "✕  " + t("url_cancel"),
              self.destroy, color=BG4, fg=FG).pack(
            pady=10, padx=20, fill="x")

    @staticmethod
    def _open_url(url: str):
        import webbrowser
        webbrowser.open(url)
