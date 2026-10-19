"""
ui/llm_window.py — Réglage global du serveur llama.cpp local (bouton ⚙)
=========================================================================
URL et modèle sont partagés (mêmes tk.StringVar) avec l'onglet Livre et
utilisés par Texte 2 quand sa case « Serveur local » est cochée.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import C, F


class LlmSettingsWindow(tk.Toplevel):

    def __init__(self, app) -> None:
        super().__init__(app)
        self.app = app
        t = app._t
        self.title(t.get("llm_title", "Local llama.cpp server"))
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.transient(app)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text=t.get("llm_title", "Local llama.cpp server"),
                  font=F["head"]).grid(row=0, column=0, columnspan=3,
                                       sticky="w", pady=(0, 4))
        ttk.Label(body, text=t.get("llm_hint", ""), style="Mu.TLabel",
                  wraplength=460, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        def row(r, label, var):
            ttk.Label(body, text=label + " :", style="Mu.TLabel").grid(
                row=r, column=0, sticky="w", padx=(0, 8), pady=4)
            fr = tk.Frame(body, bg=C["card"], highlightbackground=C["border"],
                          highlightthickness=1)
            fr.grid(row=r, column=1, columnspan=2, sticky="ew", pady=4)
            e = tk.Entry(fr, textvariable=var, width=40, bg=C["card"],
                         fg=C["text"], insertbackground=C["accent"],
                         relief="flat", font=F["body"], bd=3,
                         selectbackground=C["accent"])
            e.pack(fill="x", expand=True)
            return e

        url_entry = row(2, t.get("book_server", "Server"), app._llm_url)
        row(3, t.get("book_model", "Model"), app._llm_model)

        br = ttk.Frame(body)
        br.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.test_btn = ttk.Button(br, text=t.get("book_test_btn", "Test"),
                                   style="Def.TButton", command=self._test)
        self.test_btn.pack(side="left")
        self.status = ttk.Label(br, text="", style="Mu.TLabel")
        self.status.pack(side="left", padx=10)
        ttk.Button(br, text=t.get("llm_close", "Close"), style="Acc.TButton",
                   command=self._close).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _: self._close())
        self.bind("<Return>", lambda _: self._test())
        url_entry.focus_set()
        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_width()) // 2
        y = app.winfo_rooty() + 120
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()

    def _test(self) -> None:
        self.app._llm_save()
        self.app._llm_test(self.status, self.test_btn)

    def _close(self) -> None:
        self.app._llm_save()
        self.grab_release()
        self.destroy()
