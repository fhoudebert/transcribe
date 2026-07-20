"""
ui/app.py — Classe principale TranslatorApp
=============================================
Assemble les mixins (FileTabMixin, DefTabMixin) et les fonctions de
construction de panneaux (build_panel) pour produire l'application complète.

Responsabilités de cette classe :
  • Fenêtre principale, style ttk, notebook
  • Barre de langues (source, cible, swap)
  • Sélecteur de langue d'interface (i18n)
  • Onglets 1 et 2 (texte) via ui.panels
  • Onglet 3 (fichier) via FileTabMixin
  • Onglet 4 (définition) via DefTabMixin
  • Traduction de texte (thread) + gestion d'erreurs
  • Rafraîchissement i18n complet
  • Sélection contextuelle de mot (_get_selected_word)
  • Fermeture propre (fermeture des connexions SQLite)
"""

from __future__ import annotations

import os
import re
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import bootstrap
from config import C, F, LANG_NAMES, MAPPING, lang_code, detect_locale_lang
from dictionary import available_dics, close_all_conns
from i18n import I18N, detect_ui_lang
from translator import translate_text, TIMEOUT_TEXT
from ui.styles import build_style
from ui.panels import build_panel
from ui.file_tab import FileTabMixin
from ui.def_tab import DefTabMixin
from ui.about_window import AboutWindow


_ICON_SIZE = 36   # px — taille carrée affichée dans l'en-tête, à côté du titre
_ICON_PATH = os.path.join(bootstrap.BASE_DIR, "assets", "dico.png")


