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
    dialog_start,
)
from i18n import t, get_locale
from app_styles import (
    BG, BG2, BG3, BG4, ACCENT, GREEN, WARN, DANGER, FG, FG2, BORDER,
    FONT_MONO, FONT_UI, FONT_H1, FONT_H2, FONT_SMALL,
    mkbtn, _adj,
)
import ytdlp_probe as probe


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

        # Résultat de l'analyse (bouton « Analyser ») et sélection en cours
        self._probe_res: probe.ProbeResult | None = None
        self._probed_url = ""
        self._probing = False
        self._sub_codes: list[str] = []
        self._auto_codes: list[str] = []
        self._audio_codes: list[str] = []
        self._auto_open = False          # sous-titres automatiques : repliés
        self._run_audio_langs: list[str] = []
        self._run_opts_active = False

        self.title(t("url_title"))
        self.configure(bg=BG2)
        self.resizable(True, False)
        self.grab_set()
        self.focus_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Hauteur libre : la fenêtre s'agrandit quand les listes d'options
        # apparaissent (largeur seule imposée, position centrée sur le parent).
        self.update_idletasks()
        w = 580
        self.minsize(w, 440)
        px = parent.winfo_x() + parent.winfo_width()  // 2
        py = parent.winfo_y() + parent.winfo_height() // 2
        self.geometry(f"{w}x440+{px - w//2}+{max(0, py - 300)}")

        self._build()
        # Hauteur naturelle du contenu (le 440 initial n'est qu'un plancher)
        self.update_idletasks()
        self.geometry(f"{w}x{max(440, self.winfo_reqheight())}")

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
        url_entry = tk.Entry(url_row, textvariable=self._url_var,
                 bg=BG3, fg=FG, insertbackground=FG,
                 relief="flat", bd=0, font=FONT_UI,
                 highlightthickness=1,
                 highlightbackground=BORDER,
                 highlightcolor=ACCENT)
        url_entry.pack(side="left", fill="x", expand=True, ipady=6)
        url_entry.bind("<Return>", lambda _e: self._analyze())
        self._btn_probe = mkbtn(url_row, t("url_analyze"),
                                self._analyze, color=BG4, fg=FG)
        self._btn_probe.pack(side="left", padx=(6, 0))
        # Toute modification de l'URL invalide l'analyse précédente
        self._url_var.trace_add("write", self._on_url_edit)

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

        # Options issues de l'analyse : sous-titres, pistes audio
        self._build_options()

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
        self._build_dl_buttons(self._btn_row)

    def _build_dl_buttons(self, row):
        """
        Boutons de téléchargement :
          • « Télécharger »          — rapide, sans analyse ni options
                                       (comportement historique) ;
          • « Télécharger la sélection » — avec les sous-titres / pistes
                                       audio cochés (après « Analyser »).
        """
        self._btn_dl = mkbtn(row, t("url_download"),
                             lambda: self._start(False), color=ACCENT)
        self._btn_dl.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._btn_sel = mkbtn(row, t("url_download_sel"),
                              lambda: self._start(True), color=BG4, fg=FG)
        self._btn_sel.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self._btn_sel.config(state="normal" if self._probe_res else "disabled")
        mkbtn(row, t("url_cancel"),
              self._on_close, color=BG4, fg=FG).pack(side="left")

    def _set_dl_state(self, running: bool):
        self._btn_dl.config(state="disabled" if running else "normal")
        self._btn_sel.config(
            state="normal" if (self._probe_res and not running)
            else "disabled")

    # ── Options issues de l'analyse ────────────────────────────

    def _opt_check(self, parent, text, var, command):
        return tk.Checkbutton(
            parent, text=text, variable=var, command=command,
            bg=BG2, fg=FG, selectcolor=BG3,
            activebackground=BG2, activeforeground=FG,
            disabledforeground=BG4, font=FONT_UI,
            cursor="hand2", anchor="w", state="disabled")

    def _make_list(self, parent, height):
        """Liste à sélection multiple avec ascenseur → (cadre, Listbox)."""
        frame = tk.Frame(parent, bg=BG3, highlightthickness=1,
                         highlightbackground=BORDER)
        lb = tk.Listbox(
            frame, selectmode="multiple", exportselection=False,
            height=height, bg=BG3, fg=FG, font=FONT_UI,
            selectbackground=ACCENT, selectforeground=FG,
            activestyle="none", relief="flat", bd=0, highlightthickness=0)
        vsb = tk.Scrollbar(frame, command=lb.yview, bg=BG3,
                           troughcolor=BG3, width=10)
        lb.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True, padx=4, pady=3)
        return frame, lb

    def _build_options(self):
        self._opt = tk.Frame(self, bg=BG2)
        self._opt.pack(fill="x", padx=20, pady=(0, 6))
        self._opt.columnconfigure(0, weight=1)

        # — Sous-titres (rangée 0 : case ; rangée 1 : listes, masquées)
        self._subs_on = tk.BooleanVar(value=False)
        row = tk.Frame(self._opt, bg=BG2)
        row.grid(row=0, column=0, sticky="ew")
        self._cb_subs = self._opt_check(
            row, t("url_opt_subs"), self._subs_on, self._refresh_options)
        self._cb_subs.pack(side="left")
        self._lbl_subs = tk.Label(row, text="", bg=BG2, fg=FG2,
                                  font=FONT_SMALL)
        self._lbl_subs.pack(side="left", padx=(8, 0))

        self._subs_box = tk.Frame(self._opt, bg=BG2)
        self._subs_frame, self._lb_subs = self._make_list(self._subs_box, 5)
        self._lbl_auto = tk.Label(self._subs_box, text="", bg=BG2,
                                  fg=ACCENT, font=FONT_SMALL,
                                  cursor="hand2", anchor="w")
        self._lbl_auto.bind("<Button-1>", lambda _e: self._toggle_auto())
        self._auto_frame, self._lb_auto = self._make_list(self._subs_box, 4)

        # — Pistes audio (rangée 2 : case ; rangée 3 : liste, masquée)
        self._audio_on = tk.BooleanVar(value=False)
        row = tk.Frame(self._opt, bg=BG2)
        row.grid(row=2, column=0, sticky="ew")
        self._cb_audio = self._opt_check(
            row, t("url_opt_audio"), self._audio_on, self._refresh_options)
        self._cb_audio.pack(side="left")
        self._lbl_audio = tk.Label(row, text="", bg=BG2, fg=FG2,
                                   font=FONT_SMALL)
        self._lbl_audio.pack(side="left", padx=(8, 0))

        self._audio_box = tk.Frame(self._opt, bg=BG2)
        self._audio_frame, self._lb_audio = self._make_list(self._audio_box, 3)
        self._audio_frame.pack(fill="x")
        # La piste par défaut (index 0) ne peut pas être décochée : on
        # AJOUTE des pistes à celle que yt-dlp retiendrait de toute façon.
        self._lb_audio.bind("<<ListboxSelect>>", self._keep_default_audio)

        self._reset_opts()

    def _lang_name(self, code: str, name: str = "") -> str:
        """« fr — Français » : nom fourni par yt-dlp, sinon table de l'app."""
        base = code.split("-")[0].lower()
        label = name or LANG_NAMES.get(base, "")
        return f"{code} — {label}" if label else code

    def _keep_default_audio(self, _e=None):
        if self._audio_codes:
            self._lb_audio.selection_set(0)

    def _toggle_auto(self):
        self._auto_open = not self._auto_open
        self._refresh_options()

    def _fit_height(self):
        """Ajuste la hauteur au contenu (une géométrie explicite fige Tk)."""
        self.update_idletasks()
        self.geometry(f"{self.winfo_width()}x"
                      f"{max(440, self.winfo_reqheight())}")

    def _refresh_options(self):
        """Affiche/masque les listes selon les cases et l'analyse."""
        res = self._probe_res
        # Sous-titres : manuels + replis « automatiques »
        for w in (self._subs_frame, self._lbl_auto, self._auto_frame):
            w.pack_forget()
        if res and self._subs_on.get() and (self._sub_codes or self._auto_codes):
            if self._sub_codes:
                self._subs_frame.pack(fill="x")
            if self._auto_codes:
                arrow = "▾" if self._auto_open else "▸"
                self._lbl_auto.config(
                    text=f"{arrow} " + t("url_auto_toggle",
                                         n=len(self._auto_codes)))
                self._lbl_auto.pack(fill="x", pady=(4, 0))
                if self._auto_open:
                    self._auto_frame.pack(fill="x", pady=(2, 0))
            self._subs_box.grid(row=1, column=0, sticky="ew", pady=(2, 4))
        else:
            self._subs_box.grid_remove()
        # Pistes audio
        if res and self._audio_on.get() and len(self._audio_codes) >= 2:
            self._audio_box.grid(row=3, column=0, sticky="ew", pady=(2, 4))
        else:
            self._audio_box.grid_remove()
        self._fit_height()

    def _reset_opts(self):
        """Retour à l'état « pas encore analysé » (options inactives)."""
        self._probe_res = None
        self._probed_url = ""
        self._sub_codes, self._auto_codes, self._audio_codes = [], [], []
        self._auto_open = False
        self._subs_on.set(False)
        self._audio_on.set(False)
        for lb in (self._lb_subs, self._lb_auto, self._lb_audio):
            lb.delete(0, "end")
        for cb, lbl in ((self._cb_subs, self._lbl_subs),
                        (self._cb_audio, self._lbl_audio)):
            cb.config(state="disabled")
            lbl.config(text=t("url_opt_need_analyze"))
        self._refresh_options()
        if hasattr(self, "_btn_sel"):
            self._btn_sel.config(state="disabled")

    def _on_url_edit(self, *_):
        if self._probed_url and \
                self._url_var.get().strip() != self._probed_url:
            self._reset_opts()

    # ── Analyse ────────────────────────────────────────────────

    def _safe_after(self, fn, *args):
        try:
            self.after(0, fn, *args)
        except (tk.TclError, RuntimeError):
            pass     # fenêtre fermée pendant l'analyse

    def _analyze(self):
        if self._probing:
            return
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning(t("url_err_title"),
                                   t("url_err_empty"), parent=self)
            return
        ytdlp = self._ytdlp_bin()
        if not os.path.isfile(ytdlp):
            messagebox.showerror(t("url_err_title"),
                                 t("url_err_ytdlp", path=ytdlp),
                                 parent=self)
            return
        self._reset_opts()
        self._probing = True
        self._btn_probe.config(state="disabled")
        self._status_var.set(t("url_analyzing"))
        threading.Thread(target=self._probe_worker, args=(ytdlp, url),
                         daemon=True).start()

    def _probe_worker(self, ytdlp: str, url: str):
        try:
            res = probe.run_probe(ytdlp, url, creationflags=NO_WINDOW)
        except probe.ProbeError as e:
            self._safe_after(self._on_probe_error, str(e))
            return
        except Exception as e:                      # jamais de thread muet
            self._safe_after(self._on_probe_error, repr(e))
            return
        self._safe_after(self._on_probe_done, url, res)

    def _on_probe_error(self, msg: str):
        self._probing = False
        self._btn_probe.config(state="normal")
        self._status_var.set("⚠  " + t("url_analyze_failed"))
        self._log_line(f"⚠  {t('url_analyze_failed')}\n    {msg[:300]}")

    def _on_probe_done(self, url: str, res: "probe.ProbeResult"):
        self._probing = False
        self._btn_probe.config(state="normal")
        if self._url_var.get().strip() != url:
            return                  # l'URL a changé pendant l'analyse
        self._probe_res, self._probed_url = res, url
        self._btn_sel.config(state="normal")
        self._sub_codes = [c for c, _ in res.subs]
        self._auto_codes = [c for c, _ in res.auto]
        self._audio_codes = list(res.audio)

        for lb in (self._lb_subs, self._lb_auto, self._lb_audio):
            lb.delete(0, "end")
        for code, name in res.subs:
            self._lb_subs.insert("end", self._lang_name(code, name))
        for code, name in res.auto:
            self._lb_auto.insert("end", self._lang_name(code, name))
        for i, code in enumerate(self._audio_codes):
            label = self._lang_name(code)
            if i == 0:
                label += "  " + t("url_default_track")
            self._lb_audio.insert("end", label)
        if self._audio_codes:
            self._lb_audio.selection_set(0)

        # Présélection : langue de l'interface parmi les sous-titres manuels
        ui = (get_locale() or "").split("-")[0].lower()
        # (exact d'abord ; les variantes « forced » / « acc » — souvent vides
        # ou malentendants — ne sont proposées qu'en dernier recours)
        def _plain(c):
            return not c.lower().endswith(("-forced", "-acc"))
        cands = [i for i, c in enumerate(self._sub_codes)
                 if c.split("-")[0].lower() == ui]
        pick = next((i for i in cands if self._sub_codes[i].lower() == ui),
                    next((i for i in cands if _plain(self._sub_codes[i])),
                         cands[0] if cands else None))
        if pick is not None:
            self._lb_subs.selection_set(pick)

        n_subs, n_auto = len(self._sub_codes), len(self._auto_codes)
        if n_subs or n_auto:
            self._cb_subs.config(state="normal")
            self._lbl_subs.config(
                text=t("url_opt_subs_count", n=n_subs, auto=n_auto))
        else:
            self._lbl_subs.config(text=t("url_opt_subs_none"))
        if len(self._audio_codes) >= 2:
            self._cb_audio.config(state="normal")
            self._lbl_audio.config(
                text=t("url_opt_audio_count", n=len(self._audio_codes)))
        else:
            self._lbl_audio.config(text=t("url_opt_audio_none"))

        self._status_var.set(t("url_probe_ok", n=n_subs + n_auto,
                               audio=len(self._audio_codes)))
        if res.title:
            self._log_line(f"🔍 {res.title}")
        self._refresh_options()

    def _selected(self, lb, codes: list[str]) -> list[str]:
        return [codes[i] for i in lb.curselection() if i < len(codes)]

    def _options_env(self, url: str, with_options: bool = True) -> tuple[dict, list[str]]:
        """
        Variables d'environnement transmises au script de téléchargement,
        d'après les cases cochées. Sans analyse valide pour CETTE url, ou sans
        case cochée : environnement inchangé (comportement historique).
        Renvoie aussi la liste ordonnée des langues audio demandées.
        """
        env = os.environ.copy()
        for k in ("TRANSCRIBE_DL_SUBS", "TRANSCRIBE_DL_AUTOSUBS",
                  "TRANSCRIBE_DL_AUDIO"):
            env.pop(k, None)
        audio: list[str] = []
        if not (with_options and self._probe_res
                and self._probed_url == url):
            return env, audio

        if self._subs_on.get():
            manual = self._selected(self._lb_subs, self._sub_codes)
            auto = self._selected(self._lb_auto, self._auto_codes)
            subs = manual + [c for c in auto if c not in manual]
            if subs:
                env["TRANSCRIBE_DL_SUBS"] = ",".join(subs)
                if auto:
                    env["TRANSCRIBE_DL_AUTOSUBS"] = "1"
        if self._audio_on.get():
            self._keep_default_audio()
            audio = self._selected(self._lb_audio, self._audio_codes)
            if len(audio) >= 2:
                env["TRANSCRIBE_DL_AUDIO"] = ",".join(audio)
            else:
                audio = []
        return env, audio

    def _browse_dir(self):
        # Dossier saisi, ou à défaut son premier parent existant
        # (un initialdir inexistant fait ouvrir la boîte n'importe où).
        initialdir, _ = dialog_start(self._dir_var.get())
        d = filedialog.askdirectory(
            title=t("url_outdir"),
            **({"initialdir": initialdir} if initialdir else {}))
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

    def _start(self, with_options: bool = False):
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

        self._set_dl_state(True)
        self._status_var.set(t("url_running"))
        self._log_line(f"{t('url_log_start')} : {url}")
        self._log_line(f"→ {outdir}")
        self._log_line("─" * 56)

        cmd = self._script() + [url, outdir]
        env, audio = self._options_env(url, with_options)
        self._run_audio_langs = audio
        self._run_opts_active = bool(
            env.get("TRANSCRIBE_DL_SUBS") or env.get("TRANSCRIBE_DL_AUDIO"))
        threading.Thread(target=self._worker, args=(cmd, env),
                         daemon=True).start()

    def _worker(self, cmd: list, env: dict | None = None):
        outfile = None
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=self._parent.root_dir,
                env=env,
                creationflags=NO_WINDOW)

            for line in self._proc.stdout:
                line = line.rstrip()
                # Détecter le marqueur OUTFILE émis par le script
                if line.startswith("OUTFILE:"):
                    outfile = line[len("OUTFILE:"):].strip()
                self.after(0, self._log_line, line)

            self._proc.wait()

            if self._proc.returncode == 0:
                # Options demandées : écarte les SRT vides, rétablit les
                # langues des pistes audio (hors thread Tk : ffmpeg peut
                # durer plusieurs secondes sur un gros fichier).
                if self._run_opts_active and outfile \
                        and os.path.isfile(outfile):
                    events = probe.finalize_download(
                        outfile, self._run_audio_langs,
                        self._parent._ffmpeg(), self._parent._ffprobe(),
                        creationflags=NO_WINDOW)
                    self.after(0, self._log_events, events)
                self.after(0, self._on_success, outfile)
            else:
                self.after(0, self._on_error,
                           self._proc.returncode)
        except Exception as e:
            self.after(0, self._log_line, f"✘ {e}")
            self.after(0, self._status_var.set, f"✘ {e}")

    def _log_events(self, events: list):
        """Traduit les événements de finalize_download en lignes de journal."""
        for ev in events:
            kind = ev[0]
            if kind == "empty_srt":
                self._log_line("🧹 " + t("url_log_empty_srt", name=ev[1]))
            elif kind == "subs":
                self._log_line("💬 " + t("url_log_subs_saved",
                                         names=", ".join(ev[1])))
            elif kind == "audio_tagged":
                self._log_line("🏷  " + t("url_log_audio_tagged", langs=ev[1]))
            elif kind == "audio_tag_failed":
                self._log_line("⚠  " + t("url_log_audio_tag_failed",
                                         why=ev[1]))

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
        self._reset_opts()
        self._run_audio_langs = []
        self._run_opts_active = False
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._status_var.set("")
        # Remet le bouton Télécharger
        row = self._btn_row
        for w in row.winfo_children():
            w.destroy()
        self._build_dl_buttons(row)

    def _on_error(self, code: int):
        msg = f"✘  {t('url_err_title')} (code {code})"
        self._status_var.set(msg)
        self._log_line(f"\n{msg}")
        self._set_dl_state(False)

    def _on_close(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self.destroy()

# ──────────────────────────────────────────────────────────────
#  RecorderWindow  —  dictaphone
# ──────────────────────────────────────────────────────────────
