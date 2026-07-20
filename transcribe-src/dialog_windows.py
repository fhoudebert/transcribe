"""
dialog_windows.py  —  ChoiceDialog et DownloadWindow.
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


class ChoiceDialog(tk.Toplevel):
    """
    Dialogue modal proposant N actions après un traitement.
    extra_widget : callable(parent) optionnel inséré après les boutons
                   (ex : sélecteur de langue pour relancer une traduction).
    """

    _COLORS = [ACCENT, GREEN, WARN, DANGER, BG4]

    def __init__(self, parent, title: str, message: str,
                 choices: list[tuple], extra_widget=None):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=BG2)
        self.resizable(False, False)
        self.grab_set()
        self.focus_set()

        self.update_idletasks()
        w = 460
        extra_h = 50 if extra_widget else 0
        h = 170 + len(choices) * 50 + extra_h
        px = parent.winfo_x() + parent.winfo_width()  // 2
        py = parent.winfo_y() + parent.winfo_height() // 2
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

        font_big = ("Segoe UI" if IS_WINDOWS else "Helvetica Neue", 22)
        tk.Label(self, text="✅", font=font_big, bg=BG2).pack(pady=(18, 2))
        tk.Label(self, text=title,   font=FONT_H2, bg=BG2, fg=FG).pack()
        tk.Label(self, text=message, font=FONT_UI,  bg=BG2, fg=FG2,
                 wraplength=420, justify="center").pack(pady=(6, 12))
        tk.Frame(self, height=1, bg=BORDER).pack(fill="x", padx=20)

        area = tk.Frame(self, bg=BG2)
        area.pack(pady=10, padx=20, fill="x")

        for i, (label, action) in enumerate(choices):
            col = self._COLORS[i % len(self._COLORS)]
            fg  = FG if col != BG4 else FG2
            def cb(a=action):
                self.destroy()
                a()
            mkbtn(area, label, cb, color=col, fg=fg).pack(fill="x", pady=3)

        # Widget supplémentaire optionnel (ex : sélecteur de langue)
        if extra_widget:
            tk.Frame(self, height=1, bg=BORDER).pack(fill="x", padx=20,
                                                      pady=(6, 0))
            extra_widget(self)




# ──────────────────────────────────────────────────────────────
#  DownloadWindow  —  téléchargement d'une vidéo via URL
# ──────────────────────────────────────────────────────────────


class DownloadWindow(tk.Toplevel):
    """
    Fenêtre modale de téléchargement via yt-dlp (download_url.sh/.bat).
    Affiche la progression en temps réel dans un journal.
    À la fin, charge le fichier téléchargé dans la fenêtre principale.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._parent  = parent
        self._proc    = None
        self._outfile = None

        self.title(t("url_title"))
        self.configure(bg=BG2)
        self.resizable(True, False)
        self.grab_set()
        self.focus_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.update_idletasks()
        w, h = 580, 420
        px = parent.winfo_x() + parent.winfo_width()  // 2
        py = parent.winfo_y() + parent.winfo_height() // 2
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

        self._build()

    def _build(self):
        # En-tête
        tk.Label(self, text="⬇  " + t("url_title"),
                 font=FONT_H1, bg=BG2, fg=FG).pack(pady=(16, 2))
        tk.Label(self, text=t("url_subtitle"),
                 font=FONT_SMALL, bg=BG2, fg=FG2).pack()
        tk.Frame(self, height=1, bg=BORDER).pack(fill="x", padx=20, pady=10)

        # URL
        url_row = tk.Frame(self, bg=BG2)
        url_row.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(url_row, text=t("url_label"),
                 bg=BG2, fg=FG2, font=FONT_UI, width=22,
                 anchor="w").pack(side="left")
        self._url_var = tk.StringVar()
        tk.Entry(url_row, textvariable=self._url_var,
                 bg=BG3, fg=FG, insertbackground=FG,
                 relief="flat", bd=0, font=FONT_UI,
                 highlightthickness=1,
                 highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(
            side="left", fill="x", expand=True, ipady=6)

        # Dossier de destination
        dir_row = tk.Frame(self, bg=BG2)
        dir_row.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(dir_row, text=t("url_outdir"),
                 bg=BG2, fg=FG2, font=FONT_UI, width=22,
                 anchor="w").pack(side="left")
        self._dir_var = tk.StringVar(value=self._parent.root_dir)
        tk.Entry(dir_row, textvariable=self._dir_var,
                 bg=BG3, fg=FG, insertbackground=FG,
                 relief="flat", bd=0, font=FONT_UI,
                 highlightthickness=1,
                 highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(
            side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        mkbtn(dir_row, t("url_outdir_browse"),
              self._browse_dir, color=BG4, fg=FG).pack(side="left")

        tk.Frame(self, height=1, bg=BORDER).pack(fill="x", padx=20, pady=(0, 8))

        # Journal
        log_frame = tk.Frame(self, bg=BG3,
                             highlightthickness=1, highlightbackground=BORDER)
        log_frame.pack(fill="both", expand=True, padx=20)
        self._log = tk.Text(
            log_frame, bg=BG3, fg=FG2,
            font=FONT_MONO, relief="flat", bd=0,
            state="disabled", wrap="word", height=8)
        vsb = tk.Scrollbar(log_frame, command=self._log.yview,
                           bg=BG3, troughcolor=BG3, width=10)
        self._log.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._log.pack(fill="both", expand=True, padx=6, pady=6)

        # Statut + boutons
        tk.Frame(self, height=1, bg=BORDER).pack(fill="x", padx=20, pady=(8, 0))
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var,
                 bg=BG2, fg=FG2, font=FONT_SMALL).pack(pady=(4, 2))

        self._btn_row = tk.Frame(self, bg=BG2)
        self._btn_row.pack(pady=(4, 14), padx=20, fill="x")
        self._btn_dl = mkbtn(self._btn_row, t("url_download"),
                             self._start, color=ACCENT)
        self._btn_dl.pack(side="left", expand=True, fill="x", padx=(0, 8))
        mkbtn(self._btn_row, t("url_cancel"),
              self._on_close, color=BG4, fg=FG).pack(side="left")

    def _browse_dir(self):
        d = filedialog.askdirectory(
            title=t("url_outdir"),
            initialdir=self._dir_var.get())
        if d:
            self._dir_var.set(d)

    def _log_line(self, txt: str):
        self._log.configure(state="normal")
        self._log.insert("end", txt + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _ytdlp_bin(self) -> str:
        ext = ".exe" if IS_WINDOWS else ""
        return os.path.join(
            self._parent.root_dir, "build", "yt-dlp", f"yt-dlp{ext}")

    def _script(self) -> list[str]:
        if IS_WINDOWS:
            bat = os.path.normpath(
                os.path.join(self._parent.root_dir, "download_url.bat"))
            return ["cmd", "/c", bat]
        return ["bash",
                os.path.join(self._parent.root_dir, "download_url.sh")]

    def _start(self):
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning(t("url_err_title"),
                                   t("url_err_empty"), parent=self)
            return

        # Vérifier yt-dlp
        ytdlp = self._ytdlp_bin()
        if not os.path.isfile(ytdlp):
            messagebox.showerror(t("url_err_title"),
                                 t("url_err_ytdlp", path=ytdlp),
                                 parent=self)
            return

        outdir = self._dir_var.get().strip() or self._parent.root_dir
        os.makedirs(outdir, exist_ok=True)

        self._btn_dl.config(state="disabled")
        self._status_var.set(t("url_running"))
        self._log_line(f"{t('url_log_start')} : {url}")
        self._log_line(f"→ {outdir}")
        self._log_line("─" * 56)

        cmd = self._script() + [url, outdir]
        threading.Thread(target=self._worker, args=(cmd,),
                         daemon=True).start()

    def _worker(self, cmd: list):
        outfile = None
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=self._parent.root_dir,
                creationflags=NO_WINDOW)

            for line in self._proc.stdout:
                line = line.rstrip()
                # Détecter le marqueur OUTFILE émis par le script
                if line.startswith("OUTFILE:"):
                    outfile = line[len("OUTFILE:"):].strip()
                self.after(0, self._log_line, line)

            self._proc.wait()

            if self._proc.returncode == 0:
                self.after(0, self._on_success, outfile)
            else:
                self.after(0, self._on_error,
                           self._proc.returncode)
        except Exception as e:
            self.after(0, self._log_line, f"✘ {e}")
            self.after(0, self._status_var.set, f"✘ {e}")

    def _on_success(self, outfile: str | None):
        """
        Téléchargement terminé : affiche les boutons d'action directement
        dans la fenêtre (pas de ChoiceDialog enfant pour éviter les
        conflits de grab_set).
        """
        self._proc = None  # process terminé

        if outfile and os.path.isfile(outfile):
            self._outfile = outfile
            name = os.path.basename(outfile)
            self._status_var.set(t("url_done", name=name))
            self._log_line(f"\n✔  {t('url_done', name=name)}")
        else:
            self._outfile = None
            self._status_var.set(t("url_done_no_file"))
            self._log_line(f"\n{t('url_done_no_file')}")

        # Remplace le bouton Télécharger par les boutons de résultat
        self._btn_dl.pack_forget()
        self._show_result_buttons()

    def _show_result_buttons(self):
        """Affiche les boutons post-téléchargement dans btn_row."""
        row = self._btn_row
        for w in row.winfo_children():
            w.destroy()

        if self._outfile:
            mkbtn(row, t("btn_load_main"),
                  self._load_in_main,
                  color=ACCENT).pack(side="left", expand=True,
                                     fill="x", padx=(0, 6))
            mkbtn(row, t("url_open_location"),
                  self._open_location,
                  color=BG4, fg=FG).pack(side="left", expand=True,
                                          fill="x", padx=(0, 6))

        mkbtn(row, t("url_download_other"),
              self._reset_for_new,
              color="#1a4a1a", fg=FG).pack(side="left", expand=True,
                                           fill="x", padx=(0, 6))
        mkbtn(row, t("url_cancel"),
              self._on_close,
              color=BG4, fg=FG).pack(side="left")

    def _open_location(self):
        """Ouvre le dossier contenant le fichier téléchargé."""
        if not self._outfile:
            return
        folder = os.path.dirname(os.path.abspath(self._outfile))
        try:
            if IS_WINDOWS:
                # Ouvre l'Explorateur et sélectionne le fichier
                subprocess.Popen(
                    ["explorer", "/select,", os.path.normpath(self._outfile)],
                    creationflags=NO_WINDOW)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", self._outfile])
            else:
                # Linux : xdg-open sur le dossier (pas de sélection native)
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror(t("err_generic"), str(e), parent=self)

    def _load_in_main(self):
        if self._outfile:
            name = os.path.basename(self._outfile)
            self._parent.video_path.set(self._outfile)
            self._parent._log_line(
                f"⬇  {t('url_loaded', name=name)}")
        self.destroy()

    def _reset_for_new(self):
        """Réinitialise la fenêtre pour un nouveau téléchargement."""
        self._outfile = None
        self._proc    = None
        self._url_var.set("")
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._status_var.set("")
        # Remet le bouton Télécharger
        row = self._btn_row
        for w in row.winfo_children():
            w.destroy()
        self._btn_dl = mkbtn(row, t("url_download"),
                             self._start, color=ACCENT)
        self._btn_dl.pack(side="left", expand=True,
                          fill="x", padx=(0, 8))
        mkbtn(row, t("url_cancel"),
              self._on_close, color=BG4, fg=FG).pack(side="left")

    def _on_error(self, code: int):
        msg = f"✘  {t('url_err_title')} (code {code})"
        self._status_var.set(msg)
        self._log_line(f"\n{msg}")
        self._btn_dl.config(state="normal")

    def _on_close(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self.destroy()

# ──────────────────────────────────────────────────────────────
#  RecorderWindow  —  dictaphone
# ──────────────────────────────────────────────────────────────