def _load_header_icon() -> "tk.PhotoImage | None":
    """
    Charge assets/dico.png en image carrée de _ICON_SIZE px, pour l'en-tête.

    Utilise Pillow si disponible (redimensionnement de qualité, et gère tout
    format/ratio source en le recadrant proprement en carré). À défaut, replie
    sur tk.PhotoImage natif avec un sous-échantillonnage entier (zoom/subsample) :
    moins précis si la taille source n'est pas un multiple exact, mais ne
    requiert aucune dépendance supplémentaire.

    Ne lève jamais d'exception : retourne None si le fichier est absent ou
    illisible (clé USB incomplète, dossier assets/ manquant…), pour que
    l'absence de l'icône ne casse jamais le lancement de l'application.
    """
    if not os.path.isfile(_ICON_PATH):
        return None

    try:
        from PIL import Image, ImageTk
        img = Image.open(_ICON_PATH).convert("RGBA")
        # Recadrage centré en carré avant redimensionnement, pour ne pas
        # déformer une icône source non carrée.
        w, h = img.size
        side = min(w, h)
        left, top = (w - side) // 2, (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((_ICON_SIZE, _ICON_SIZE), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except ImportError:
        pass
    except Exception:
        return None

    # ── Repli sans Pillow : tk.PhotoImage natif ────────────────────────────────
    try:
        raw = tk.PhotoImage(file=_ICON_PATH)
        w, h = raw.width(), raw.height()
        if w <= 0 or h <= 0:
            return None
        if w > _ICON_SIZE and h > _ICON_SIZE:
            factor = max(1, min(w, h) // _ICON_SIZE)
            raw = raw.subsample(factor, factor)
        elif w < _ICON_SIZE and h < _ICON_SIZE:
            factor = max(1, _ICON_SIZE // max(w, h))
            raw = raw.zoom(factor, factor)
        return raw
    except Exception:
        return None


class TranslatorApp(FileTabMixin, DefTabMixin, tk.Tk):

    def __init__(self) -> None:
        super().__init__()
        self._ui: str  = detect_ui_lang()
        self._t:  dict = I18N[self._ui]

        self.title(self._t["title"])
        self.geometry("1040x740")
        self.minsize(800, 580)
        self.configure(bg=C["bg"])
        self.resizable(True, True)

        self._tabs: dict = {}
        self._progress_timers: dict[str, str | None] = {}  # key -> after() id
        self._progress_starts: dict[str, float] = {}       # key -> time.monotonic()

        build_style(self)
        self._build_ui()
        self._refresh_i18n()
        self._apply_locale_defaults()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Fermeture ─────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        for key in list(self._progress_timers):
            self._stop_progress_timer(key)
        close_all_conns()
        self.destroy()

    # ── Chronomètre de progression (texte ET fichier) ─────────────────────────
    #
    # Une opération qui passe par le venv (chargement du modèle CTranslate2
    # à froid, fichier volumineux, etc.) peut prendre de quelques secondes à
    # plusieurs minutes. Sans retour visuel continu, l'interface paraît figée
    # pendant toute cette attente — et l'éventuel échec final (timeout après
    # 120s ou 600s) n'apparaît qu'après une très longue période de silence.
    #
    # _start_progress_timer() affiche un chronomètre dans lbl_status (mis à
    # jour chaque seconde) avec un message qui s'enrichit progressivement :
    #   0–9s    : "Traduction…"
    #   10–29s  : "Traduction… 12s"
    #   30s+    : "Toujours en cours… le premier chargement du modèle peut
    #              prendre du temps (34s)"
    # passé un certain seuil proche du timeout réel, un message d'attente
    # explicite supplémentaire est affiché pour rassurer l'utilisateur plutôt
    # que de le laisser face à un silence total jusqu'à l'échec.

    _ELAPSED_THRESHOLD = 10     # s — bascule "…" → "… Ns"
    _SLOW_THRESHOLD     = 30    # s — bascule vers le message "toujours en cours"

    def _start_progress_timer(
        self,
        key: str,
        base_key: str,
        elapsed_key: str,
        slow_key: str,
        timeout_soon_key: str,
        timeout_total: int,
        on_tick=None,
    ) -> None:
        """
        Démarre un chronomètre affiché dans self.lbl_status, identifié par
        *key* (ex. "text:0", "text:1", "file").

        base_key / elapsed_key / slow_key / timeout_soon_key sont les clés
        I18N à utiliser selon le temps écoulé. timeout_total est la durée
        réelle du timeout côté translator.py (utilisée pour calculer le
        seuil "ça devient anormalement long").

        on_tick, si fourni, est appelé à chaque tic avec le nombre de
        secondes écoulées (permet par ex. de mettre aussi à jour un libellé
        dédié à l'onglet Fichier en plus de lbl_status).
        """
        self._stop_progress_timer(key)   # sécurité : pas de double-chrono
        self._progress_starts[key] = time.monotonic()

        soon_threshold = max(timeout_total - 20, self._SLOW_THRESHOLD + 10)

        def tick() -> None:
            start = self._progress_starts.get(key)
            if start is None:
                return   # chronomètre arrêté entre-temps
            elapsed = int(time.monotonic() - start)
            t = self._t

            if elapsed >= soon_threshold:
                msg = t.get(timeout_soon_key, "{sec}s").format(sec=elapsed)
            elif elapsed >= self._SLOW_THRESHOLD:
                msg = t.get(slow_key, "{sec}s").format(sec=elapsed)
            elif elapsed >= self._ELAPSED_THRESHOLD:
                msg = t.get(elapsed_key, "{sec}s").format(sec=elapsed)
            else:
                msg = t.get(base_key, "…")

            self.lbl_status.configure(text=msg)
            if on_tick is not None:
                on_tick(elapsed, msg)

            self._progress_timers[key] = self.after(1000, tick)

        tick()

    def _stop_progress_timer(self, key: str) -> None:
        """Arrête et nettoie le chronomètre identifié par *key*, s'il existe."""
        after_id = self._progress_timers.pop(key, None)
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
        self._progress_starts.pop(key, None)

    # ── Squelette de l'interface ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        # En-tête
        hdr = ttk.Frame(self, style="P.TFrame")
        hdr.pack(fill="x")
        hi = ttk.Frame(hdr, style="P.TFrame")
        hi.pack(fill="x", padx=20, pady=10)

        tb = ttk.Frame(hi, style="P.TFrame")
        tb.pack(side="left")

        self._header_icon = _load_header_icon()   # référence conservée : sinon
        if self._header_icon is not None:          # le GC effacerait l'image
            icon_lbl = tk.Label(
                tb, image=self._header_icon,
                bg=C["panel"], bd=0, highlightthickness=0,
            )
            icon_lbl.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 10))

        title_col = ttk.Frame(tb, style="P.TFrame")
        title_col.grid(row=0, column=1, rowspan=2, sticky="w")
        self.lbl_title    = ttk.Label(title_col, text="", style="Ti.TLabel")
        self.lbl_title.pack(anchor="w")
        self.lbl_subtitle = ttk.Label(title_col, text="", style="Sub.TLabel")
        self.lbl_subtitle.pack(anchor="w")

        uif = ttk.Frame(hi, style="P.TFrame")
        uif.pack(side="right")
        self.lbl_ui = ttk.Label(uif, text="", style="PMu.TLabel")
        self.lbl_ui.pack(side="left", padx=(0, 6))
        ui_opts = [LANG_NAMES.get(c, c) for c in sorted(I18N)]
        self.cb_ui = ttk.Combobox(uif, values=ui_opts, state="readonly",
                                  width=19, font=F["small"])
        self.cb_ui.set(LANG_NAMES.get(self._ui, self._ui))
        self.cb_ui.pack(side="left")
        self.cb_ui.bind("<<ComboboxSelected>>", self._on_ui_lang)

        self.btn_about = ttk.Button(
            uif, text="ℹ", style="Ghost.TButton", width=3,
            command=self._open_about,
        )
        self.btn_about.pack(side="left", padx=(8, 0))

        ttk.Separator(self).pack(fill="x")

        # Barre de langues
        lb = ttk.Frame(self, style="P.TFrame")
        lb.pack(fill="x")
        li = ttk.Frame(lb, style="P.TFrame")
        li.pack(fill="x", padx=20, pady=14)
        li.columnconfigure(0, weight=1)
        li.columnconfigure(2, weight=1)

        sf = ttk.Frame(li, style="P.TFrame")
        sf.grid(row=0, column=0, sticky="ew")
        sf.columnconfigure(0, weight=1)
        self.lbl_src = ttk.Label(sf, text="", style="PH.TLabel")
        self.lbl_src.grid(row=0, column=0, sticky="w", pady=(0, 5))
        src_langs = sorted(MAPPING.keys(), key=lambda c: LANG_NAMES.get(c, c))
        self.cb_src = ttk.Combobox(
            sf, values=[LANG_NAMES.get(c, c) for c in src_langs],
            state="readonly", width=28, font=F["body"],
        )
        self.cb_src.grid(row=1, column=0, sticky="ew")
        self.cb_src.bind("<<ComboboxSelected>>", self._on_src_change)

        sbf = ttk.Frame(li, style="P.TFrame")
        sbf.grid(row=0, column=1, padx=14, sticky="s", pady=(0, 2))
        self.btn_swap = ttk.Button(sbf, text="", style="Swap.TButton",
                                   command=self._swap_langs)
        self.btn_swap.pack()

        tf = ttk.Frame(li, style="P.TFrame")
        tf.grid(row=0, column=2, sticky="ew")
        tf.columnconfigure(0, weight=1)
        self.lbl_tgt = ttk.Label(tf, text="", style="PH.TLabel")
        self.lbl_tgt.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.cb_tgt = ttk.Combobox(tf, values=[], state="readonly",
                                   width=28, font=F["body"])
        self.cb_tgt.grid(row=1, column=0, sticky="ew")

        ttk.Separator(self).pack(fill="x")

        # Notebook
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        for idx in range(2):
            tab = ttk.Frame(self.nb, style="TFrame")
            self.nb.add(tab, text="")
            self._tabs[idx] = build_panel(self, tab, idx)

        self._file_tab = ttk.Frame(self.nb, style="TFrame")
        self.nb.add(self._file_tab, text="")
        self.build_file_tab(self._file_tab)

        self._def_tab = ttk.Frame(self.nb, style="TFrame")
        self.nb.add(self._def_tab, text="")
        self.build_def_tab(self._def_tab)

        # Barre de statut
        sbar = ttk.Frame(self, style="P.TFrame")
        sbar.pack(fill="x", side="bottom")
        self.lbl_status = ttk.Label(sbar, text="", style="PMu.TLabel")
        self.lbl_status.pack(side="left", padx=16, pady=5)

    # ── Pré-sélection locale ──────────────────────────────────────────────────

    def _apply_locale_defaults(self) -> None:
        """
        Pré-sélectionne la langue source et le dictionnaire d'après la locale.
        """
        lc = detect_locale_lang()

        if lc in MAPPING:
            display = LANG_NAMES.get(lc, lc)
            if display in self.cb_src["values"]:
                self.cb_src.set(display)
                self._on_src_change()

        dics = available_dics()
        if lc in dics:
            opts = self._dic_opts(dics)
            target = next(
                (o for o in opts if re.search(
                    rf'\[{re.escape(lc)}-{re.escape(lc)}\.db\]', o
                )),
                None,
            )
            if target:
                self._def_cb_lang.configure(values=opts)
                self._def_cb_lang.set(target)

    # ── Combobox langues ──────────────────────────────────────────────────────

    def _on_src_change(self, _=None) -> None:
        code    = lang_code(self.cb_src.get())
        targets = sorted([LANG_NAMES.get(c, c) for c in MAPPING.get(code, [])])
        self.cb_tgt.configure(values=targets)
        self.cb_tgt.set(targets[0] if targets else "")

    def _swap_langs(self) -> None:
        """Inverse source ↔ cible ET permute les textes dans les deux panneaux."""
        s, tg = self.cb_src.get(), self.cb_tgt.get()
        if not s or not tg:
            return
        ns, nt = lang_code(tg), lang_code(s)
        if ns not in MAPPING:
            messagebox.showwarning(
                self._t["error_title"],
                f"'{tg}' ne peut pas être langue source.",
            )
            return
        if nt not in MAPPING.get(ns, []):
            messagebox.showwarning(
                self._t["error_title"],
                f"Aucune paire {ns} → {nt} disponible.",
            )
            return

        saved = [
            (self._tabs[i]["src"].get("1.0", "end-1c"),
             self._tabs[i]["tgt"].get("1.0", "end-1c"))
            for i in range(2)
        ]

        self.cb_src.set(LANG_NAMES.get(ns, ns))
        self._on_src_change()
        self.cb_tgt.set(LANG_NAMES.get(nt, nt))

        for i in range(2):
            old_src, old_tgt = saved[i]
            w = self._tabs[i]
            w["src"].delete("1.0", "end")
            if old_tgt.strip():
                w["src"].insert("1.0", old_tgt)
            w["tgt"].configure(state="normal")
            w["tgt"].delete("1.0", "end")
            if old_src.strip():
                w["tgt"].insert("1.0", old_src)
            w["tgt"].configure(state="disabled")
            self._upd_chars(i)

    # ── Traduction de texte ───────────────────────────────────────────────────

    def _translate(self, idx: int) -> None:
        src_c = lang_code(self.cb_src.get())
        tgt_c = lang_code(self.cb_tgt.get())
        if not src_c or not tgt_c:
            messagebox.showwarning(self._t["error_title"], self._t["select_langs"])
            return
        text = self._tabs[idx]["src"].get("1.0", "end-1c").strip()
        if not text:
            messagebox.showinfo(self._t["error_title"], self._t["no_text"])
            return

        btn = self._tabs[idx]["tr_btn"]
        btn.configure(text=self._t["translating"], state="disabled")

        timer_key = f"text:{idx}"
        self._start_progress_timer(
            timer_key,
            base_key="translating",
            elapsed_key="translating_elapsed",
            slow_key="translating_slow",
            timeout_soon_key="translating_timeout_soon",
            timeout_total=TIMEOUT_TEXT,
        )

        def run() -> None:
            try:
                result = translate_text(src_c, tgt_c, text)
                self.after(0, lambda: self._set_result(idx, result))
            except RuntimeError as exc:
                self.after(0, lambda m=str(exc): self._on_trans_err(idx, m))

        threading.Thread(target=run, daemon=True).start()

    def _set_result(self, idx: int, text: str) -> None:
        self._stop_progress_timer(f"text:{idx}")
        w = self._tabs[idx]
        w["tgt"].configure(state="normal")
        w["tgt"].delete("1.0", "end")
        w["tgt"].insert("1.0", text)
        w["tgt"].configure(state="disabled")
        w["tr_btn"].configure(text=self._t["translate_btn"], state="normal")
        self.lbl_status.configure(text="")

    def _on_trans_err(self, idx: int, err: str) -> None:
        self._stop_progress_timer(f"text:{idx}")
        self._tabs[idx]["tr_btn"].configure(
            text=self._t["translate_btn"], state="normal",
        )
        self.lbl_status.configure(text="")
        t = self._t
        if err == "NO_VENV_PYTHON":
            messagebox.showerror(t["error_title"], self._venv_missing_msg())
        elif err.startswith("SYS_PATH_ONLY:"):
            detail = err.split(":", 1)[1]
            messagebox.showerror(t["error_title"], self._sys_path_only_msg(detail))
        elif err in ("IMPORT_ERROR", "NO_LANGUAGES"):
            messagebox.showerror(t["error_title"], self._venv_import_msg(t))
        elif err.startswith("NO_PKG:"):
            _, sc, tc = err.split(":")
            messagebox.showerror(t["error_title"],
                                 t["error_no_pkg"].format(
                                     src=LANG_NAMES.get(sc, sc),
                                     tgt=LANG_NAMES.get(tc, tc),
                                 ))
        elif err.startswith("NO_LANG:"):
            _, lc_ = err.split(":", 1)
            messagebox.showerror(t["error_title"],
                                 t["error_no_pkg"].format(
                                     src=LANG_NAMES.get(lc_, lc_), tgt="?",
                                 ))
        elif err.startswith("SUBPROCESS:"):
            detail = err.split(":", 1)[1]
            messagebox.showerror(t["error_title"],
                                 t["error_trans"].format(err=detail))
        else:
            messagebox.showerror(t["error_title"],
                                 t["error_trans"].format(err=err))

    @staticmethod
    def _venv_missing_msg() -> str:
        return (
            "Python venv not found at build/python/venv\n\n"
            "Le venv Python figé (build/python/venv) est introuvable à côté "
            "de l'exécutable. Vérifiez que le dossier 'build' a bien été "
            "copié sur la clé USB, au même niveau que l'application."
        )

    @staticmethod
    def _venv_import_msg(t: dict) -> str:
        """
        Message enrichi pour IMPORT_ERROR / NO_LANGUAGES : indique le chemin
        exact de l'interpréteur utilisé et signale s'il s'agit probablement
        du Python système plutôt que de celui du venv (cause la plus
        fréquente : un outil de copie a déréférencé le symlink bin/python
        et copié le binaire système à sa place).
        """
        diag = bootstrap.diagnose_venv_python()
        base = t.get("error_pkg", "argostranslate is not installed.")
        if not diag["found"]:
            return base + "\n\n" + diag["note"]
        path_line = f"\n\nInterpréteur utilisé : {diag['path']}"
        if not diag["genuine"]:
            return base + path_line + "\n\n" + diag["note"]
        return base + path_line

    @staticmethod
    def _sys_path_only_msg(detail: str) -> str:
        """
        Message pour SYS_PATH_ONLY : le diagnostic en sous-processus a
        prouvé que le venv lui-même fonctionne (argostranslate y est
        bien installé et y trouve ses langues), donc le problème est
        spécifique à l'injection sys.path dans CE process — par exemple
        un module nommé "argostranslate" trouvé ailleurs dans sys.path
        avant celui du venv, ou un conflit de version d'une dépendance
        déjà importée. Distinct du cas générique "pas installé", car
        l'action corrective est différente (vérifier l'ordre de
        sys.path / l'absence de module homonyme, pas réinstaller).
        """
        return (
            "Le venv (build/python/venv) fonctionne correctement — "
            "argostranslate y est bien installé — mais son chargement a "
            "échoué dans le processus de l'application elle-même.\n\n"
            f"Détail technique : {detail}\n\n"
            "Cause probable : un module portant le même nom est chargé "
            "depuis un autre emplacement avant celui du venv, ou un "
            "conflit de version d'une dépendance déjà importée dans ce "
            "process. Essayez de redémarrer l'application ; si le "
            "problème persiste, signalez ce message."
        )

    # ── Opérations texte ─────────────────────────────────────────────────────

    def _clear(self, idx: int) -> None:
        w = self._tabs[idx]
        w["src"].delete("1.0", "end")
        w["tgt"].configure(state="normal")
        w["tgt"].delete("1.0", "end")
        w["tgt"].configure(state="disabled")
        self._upd_chars(idx)

    def _copy(self, idx: int) -> None:
        text = self._tabs[idx]["tgt"].get("1.0", "end-1c").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.lbl_status.configure(text=self._t["copied"])
            self.after(3000, lambda: self.lbl_status.configure(text=""))

    def _upd_chars(self, idx: int) -> None:
        n = len(self._tabs[idx]["src"].get("1.0", "end-1c"))
        self._tabs[idx]["char"].configure(
            text=self._t["char_count"].format(n=n),
        )

    def _get_selected_word(self, idx: int, side: str) -> str | None:
        widget = self._tabs[idx][side]
        try:
            sel = widget.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
            if sel:
                return sel.split()[0] if " " in sel else sel
        except tk.TclError:
            pass
        return None

    # ── Internationalisation ──────────────────────────────────────────────────

    def _on_ui_lang(self, _=None) -> None:
        code = lang_code(self.cb_ui.get())
        if code in I18N:
            self._ui = code
            self._t  = I18N[code]
            self._refresh_i18n()

    def _open_about(self) -> None:
        """Ouvre la fenêtre modale 'À propos' (bouton ℹ de l'en-tête)."""
        AboutWindow(self, self._t)

    def _refresh_i18n(self) -> None:
        t = self._t
        self.title(t["title"])
        self.lbl_title.configure(text=t["title"])
        self.lbl_subtitle.configure(text=t.get("subtitle", ""))
        self.lbl_src.configure(text=t["source_lang"])
        self.lbl_tgt.configure(text=t["target_lang"])
        self.btn_swap.configure(text=t["swap_btn"])
        self.lbl_ui.configure(text=t["ui_lang"] + " :")
        self.nb.tab(0, text=t["tab1"])
        self.nb.tab(1, text=t["tab2"])
        self.nb.tab(2, text=t.get("tab3", "File"))
        self.nb.tab(3, text=t.get("tab4", "Definition"))

        define_label = t.get("define_btn", "📖 Define")
        for i in range(2):
            w = self._tabs[i]
            w["lbl_s"].configure(text=t["source_text"])
            w["lbl_t"].configure(text=t["target_text"])
            w["tr_btn"].configure(text=t["translate_btn"])
            w["cl_btn"].configure(text=t["clear_btn"])
            w["cp_btn"].configure(text=t["copy_btn"])
            w["def_src_btn"].configure(text=define_label)
            w["def_tgt_btn"].configure(text=define_label)
            w["src_menu"].entryconfigure(0, label=define_label)
            w["tgt_menu"].entryconfigure(0, label=define_label)
            self._upd_chars(i)

        # Onglet Fichier
        self._file_lbl_title.configure(text=t.get("file_tab_title", "File Translation"))
        self._file_lbl_fmt.configure(text=t.get("file_formats", ""))
        self._file_pick_btn.configure(text=t.get("file_pick_btn", "📂  Choose file…"))
        self._file_tr_btn.configure(text=t.get("file_translate_btn", "Translate file →"))
        self._file_open_btn.configure(text=t.get("file_open_btn", "📁  Open folder"))
        self._file_out_head.configure(text=t.get("file_out_label", "Output file") + " :")
        if not self._file_path.get():
            self._file_path.set(t.get("file_none", "No file selected"))

        # Onglet Définition
        self._def_lbl_title.configure(text=t.get("def_tab_title", "Dictionary Search"))
        self._def_lbl_lang.configure(text=t.get("def_lang_label", "Dictionary") + " :")
        self._def_search_btn.configure(text=t.get("def_search_btn", "Containing"))
        self._def_prefix_btn.configure(text=t.get("def_btn_prefix", "Starting with"))
        self._def_exact_btn.configure(text=t.get("def_btn_exact", "Definition"))
        self._def_refresh_btn.configure(text=t.get("def_refresh", "↺"))
        self._def_show_hint()
