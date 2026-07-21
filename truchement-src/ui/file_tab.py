"""
ui/file_tab.py — Onglet traduction de fichier
===============================================
FileTabMixin fournit toutes les méthodes relatives à l'onglet Fichier.
Il est mélangé dans TranslatorApp (via héritage multiple).

Méthodes publiques :
    build_file_tab(parent)   → construit les widgets, stocke refs dans self
    _pick_file()             → filedialog
    _translate_file()        → lance la traduction en thread
    _file_done(out, err)     → callback thread → UI
    _open_folder()           → ouvre l'explorateur de fichiers
    _file_err_msg(err) → str → traduit un code d'erreur en message localisé
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import bootstrap
from config import C, F, LANG_NAMES
from translator import translate_file, TIMEOUT_FILE


class FileTabMixin:

    # ── Construction ──────────────────────────────────────────────────────────

    def build_file_tab(self, parent: ttk.Frame) -> None:
        self._file_path:     tk.StringVar = tk.StringVar(value="")
        self._file_out_path: tk.StringVar = tk.StringVar(value="")

        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True, padx=32, pady=24)
        outer.columnconfigure(0, weight=1)

        # Titre
        tr_row = ttk.Frame(outer)
        tr_row.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        self._file_lbl_title = ttk.Label(
            tr_row, text="", font=F["title"],
            foreground=C["text"], background=C["bg"],
        )
        self._file_lbl_title.pack(side="left")

        # Formats supportés
        self._file_lbl_fmt = ttk.Label(outer, text="", style="Mu.TLabel")
        self._file_lbl_fmt.grid(row=1, column=0, sticky="w", pady=(0, 18))

        # Sélecteur de fichier source
        pf = tk.Frame(outer, bg=C["card"],
                      highlightbackground=C["border"], highlightthickness=1)
        pf.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        pf.columnconfigure(1, weight=1)

        self._file_pick_btn = ttk.Button(
            pf, text="", style="Ghost.TButton", command=self._pick_file,
        )
        self._file_pick_btn.grid(row=0, column=0, padx=(8, 0), pady=8)

        self._file_src_lbl = ttk.Label(
            pf, textvariable=self._file_path,
            background=C["card"], foreground=C["muted"],
            font=F["body"], anchor="w",
        )
        self._file_src_lbl.grid(row=0, column=1, sticky="ew", padx=12)

        # Fichier de sortie
        of = ttk.Frame(outer)
        of.grid(row=3, column=0, sticky="ew", pady=(0, 24))
        of.columnconfigure(1, weight=1)

        self._file_out_head = ttk.Label(of, text="", style="Mu.TLabel")
        self._file_out_head.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self._file_out_val = ttk.Label(
            of, textvariable=self._file_out_path,
            foreground=C["teal"], background=C["bg"],
            font=F["body"], anchor="w",
        )
        self._file_out_val.grid(row=0, column=1, sticky="ew")

        # Barre de progression (masquée par défaut)
        self._file_progress = ttk.Progressbar(
            outer, mode="indeterminate", length=400,
        )
        self._file_progress.grid(row=4, column=0, sticky="ew", pady=(0, 18))
        self._file_progress.grid_remove()

        # Boutons d'action
        br = ttk.Frame(outer)
        br.grid(row=5, column=0, sticky="w", pady=(4, 0))

        self._file_tr_btn = ttk.Button(
            br, text="", style="Acc.TButton", command=self._translate_file,
        )
        self._file_tr_btn.pack(side="left", padx=(0, 10))

        self._file_open_btn = ttk.Button(
            br, text="", style="Ghost.TButton",
            command=self._open_folder, state="disabled",
        )
        self._file_open_btn.pack(side="left")

        # Statut / erreur inline
        self._file_status_lbl = ttk.Label(
            outer, text="", foreground=C["teal"],
            background=C["bg"], font=F["small"],
            wraplength=700, justify="left",
        )
        self._file_status_lbl.grid(row=6, column=0, sticky="w", pady=(16, 0))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _pick_file(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title=self._t.get("file_pick_btn", "Choose file"),
            filetypes=[
                ("All supported", "*.txt *.html *.htm *.srt *.docx *.pdf"),
                ("Text files",    "*.txt"),
                ("HTML files",    "*.html *.htm"),
                ("SubRip",        "*.srt"),
                ("Word documents","*.docx"),
                ("PDF files",     "*.pdf"),
                ("All files",     "*.*"),
            ],
        )
        if path:
            self._file_path.set(path)
            self._file_out_path.set("")
            self._file_src_lbl.configure(foreground=C["text"])
            self._file_open_btn.configure(state="disabled")
            self._file_status_lbl.configure(text="")

    def _translate_file(self) -> None:
        from config import lang_code
        src_c = lang_code(self.cb_src.get())
        tgt_c = lang_code(self.cb_tgt.get())
        if not src_c or not tgt_c:
            messagebox.showwarning(self._t["error_title"], self._t["select_langs"])
            return
        fpath = self._file_path.get().strip()
        placeholder = self._t.get("file_none", "")
        if not fpath or fpath == placeholder:
            messagebox.showinfo(
                self._t["error_title"],
                self._t.get("file_no_file", "No file selected."),
            )
            return

        self._file_tr_btn.configure(
            text=self._t.get("file_translating", "…"), state="disabled",
        )
        self._file_pick_btn.configure(state="disabled")
        self._file_open_btn.configure(state="disabled")
        self._file_out_path.set("")
        self._file_progress.grid()
        self._file_progress.start(12)

        # Chronomètre partagé : met à jour à la fois la barre de statut
        # générale (en bas à gauche) ET le libellé inline de l'onglet
        # Fichier, pour que l'attente — potentiellement longue au premier
        # chargement du modèle ou sur un fichier volumineux — reste
        # explicite quel que soit l'endroit où l'utilisateur regarde.
        def _on_tick(elapsed: int, msg: str) -> None:
            self._file_status_lbl.configure(text=msg, foreground=C["muted"])

        self._start_progress_timer(
            "file",
            base_key="file_translating",
            elapsed_key="file_translating_elapsed",
            slow_key="file_translating_slow",
            timeout_soon_key="file_translating_timeout_soon",
            timeout_total=TIMEOUT_FILE,
            on_tick=_on_tick,
        )

        def run() -> None:
            try:
                out = translate_file(src_c, tgt_c, fpath)
                self.after(0, lambda: self._file_done(out, None))
            except RuntimeError as exc:
                self.after(0, lambda e=str(exc): self._file_done(None, e))

        threading.Thread(target=run, daemon=True).start()

    def _file_done(self, out_path: str | None, err: str | None) -> None:
        self._stop_progress_timer("file")
        self._file_progress.stop()
        self._file_progress.grid_remove()
        self._file_tr_btn.configure(
            text=self._t.get("file_translate_btn", "Translate file →"),
            state="normal",
        )
        self._file_pick_btn.configure(state="normal")
        self.lbl_status.configure(text="")

        if err:
            msg = self._file_err_msg(err)
            self._file_status_lbl.configure(text=msg, foreground=C["swap"])
            messagebox.showerror(self._t["error_title"], msg)
        else:
            self._file_out_path.set(out_path or "")
            self._file_open_btn.configure(state="normal")
            msg = self._t.get("file_success", "File translated: {path}").format(
                path=out_path,
            )
            self._file_status_lbl.configure(text=msg, foreground=C["teal"])
            self.lbl_status.configure(text=msg)
            self.after(5000, lambda: self.lbl_status.configure(text=""))

    def _file_err_msg(self, err: str) -> str:
        t = self._t
        if err == "NO_VENV_PYTHON":
            return self._venv_missing_msg()
        if err.startswith("SYS_PATH_ONLY:"):
            return self._sys_path_only_msg(err.split(":", 1)[1])
        if err == "IMPORT_BS4":
            return (
                "BeautifulSoup4 is not installed.\n\n"
                "Install with: pip install beautifulsoup4 lxml"
            )
        if err == "IMPORT_FILES":
            return t.get("error_file_pkg", "argostranslatefiles not installed.")
        if err in ("IMPORT_ERROR", "NO_LANGUAGES"):
            return self._venv_import_msg(t)
        if err.startswith("NO_PKG:"):
            _, sc, tc = err.split(":")
            return t.get("error_no_pkg", "No package for {src}→{tgt}.").format(
                src=LANG_NAMES.get(sc, sc), tgt=LANG_NAMES.get(tc, tc),
            )
        if err.startswith("NO_LANG:"):
            _, lc_ = err.split(":", 1)
            return t.get("error_no_pkg", "No package for {src}→{tgt}.").format(
                src=LANG_NAMES.get(lc_, lc_), tgt="?",
            )
        if err.startswith("SUBPROCESS:"):
            detail = err.split(":", 1)[1]
            return t.get("error_file_trans",
                         "File translation failed:\n{err}").format(err=detail)
        return t.get("error_file_trans",
                     "File translation failed:\n{err}").format(err=err)

    def _open_folder(self) -> None:
        import subprocess
        import sys as _sys
        path = self._file_out_path.get()
        if not path:
            return
        folder = os.path.dirname(os.path.abspath(path))
        if _sys.platform.startswith("win"):
            subprocess.Popen(["explorer", folder])
        elif _sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
