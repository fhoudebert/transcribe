"""
main_window.py  —  Fenêtre principale Transcribe.
"""

import json
import os
import re
import sys
import threading
import subprocess
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from app_config import (
    IS_WINDOWS, NO_WINDOW,
    MODELS, TARGET_LANGUAGES, SOURCE_LANGUAGES, LANG_NAMES, ISO_639_2,
    AUTO_LANG, NO_TRANSLATION,
    lang_label, lang_code,
    load_settings, save_settings,
)

# Ligne stderr de whisper-cli en mode -l auto :
#   "whisper_full_with_state: auto-detected language: it (p = 0.98…)"
_DETECT_RE = re.compile(r"auto-detected language:\s*([a-z]{2,3})")
from app_styles import (
    BG, BG2, BG3, BG4, ACCENT, GREEN, WARN, DANGER, TEAL,
    FG, FG2, BORDER,
    FONT_MONO, FONT_UI, FONT_H1, FONT_H2, FONT_SMALL, FONT_INFO,
    mkbtn, section, hdivider, checkbox, apply_ttk_style, _adj,
)
from recorder_window import RecorderWindow
from dialog_windows  import ChoiceDialog, DownloadWindow
from about_window    import AboutWindow
from i18n import t, available_locales, set_locale, get_locale


class Transcribe(tk.Tk):

    def __init__(self, **kwargs):
        super().__init__(className=kwargs.pop("className", "Transcribe"))
        self.title("Transcribe")
        self.geometry("860x820")
        self.minsize(760, 700)
        self.configure(bg=BG)
        self.resizable(True, True)

        self.video_path    = tk.StringVar()
        self.model_key     = tk.StringVar(value="medium")  # code du modèle
        self.src_lang      = tk.StringVar(value=AUTO_LANG)  # langue de l'audio (-l whisper)
        self.to_lang       = tk.StringVar(value="fr")       # langue de traduction (argos)
        self._detected_lang: str | None = None              # renseignée par whisper -l auto
        self.pre_loudnorm  = tk.BooleanVar(value=True)
        self.pre_denoise   = tk.BooleanVar(value=False)
        self.pre_voiceband = tk.BooleanVar(value=False)
        self.pre_volume_db = tk.DoubleVar(value=0.0)
        self.opt_dual_sub  = tk.BooleanVar(value=True)

        self.root_dir = os.environ.get(
            "TRANSCRIBE_BASE_DIR",
            os.path.dirname(os.path.abspath(__file__)))

        # Préférences persistées (settings.json à la racine)
        _s = load_settings(self.root_dir)
        if _s.get("src_lang") in SOURCE_LANGUAGES:
            self.src_lang.set(_s["src_lang"])
        if _s.get("target_lang") in [NO_TRANSLATION] + TARGET_LANGUAGES:
            self.to_lang.set(_s["target_lang"])

        self._btn_translate = None
        self._btn_include   = None
        self._buttons_all: list[tk.Button] = []
        self._body_frame    = None      # frame reconstruite au changement de langue

        # ── Icône fenêtre ─────────────────────────────────────
        # Chargée ici (sur la Tk root) pour s'appliquer à toutes les
        # fenêtres enfants (Toplevel héritent de iconphoto(True, ...)).
        # Cherche dans assets/ : .png (dev + Linux) puis .ico (Windows).
        # Compatible PyInstaller --add-data "assets:assets"
        self._wm_icon = None   # référence pour éviter le GC
        self._load_window_icon()

        self._build_ui()
        apply_ttk_style(self)

        self.video_path.trace_add(
            "write",
            lambda *_: self._update_mkv_btn(self.video_path.get()))

    # ── Chemins ─────────────────────────────────────────────
    def _load_window_icon(self) -> None:
        """
        Charge l'icône de fenêtre depuis assets/.
        Ordre de recherche :
          1. assets/icone.png  (nom utilisé dans la commande PyInstaller)
          2. assets/icon.png   (nom alternatif courant)
          3. assets/icon.ico   (Windows natif, meilleure intégration taskbar)

        iconphoto(True, img) applique l'icône à cette fenêtre ET à tous
        les Toplevel créés ensuite (RecorderWindow, DownloadWindow…).

        Sur Windows, wm_iconbitmap() avec un .ico donne une icône haute
        résolution dans la barre des tâches — on fait les deux si possible.
        """
        assets_dir = os.path.join(self.root_dir, "assets")

        # Candidats PNG/ICO par ordre de préférence
        candidates_png = [
            os.path.join(assets_dir, "icone.png"),
            os.path.join(assets_dir, "icon.png"),
        ]
        candidates_ico = [
            os.path.join(assets_dir, "icone.ico"),
            os.path.join(assets_dir, "icon.ico"),
        ]

        # ── 1. Icône PNG via tk.PhotoImage (toutes plateformes) ──
        for png_path in candidates_png:
            if not os.path.isfile(png_path):
                continue
            try:
                from PIL import Image, ImageTk
                # Pillow : resize propre en 64×64 pour iconphoto
                img = Image.open(png_path).resize((64, 64), Image.LANCZOS)
                self._wm_icon = ImageTk.PhotoImage(img)
            except ImportError:
                # Pillow absent : tk.PhotoImage natif (PNG sans resize)
                try:
                    self._wm_icon = tk.PhotoImage(file=png_path)
                except Exception:
                    continue
            except Exception:
                continue

            if self._wm_icon:
                try:
                    self.iconphoto(True, self._wm_icon)
                except Exception:
                    pass
                break   # PNG chargé avec succès

        # ── 2. ICO Windows (barre des tâches haute résolution) ──
        if IS_WINDOWS:
            for ico_path in candidates_ico:
                if os.path.isfile(ico_path):
                    try:
                        self.wm_iconbitmap(default=ico_path)
                    except Exception:
                        pass
                    break


    def _ffmpeg(self) -> str:
        ext = ".exe" if IS_WINDOWS else ""
        return os.path.join(self.root_dir, "build", "ffmpeg", "bin", f"ffmpeg{ext}")

    def _ffprobe(self) -> str:
        ext = ".exe" if IS_WINDOWS else ""
        return os.path.join(self.root_dir, "build", "ffmpeg", "bin", f"ffprobe{ext}")

    @staticmethod
    def _python_exe() -> str:
        """
        Retourne l'interpréteur Python du venv portable.

        L'application est portable : le venv est toujours présent sous
          build/python/venv/  (relatif à root_dir / sys.executable.parent)

        Ordre de recherche :
          1. build/python/venv/bin/python3   (Linux/Mac — priorité absolue)
          2. build/python/venv/bin/python    (alias Linux)
          3. build/python/venv/Scripts/python.exe  (Windows venv)
          4. sys.executable                  (dev sans frozen : venv courant)
          5. python3 système                 (ultime fallback)

        En mode développement (non-frozen), sys.executable est déjà le
        python du venv actif — on le retourne directement.
        """
        # Racine = dossier du binaire (frozen) ou du script (dev)
        if getattr(sys, "frozen", False):
            root = os.path.dirname(sys.executable)
        else:
            root = os.environ.get(
                "TRANSCRIBE_BASE_DIR",
                os.path.dirname(os.path.abspath(__file__)))

        # Candidats dans le venv portable, par ordre de préférence
        candidates = (
            os.path.join(root, "build", "python", "venv", "bin",
                         "python3"),
            os.path.join(root, "build", "python", "venv", "bin",
                         "python"),
            os.path.join(root, "build", "python", "venv", "Scripts",
                         "python.exe"),   # Windows
        )
        for p in candidates:
            if os.path.isfile(p):
                return p

        # Fallback dev : sys.executable (venv activé en développement)
        if not getattr(sys, "frozen", False):
            return sys.executable

        # Dernier recours : python3 système (non recommandé en portabilité)
        import shutil
        return shutil.which("python3") or shutil.which("python") or "python3"

    def _script(self, name: str) -> list[str]:
        if name == "traduire-srt":
            # Utilise _python_exe() et non sys.executable :
            # en mode frozen, sys.executable est le binaire PyInstaller.
            return [self._python_exe(),
                    os.path.join(self.root_dir, "traduire-srt.py")]
        if IS_WINDOWS:
            bat = os.path.normpath(
                os.path.join(self.root_dir, f"{name}.bat"))
            return ["cmd", "/c", bat]
        return ["bash", os.path.join(self.root_dir, f"{name}.sh")]

    def _model(self) -> str:
        """Retourne le nom du modèle sélectionné (ex: 'medium', 'large-v3')."""
        return self.model_key.get() or "medium"


    def _update_model_hint(self):
        """
        Met à jour le label de l’indicateur selon le modèle sélectionné.
        Regarde le DÉBUT du nom : tiny / small / medium / large.
        """
        name = self.model_key.get().lower()
        if name.startswith("tiny"):
            hint = t("model_tiny")
        elif name.startswith("small"):
            hint = t("model_small")
        elif name.startswith("medium"):
            hint = t("model_medium")
        elif name.startswith("large"):
            hint = t("model_large")
        else:
            hint = t("model_hint_unknown")
        if hasattr(self, "_model_hint_var"):
            self._model_hint_var.set(f"  ↳  {hint}" if hint else "")

    def _scan_models(self) -> list[str]:
        """
        Scanne build/whisper/models/*.bin et retourne les noms de modèles
        (sans 'ggml-' et sans '.bin').
        Ex: ['base', 'medium', 'large-v3']
        Fallback sur les modèles statiques de app_config si le dossier est vide.
        """
        import glob
        models_dir = os.path.join(self.root_dir, "build", "whisper", "models")
        bins = sorted(glob.glob(os.path.join(models_dir, "ggml-*.bin")))
        if bins:
            names = []
            for p in bins:
                name = os.path.basename(p)          # ggml-medium.bin
                name = name[len("ggml-"):]           # medium.bin
                name = name[:-len(".bin")]            # medium
                names.append(name)
            return names
        # Fallback : modèles statiques de app_config
        return list(MODELS.values())

    def _ffmpeg(self) -> str:
        ext = ".exe" if IS_WINDOWS else ""
        return os.path.join(self.root_dir, "build", "ffmpeg", "bin", f"ffmpeg{ext}")

    def _whisper_bin(self) -> str:
        ext = ".exe" if IS_WINDOWS else ""
        return os.path.join(self.root_dir, "build", "whisper", f"whisper-cli{ext}")

    def _whisper_model(self) -> str:
        return os.path.join(self.root_dir, "build", "whisper", "models",
                            f"ggml-{self._model()}.bin")

    # ── Sélecteur de langue UI ───────────────────────────────



    def _switch_ui_lang(self, code: str):
        """
        Sauvegarde la langue choisie dans settings.json.
        Affiche un message demandant le redémarrage.
        (Pas de rechargement à chaud — redémarrage suffisant.)
        """
        if code == get_locale():
            return
        set_locale(code)
        messagebox.showinfo(
            "🌐  " + code.upper(),
            t("settings_restart"),
            parent=self)
        # Ne reconstruit PAS le header ici → évite le doublon de boutons.
        # Le changement prend effet au prochain démarrage.

    # ── Construction UI ──────────────────────────────────────

    def _build_ui(self):
        # Bandeau (fixe, reconstruit uniquement les boutons de langue)
        self._hdr = tk.Frame(self, bg=BG2)
        self._hdr.pack(fill="x")
        self._build_header()
        # Corps (reconstruit au changement de locale)
        self._build_body()

    def _build_header(self):
        for w in self._hdr.winfo_children():
            w.destroy()
        inner = tk.Frame(self._hdr, bg=BG2)
        inner.pack(side="left", padx=18, pady=10)

        # ── Icône application (optionnelle) ──────────────────
        # Placez icon.png (512×512 recommandé) dans le répertoire racine.
        # Stratégie de chargement :
        #   1. Pillow (resize précis LANCZOS) si disponible
        #   2. tk.PhotoImage natif (PNG supporté sans dépendance,
        #      mais pas de resize → on zoome/subsample si nécessaire)
        #   3. Placeholder canvas si icon.png absent
        # ── Icône dans le bandeau ────────────────────────────
        # On réutilise l'icône déjà chargée dans _load_window_icon
        # mais redimensionnée à 40×40 pour le bandeau.
        # Si indisponible, affiche un placeholder canvas.
        icon_size = 40
        banner_icon = None
        assets_dir  = os.path.join(self.root_dir, "assets")

        for png_name in ("icone.png", "icon.png"):
            png_path = os.path.join(assets_dir, png_name)
            if not os.path.isfile(png_path):
                continue
            try:
                from PIL import Image, ImageTk
                img = Image.open(png_path).resize(
                    (icon_size, icon_size), Image.LANCZOS)
                banner_icon = ImageTk.PhotoImage(img)
                # Stockage sur self pour éviter le GC
                self._banner_icon = banner_icon
            except ImportError:
                try:
                    raw = tk.PhotoImage(file=png_path)
                    w, h = raw.width(), raw.height()
                    factor = max(1, round(min(w, h) / icon_size))
                    if factor > 1:
                        raw = raw.subsample(factor, factor)
                    banner_icon = raw
                    self._banner_icon = banner_icon
                except Exception:
                    pass
            except Exception:
                pass
            if banner_icon:
                break

        if banner_icon:
            tk.Label(inner, image=banner_icon,
                     bg=BG2, bd=0).pack(side="left", padx=(0, 10))
        else:
            # Placeholder : cercle ACCENT + lettre T
            canvas = tk.Canvas(inner, width=icon_size, height=icon_size,
                                bg=BG2, highlightthickness=0)
            canvas.pack(side="left", padx=(0, 10))
            canvas.create_oval(2, 2, icon_size-2, icon_size-2,
                                fill=ACCENT, outline="")
            canvas.create_text(icon_size//2, icon_size//2, text="T",
                                font=("Segoe UI" if IS_WINDOWS
                                      else "Helvetica Neue",
                                      icon_size // 2, "bold"),
                                fill=BG2)

        # ── Titre + sous-titre ────────────────────────────────
        txt_col = tk.Frame(inner, bg=BG2)
        txt_col.pack(side="left")
        tk.Label(txt_col, text=t("app_title"),
                 font=FONT_H1, bg=BG2, fg=FG,
                 anchor="w").pack(anchor="w")
        tk.Label(txt_col, text=t("app_subtitle"),
                 font=FONT_SMALL, bg=BG2, fg=FG2,
                 anchor="w").pack(anchor="w")

        # ── Sélecteur de langue + bouton ℹ (intégré dans le header) ──
        locales = available_locales()
        active  = get_locale()
        rframe  = tk.Frame(self._hdr, bg=BG2)
        rframe.pack(side="right", padx=14)

        tk.Label(rframe, text=t("settings_ui_lang"),
                 bg=BG2, fg=FG2,
                 font=FONT_SMALL).pack(side="left", padx=(0, 4))

        for code, name in locales:
            is_active = (code == active)
            col = ACCENT if is_active else BG4
            fg  = FG     if is_active else FG2
            tk.Button(
                rframe, text=code.upper(),
                bg=col, fg=fg,
                activebackground=_adj(ACCENT, 20), activeforeground=FG,
                relief="flat", bd=0, cursor="hand2",
                font=("Segoe UI" if IS_WINDOWS else "Helvetica Neue",
                      9, "bold"),
                padx=8, pady=4,
                command=lambda c=code: self._switch_ui_lang(c),
            ).pack(side="left", padx=2)

        tk.Frame(rframe, width=1, bg=BORDER).pack(
            side="left", fill="y", padx=(8, 4))
        tk.Button(
            rframe, text=t("about_btn"),
            bg=BG2, fg=FG2,
            activebackground=BG3, activeforeground=FG,
            relief="flat", bd=0, cursor="hand2",
            font=("Segoe UI" if IS_WINDOWS else "Helvetica Neue",
                  11, "bold"),
            padx=4, pady=2,
            command=lambda: AboutWindow(self),
        ).pack(side="left")

    def _build_body(self):
        # Barre de statut (en bas, fixe)
        if hasattr(self, "_sbar"):
            self._sbar.destroy()
        self._sbar = tk.Frame(self, bg=BG2)
        self._sbar.pack(fill="x", side="bottom")
        tk.Frame(self._sbar, height=1, bg=BORDER).pack(fill="x")
        si = tk.Frame(self._sbar, bg=BG2)
        si.pack(fill="x", padx=14, pady=5)
        self._status = tk.StringVar(value=t("status_ready"))
        tk.Label(si, textvariable=self._status,
                 bg=BG2, fg=FG2, font=FONT_SMALL).pack(side="left")
        self._progress = ttk.Progressbar(si, mode="indeterminate", length=160)
        self._progress.pack(side="right")
        plat = "Windows" if IS_WINDOWS else "Linux"
        tk.Label(si, text=f"  {plat} · Python {sys.version[:6]}",
                 bg=BG2, fg=BG4, font=FONT_SMALL).pack(side="right")

        # Corps scrollable
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)
        self._body_frame = outer

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb    = tk.Scrollbar(outer, orient="vertical",
                              command=canvas.yview, bg=BG2)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(canvas, bg=BG)
        win  = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(
                            -1*(e.delta//120), "units"))

        pad = {"padx": 26}

        # ① Fichier
        section(body, t("sec_file"))
        frow = tk.Frame(body, bg=BG)
        frow.pack(fill="x", **pad)
        self._entry = tk.Entry(
            frow, textvariable=self.video_path,
            bg=BG3, fg=FG, insertbackground=FG, relief="flat", bd=0,
            font=FONT_UI, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT)
        self._entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0,8))
        for text_key, cmd, color, fg in [
            ("btn_browse",  self._browse,         BG4,       FG),
            ("btn_url",     self._open_downloader,"#1a4a1a",  FG),
            ("btn_analyze", self._run_analyze,    TEAL,       BG),
            ("btn_record",  self._open_recorder,  "#7c3f00",  FG),
        ]:
            b = mkbtn(frow, t(text_key), cmd, color=color, fg=fg)
            b.pack(side="left", padx=(0, 6))
            self._buttons_all.append(b)

        self._info_frame = tk.Frame(body, bg=BG3,
                                    highlightthickness=1,
                                    highlightbackground=BORDER)
        self._info_text  = tk.Text(
            self._info_frame, bg=BG3, fg=TEAL,
            font=FONT_INFO, relief="flat", bd=0,
            state="disabled", height=5, wrap="none")
        self._info_text.pack(fill="both", padx=8, pady=6)

        hdivider(body)

        # ② Modèle
        section(body, t("sec_model"))
        mrow = tk.Frame(body, bg=BG)
        mrow.pack(fill="x", **pad)
        model_names = self._scan_models()
        # Sélection par défaut : medium si disponible, sinon premier
        if self.model_key.get() not in model_names and model_names:
            self.model_key.set(model_names[0])
        if "medium" in model_names:
            self.model_key.set("medium")
        self._model_cb = ttk.Combobox(
            mrow, textvariable=self.model_key,
            values=model_names,
            width=22, state="readonly", font=FONT_UI)
        self._model_cb.pack(side="left")

        # Hint dynamique selon le modèle sélectionné
        self._model_hint_var = tk.StringVar()
        tk.Label(mrow, textvariable=self._model_hint_var,
                 bg=BG, fg=WARN, font=FONT_SMALL,
                 anchor="w", wraplength=380).pack(
            side="left", padx=(12, 0), fill="x", expand=True)
        self.model_key.trace_add("write",
            lambda *_: self._update_model_hint())
        self._update_model_hint()   # affichage initial

        hdivider(body)

        # ③ Pré-traitement
        section(body, t("sec_preproc"), color=WARN)
        prow = tk.Frame(body, bg=BG)
        prow.pack(fill="x", **pad)
        checkbox(prow, t("pre_loudnorm"),  self.pre_loudnorm ).pack(side="left", padx=(0,20))
        checkbox(prow, t("pre_denoise"),   self.pre_denoise  ).pack(side="left", padx=(0,20))
        checkbox(prow, t("pre_voice"),     self.pre_voiceband).pack(side="left")

        vrow = tk.Frame(body, bg=BG)
        vrow.pack(fill="x", pady=(6,0), **pad)
        tk.Label(vrow, text=t("pre_volume"), bg=BG, fg=FG2,
                 font=FONT_UI).pack(side="left")
        tk.Scale(vrow, variable=self.pre_volume_db,
                 from_=-12, to=12, resolution=0.5, orient="horizontal",
                 bg=BG, fg=FG, troughcolor=BG3, activebackground=ACCENT,
                 highlightthickness=0, bd=0, sliderrelief="flat",
                 length=200, font=FONT_SMALL,
                 ).pack(side="left", padx=(8, 6))
        self._vol_label = tk.Label(vrow, text="0.0 dB",
                                   bg=BG, fg=WARN, font=FONT_UI, width=8)
        self._vol_label.pack(side="left")
        self.pre_volume_db.trace_add(
            "write",
            lambda *_: self._vol_label.config(
                text=f"{self.pre_volume_db.get():+.1f} dB"))

        # Bouton : appliquer les filtres et enregistrer sous <nom>-vol.<ext>
        mkbtn(vrow, t("pre_export_btn"),
              self._run_export_audio,
              color="#2a3a5a", fg=FG).pack(side="left", padx=(14, 0))

        self._filter_info = tk.Label(body, text="", bg=BG, fg=FG2,
                                     font=FONT_SMALL, anchor="w")
        self._filter_info.pack(fill="x", padx=26, pady=(2,0))
        for v in (self.pre_loudnorm, self.pre_denoise,
                  self.pre_voiceband, self.pre_volume_db):
            v.trace_add("write", lambda *_: self._refresh_filter_info())
        self._refresh_filter_info()

        hdivider(body)

        # ④ Langue — source audio et cible de traduction sur une ligne
        section(body, t("sec_lang"))
        lrow = tk.Frame(body, bg=BG)
        lrow.pack(fill="x", pady=(0,2), **pad)

        # — Langue de la source audio (guide le -l de whisper)
        tk.Label(lrow, text=t("lbl_audio_lang"), bg=BG, fg=FG2,
                 font=FONT_UI).pack(side="left")
        self._src_cb = ttk.Combobox(
            lrow, textvariable=self.src_lang,
            values=[self._lang_display(c) for c in SOURCE_LANGUAGES],
            width=18, state="readonly")
        self._src_cb.pack(side="left", padx=(8,18))
        self._src_cb.bind("<<ComboboxSelected>>", self._on_src_lang_select)
        self.src_lang.set(self._lang_display(
            self._lang_from_display(self.src_lang.get())))

        # — Langue de traduction cible (étape argos)
        tk.Label(lrow, text=t("lbl_translate_to"), bg=BG, fg=FG2,
                 font=FONT_UI).pack(side="left")
        self._lang_cb = ttk.Combobox(
            lrow, textvariable=self.to_lang,
            values=[self._lang_display(c)
                    for c in [NO_TRANSLATION] + TARGET_LANGUAGES],
            width=18, state="readonly")
        self._lang_cb.pack(side="left", padx=(8,0))
        self._lang_cb.bind("<<ComboboxSelected>>", self._on_lang_select)
        self.to_lang.set(self._lang_display(
            self._lang_from_display(self.to_lang.get())))

        hdivider(body)

        # ⑤ Options MKV
        section(body, t("sec_mkv"), color=GREEN)
        orow = tk.Frame(body, bg=BG)
        orow.pack(fill="x", **pad)
        checkbox(orow, t("opt_dual_sub"), self.opt_dual_sub).pack(side="left")

        hdivider(body)

        # ⑥ Traitements
        section(body, t("sec_actions"))
        brow = tk.Frame(body, bg=BG)
        brow.pack(fill="x", pady=6, **pad)

        b_audio = mkbtn(brow, t("btn_audio"), self._run_audio,
                        color="#1f3a6e", fg=FG)
        b_audio.pack(side="left", padx=(0,8))
        self._buttons_all.append(b_audio)

        b_whisper = mkbtn(brow, t("btn_whisper"), self._run_whisper,
                          color=ACCENT)
        b_whisper.pack(side="left", padx=(0,8))
        self._buttons_all.append(b_whisper)

        self._btn_translate = mkbtn(brow, t("btn_translate"),
                                    self._run_translate,
                                    color="#1a5c38", fg=FG)
        # masqué au démarrage

        self._btn_include = mkbtn(brow, t("btn_mkv"), self._run_include,
                                  color="#4a2060", fg=FG)
        self._btn_include.pack(side="left")
        self._buttons_all.append(self._btn_translate)
        self._buttons_all.append(self._btn_include)

        hdivider(body)

        # ⑦ Journal
        section(body, t("sec_log"))
        log_wrap = tk.Frame(body, bg=BG3, highlightthickness=1,
                            highlightbackground=BORDER)
        log_wrap.pack(fill="both", expand=True, **pad, pady=(0,10))
        self._log = tk.Text(
            log_wrap, bg=BG3, fg=FG2, font=FONT_MONO,
            relief="flat", bd=0, state="disabled",
            wrap="word", height=12,
            selectbackground=ACCENT, selectforeground=FG)
        lsb = tk.Scrollbar(log_wrap, command=self._log.yview,
                           bg=BG3, troughcolor=BG3, width=10)
        self._log.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        self._log.pack(fill="both", expand=True, padx=6, pady=6)


    # ── Helpers UI ───────────────────────────────────────────

    def _refresh_filter_info(self):
        parts = []
        if self.pre_loudnorm.get():  parts.append("loudnorm")
        if self.pre_denoise.get():   parts.append("afftdn")
        if self.pre_voiceband.get(): parts.append("highpass=200,lowpass=3000")
        db = self.pre_volume_db.get()
        if abs(db) >= 0.5:           parts.append(f"volume={db:+.1f}dB")
        if parts:
            self._filter_info.config(
                text=f"  {t('pre_filters_on')}" + "  →  ".join(parts), fg=WARN)
        else:
            self._filter_info.config(
                text=f"  {t('pre_filters_off')}", fg=FG2)

    def _lang_display(self, code: str) -> str:
        """Libellé combobox pour un code, y compris auto / none."""
        if code == AUTO_LANG:      return t("lang_auto")
        if code == NO_TRANSLATION: return t("lang_none")
        return lang_label(code)

    def _lang_from_display(self, label: str) -> str:
        """Code depuis un libellé combobox (ou un code déjà nu)."""
        if label == t("lang_auto"):  return AUTO_LANG
        if label == t("lang_none"):  return NO_TRANSLATION
        return lang_code(label)

    def _on_lang_select(self, _=None):
        self.to_lang.set(self._lang_from_display(self.to_lang.get()))
        save_settings(self.root_dir, target_lang=self._get_lang())

    def _on_src_lang_select(self, _=None):
        self.src_lang.set(self._lang_from_display(self.src_lang.get()))
        self._detected_lang = None   # nouveau choix ⇒ oublie la détection
        save_settings(self.root_dir, src_lang=self._get_src_lang())

    def _get_lang(self) -> str:
        return self._lang_from_display(self.to_lang.get())

    def _get_src_lang(self) -> str:
        return self._lang_from_display(self.src_lang.get())

    def _resolved_src_lang(self) -> str | None:
        """Langue source effective : choix explicite, sinon détection whisper."""
        src = self._get_src_lang()
        if src != AUTO_LANG:
            return src
        return self._detected_lang

    def _log_line(self, txt: str):
        self._log.configure(state="normal")
        self._log.insert("end", txt + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _busy(self, msg: str):
        self._status.set(msg)
        self._progress.start(10)
        for b in self._buttons_all:
            try: b.config(state="disabled")
            except Exception: pass

    def _idle(self, msg: str = ""):
        self._progress.stop()
        self._status.set(msg or t("status_ready"))
        for b in self._buttons_all:
            try: b.config(state="normal")
            except Exception: pass

    def _show_translate_btn(self):
        if self._btn_translate and not self._btn_translate.winfo_ismapped():
            self._btn_translate.pack(side="left", padx=(0,8),
                                     before=self._btn_include)

    def _update_mkv_btn(self, filepath: str = ""):
        if not self._btn_include:
            return
        AUDIO_EXTS = {".mp3",".wav",".ogg",".flac",".aac",
                      ".m4a",".opus",".wma"}
        ext = os.path.splitext(filepath)[1].lower()
        if ext in AUDIO_EXTS:
            self._btn_include.config(state="disabled")
            self._btn_include.pack_forget()
        else:
            if not self._btn_include.winfo_ismapped():
                self._btn_include.pack(side="left")
            self._btn_include.config(state="normal")

    def _validate(self) -> str | None:
        p = self.video_path.get().strip()
        if not p:
            messagebox.showwarning(t("err_file_missing"),
                                   t("err_file_missing_msg"))
            return None
        p = os.path.normpath(p)
        if not os.path.isfile(p):
            messagebox.showerror(t("err_file_not_found"),
                                 t("err_file_not_found_msg") + p)
            return None
        self.video_path.set(p)
        return p

    # ── Exécution scripts ────────────────────────────────────

    def _run_cmd(self, cmd: list, label: str, on_success=None):
        self._busy(f"{label}…")
        self._log_line(f"\n▶  {label}")
        self._log_line("   " + " ".join(
            f'"{c}"' if " " in str(c) else str(c) for c in cmd))
        self._log_line("─" * 64)

        def worker():
            try:
                # CWD : %TEMP% sur Windows pour eviter les politiques
                # de securite qui bloquent l'execution depuis une cle USB
                # ou un lecteur reseau. Sur Linux : root_dir (normal).
                import tempfile as _tf
                _cwd = _tf.gettempdir() if IS_WINDOWS else self.root_dir
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    cwd=_cwd, creationflags=NO_WINDOW)
                for line in proc.stdout:
                    txt = line.rstrip()
                    m = _DETECT_RE.search(txt)
                    if m:
                        code = m.group(1)
                        self._detected_lang = code
                        self.after(0, self._log_line,
                                   "🌐 " + t("log_lang_detected",
                                             name=LANG_NAMES.get(code, code)))
                    self.after(0, self._log_line, txt)
                proc.wait()
                if proc.returncode == 0:
                    self.after(0, self._log_line,
                               f"\n✔  {label} {t('status_done')}")
                    self.after(0, self._idle,
                               f"✔  {label} {t('status_done')}")
                    if on_success:
                        self.after(0, on_success)
                else:
                    code = proc.returncode
                    msg  = f"\n✘  {t('err_generic')} (code {code})"
                    self.after(0, self._log_line, msg)
                    # 0xC0000135 = STATUS_DLL_NOT_FOUND : whisper-cli.exe
                    # requiert le runtime Visual C++ x64 (MSVCP140.dll,
                    # VCRUNTIME140*.dll, VCOMP140.dll).
                    if code in (3221225781, -1073741515):
                        self.after(0, self._log_line,
                                   "ℹ  " + t("err_dll_hint"))
                    self.after(0, self._idle,
                               t("status_error", label=label))
                    self.after(0, messagebox.showerror,
                               t("err_generic"),
                               t("err_failed", label=label, code=code))
            except FileNotFoundError as e:
                self.after(0, self._log_line, f"\n✘  {e}")
                self.after(0, self._idle, "✘  " + t("err_script_missing"))
                self.after(0, messagebox.showerror,
                           t("err_script_missing"), str(e))
            except Exception as e:
                self.after(0, self._log_line, f"\n✘  {e}")
                self.after(0, self._idle)

        threading.Thread(target=worker, daemon=True).start()

    # ── Actions ──────────────────────────────────────────────

    def _browse(self):
        p = filedialog.askopenfilename(
            title=t("sec_file"),
            filetypes=[
                (t("filter_video"), "*.mp4 *.mkv *.webm *.avi *.mov *.flv *.ts *.m4v"),
                (t("filter_audio"), "*.mp3 *.wav *.m4a *.ogg *.flac *.aac"),
                (t("filter_all"),   "*.*"),
            ])
        if p:
            self.video_path.set(p)
            self._log_line(f"📂 {p}\n")
            self._update_mkv_btn(p)

    def _open_recorder(self):
        RecorderWindow(self)

    def _open_downloader(self):
        DownloadWindow(self)


    def _update_model_hint(self):
        """Met à jour le hint contextuel selon le modèle sélectionné."""
        hints = {
            "tiny":   t("model_hint_tiny"),
            "base":   t("model_hint_base"),
            "small":  t("model_hint_small"),
            "medium": t("model_hint_medium"),
            "large":  t("model_hint_large"),
        }
        name = self.model_key.get().lower()
        hint = next((v for k, v in hints.items() if name.startswith(k)), "")
        if hasattr(self, "_model_hint_var"):
            self._model_hint_var.set(hint)

    def _run_audio(self):
        video = self._validate()
        if not video: return
        src = self._get_src_lang()   # langue de l'audio = -l passé à whisper
        cmd = self._script("audio2en") + [video, self._model()]
        if src != AUTO_LANG:
            cmd.append(src)          # omis ⇒ auto-détection whisper
        self._run_cmd(cmd, t("btn_audio").replace("\n", " "))


    def _run_export_audio(self):
        """
        Applique les filtres actifs (loudnorm, afftdn, filtre voix, volume)
        et enregistre le résultat dans un nouveau fichier suffixé -vol.

        Comportements selon la source :
          - Fichier vidéo (mp4, mkv…)  → extrait l'audio → <nom>-vol.mp3
          - Fichier audio (mp3, wav…)  → applique les filtres → <nom>-vol.<ext>

        Si aucun filtre n'est actif, applique quand même une copie simple
        (utile pour extraire l'audio d'une vidéo sans traitement).
        """
        video = self._validate()
        if not video:
            return

        ffmpeg = self._ffmpeg()
        if not os.path.isfile(ffmpeg):
            messagebox.showerror(t("err_file_not_found"),
                                 ffmpeg, parent=self)
            return

        src_ext  = os.path.splitext(video)[1].lower()
        base     = os.path.splitext(video)[0]

        AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac",
                      ".aac", ".m4a", ".opus", ".wma"}
        is_audio   = src_ext in AUDIO_EXTS

        # Extension de sortie
        if is_audio:
            out_ext = src_ext   # même format
        else:
            out_ext = ".mp3"    # extraction audio depuis vidéo

        # Évite un double suffixe si déjà -vol
        if base.endswith("-vol"):
            base = base[:-4]
        out_path = base + "-vol" + out_ext

        # Filtres audio actifs
        af = self._build_audio_filter()

        self._log_line(f"\n💾  {t('pre_export_log')}")
        self._log_line(f"   {t('preproc_source')}{os.path.basename(video)}")
        self._log_line(f"   {t('preproc_out')}{os.path.basename(out_path)}")
        if af:
            self._log_line(f"   {t('preproc_filters')}{af}")
        self._log_line("─" * 64)

        # Construction de la commande ffmpeg
        cmd = [ffmpeg, "-y", "-i", video]

        if is_audio:
            # Audio → audio : applique les filtres, recompresse si nécessaire
            if af:
                cmd += ["-af", af]
            else:
                cmd += ["-c:a", "copy"]
        else:
            # Vidéo → audio : extrait + filtre
            cmd += ["-vn"]          # pas de piste vidéo
            if af:
                cmd += ["-af", af]
            cmd += ["-q:a", "4"]    # qualité MP3 variable (~165 kbps)

        cmd.append(out_path)

        def on_done():
            self._log_line(
                f"   ✔  {t('pre_export_done', name=os.path.basename(out_path))}")
            # Propose de charger le fichier produit
            if messagebox.askyesno(
                    t("pre_export_load_title"),
                    t("pre_export_load_msg",
                      name=os.path.basename(out_path)),
                    parent=self):
                self.video_path.set(out_path)
                self._log_line(f"📂 {out_path}")

        self._run_cmd(cmd, t("pre_export_btn"), on_success=on_done)

    def _run_analyze(self):
        video = self._validate()
        if not video: return
        ffprobe = self._ffprobe()
        ffmpeg  = self._ffmpeg()
        if not os.path.isfile(ffprobe):
            messagebox.showerror(t("err_file_not_found"),
                                 t("analyze_missing") + ffprobe)
            return
        self._busy(t("status_analyzing"))
        self._log_line(f"\n🔍  {t('btn_analyze')}…")
        self._log_line("─" * 64)

        def worker():
            try:
                r = subprocess.run(
                    [ffprobe, "-v", "quiet", "-print_format", "json",
                     "-show_format", "-show_streams", video],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    creationflags=NO_WINDOW)
                info: dict = {}
                try:
                    data = json.loads(r.stdout)
                    fmt  = data.get("format", {})
                    info[t("analyze_file")]    = os.path.basename(video)
                    dur = float(fmt.get("duration", 0))
                    h, m, s = int(dur//3600), int((dur%3600)//60), dur%60
                    info[t("analyze_dur")]     = f"{h:02d}:{m:02d}:{s:05.2f}"
                    info[t("analyze_size")]    = (
                        f"{int(fmt.get('size',0))//1024//1024} Mo"
                        if fmt.get("size") else "—")
                    info[t("analyze_bitrate")] = (
                        f"{int(fmt.get('bit_rate',0))//1000} kb/s"
                        if fmt.get("bit_rate") else "—")
                    for st in data.get("streams", []):
                        ct = st.get("codec_type","")
                        if ct=="video" and t("analyze_video") not in info:
                            info[t("analyze_video")] = (
                                f"{st.get('codec_name','?').upper()}  "
                                f"{st.get('width','?')}×{st.get('height','?')}  "
                                f"{st.get('r_frame_rate','?')} fps")
                        elif ct=="audio" and t("analyze_audio") not in info:
                            info[t("analyze_audio")] = (
                                f"{st.get('codec_name','?').upper()}  "
                                f"{st.get('sample_rate','?')} Hz  "
                                f"{st.get('channels','?')} ch  "
                                f"lang={st.get('tags',{}).get('language','?')}")
                except Exception as e:
                    info["ffprobe"] = str(e)

                r2 = subprocess.run(
                    [ffmpeg, "-i", video, "-af", "volumedetect",
                     "-f", "null", "NUL" if IS_WINDOWS else "/dev/null"],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    creationflags=NO_WINDOW)
                combined = r2.stdout + r2.stderr
                for pat, key in [
                    (r"mean_volume:\s*([\-\d.]+)\s*dB", "analyze_vol_mean"),
                    (r"max_volume:\s*([\-\d.]+)\s*dB",  "analyze_vol_max"),
                ]:
                    m = re.search(pat, combined)
                    if m:
                        info[t(key)] = m.group(1) + " dB"

                self.after(0, self._show_info, info)
                self.after(0, self._idle, t("analyze_done"))
                self.after(0, self._log_line, t("analyze_done"))
            except Exception as e:
                self.after(0, self._log_line, f"✘  {e}")
                self.after(0, self._idle, t("analyze_err"))

        threading.Thread(target=worker, daemon=True).start()

    def _show_info(self, info: dict):
        self._info_text.configure(state="normal")
        self._info_text.delete("1.0", "end")
        col_w = max(len(k) for k in info) + 2
        for k, v in info.items():
            self._info_text.insert("end", f"  {k:<{col_w}}{v}\n")
        self._info_text.configure(state="disabled")
        if not self._info_frame.winfo_ismapped():
            self._info_frame.pack(fill="x", padx=26, pady=(4,0))

    def _build_audio_filter(self) -> str | None:
        parts = []
        if self.pre_loudnorm.get():  parts.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        if self.pre_denoise.get():   parts.append("afftdn=nf=-25")
        if self.pre_voiceband.get(): parts.append("highpass=f=200,lowpass=f=3000")
        db = self.pre_volume_db.get()
        if abs(db) >= 0.5:           parts.append(f"volume={db:+.1f}dB")
        return ",".join(parts) if parts else None

    def _run_whisper(self):
        video = self._validate()
        if not video: return
        af = self._build_audio_filter()

        if af:
            orig    = os.path.normpath(video)
            base    = os.path.splitext(orig)[0]
            if base.endswith(".__pre__"):
                base = base[:-len(".__pre__")]
            wav_pre = base + ".__pre__.wav"

            if os.path.normpath(wav_pre) == os.path.normpath(orig):
                messagebox.showerror(t("err_conflict_title"),
                                     t("err_conflict_msg"))
                return

            self._busy(t("status_preproc"))
            self._log_line(t("log_preproc_start"))
            self._log_line(t("log_preproc_source") + os.path.basename(orig))
            self._log_line(t("log_preproc_filters") + af)
            self._log_line(t("log_preproc_output") + os.path.basename(wav_pre))
            self._log_line("─" * 64)

            cmd_pre = [
                self._ffmpeg(), "-y",
                "-err_detect", "ignore_err",
                "-i",  os.path.normpath(orig),
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                "-af", af,
                os.path.normpath(wav_pre),
            ]

            def after_pre(wp=wav_pre, b=base):
                wb = self._whisper_bin()
                wm = self._whisper_model()
                if not os.path.isfile(wb):
                    self.after(0, messagebox.showerror,
                               t("err_whisper_missing"), wb)
                    self.after(0, self._idle)
                    return
                if not os.path.isfile(wm):
                    self.after(0, messagebox.showerror,
                               t("err_model_missing"), wm)
                    self.after(0, self._idle)
                    return
                srt_base = wp[:-4]
                src   = self._get_src_lang()
                to_en = (self._get_lang() == "en")   # -tr ne sait traduire que vers en
                # Sur Windows, subprocess.Popen (via CreateProcess)
                # quote automatiquement les éléments contenant des espaces.
                # Ne jamais entourer les chemins de guillemets dans la liste.
                cmd_w = [wb,
                         "-m", wm,
                         "-f", os.path.normpath(wp)]
                if src != AUTO_LANG:
                    cmd_w += ["-l", src]
                if to_en:
                    cmd_w += ["-tr"]
                cmd_w += ["-osrt",
                          "-of", os.path.normpath(srt_base)]
                self._run_cmd(cmd_w, t("btn_whisper").replace("\n"," "),
                              on_success=lambda: self._after_whisper_pre(
                                  wp, b, to_en))

            self._run_cmd(cmd_pre, t("sec_preproc").split("(")[0].strip(),
                          on_success=after_pre)
        else:
            src   = self._get_src_lang()
            to_en = (self._get_lang() == "en")
            cmd = self._script("soustitre") + [
                os.path.normpath(video), self._model(),
                "yes" if to_en else "no", src]
            self._run_cmd(cmd, t("btn_whisper").replace("\n"," "),
                          on_success=self._after_whisper)

    def _after_whisper_pre(self, wav_pre: str, base: str,
                           translated_en: bool = True):
        pre_base = os.path.splitext(wav_pre)[0]
        tgt_srt  = base + (".en.srt" if translated_en else ".srt")
        for candidate in (pre_base + ".en.srt", pre_base + ".srt"):
            if os.path.isfile(candidate):
                self._log_line(t("log_rename") +
                    f"{os.path.basename(candidate)} → {os.path.basename(tgt_srt)}")
                try:
                    if os.path.isfile(tgt_srt): os.remove(tgt_srt)
                    os.rename(candidate, tgt_srt)
                except OSError as e:
                    self._log_line(t("log_rename_failed") + str(e))
                break
        else:
            self._log_line(t("log_wav_missing") + f"{pre_base}[.en].srt")
        try:
            os.remove(wav_pre)
            self._log_line(t("log_wav_deleted"))
        except OSError:
            pass
        self._after_whisper()

    def _after_whisper(self):
        if self._get_lang() == NO_TRANSLATION:
            choices = [
                (t("choice_mkv_direct"), self._run_include),
                (t("choice_quit"),       self.destroy),
            ]
        else:
            self._show_translate_btn()
            choices = [
                (t("choice_translate"),  self._run_translate),
                (t("choice_mkv_direct"), self._run_include),
                (t("choice_quit"),       self.destroy),
            ]
        ChoiceDialog(self,
            title=t("dlg_subtitles_title"),
            message=t("dlg_subtitles_msg"),
            choices=choices)

    def _run_translate(self):
        video = self._validate()
        if not video: return
        lang = self._get_lang()
        if lang == NO_TRANSLATION:
            messagebox.showinfo(t("sec_lang").split(" ", 1)[-1],
                                t("err_no_target"))
            return
        base = os.path.splitext(video)[0]
        # SRT anglais (whisper -tr) prioritaire, sinon SRT langue source
        srt       = base + ".en.srt"
        from_lang = "en"
        if not os.path.isfile(srt):
            srt = base + ".srt"
            from_lang = self._resolved_src_lang() or "en"
        if not os.path.isfile(srt):
            messagebox.showwarning(t("err_srt_missing"),
                                   t("err_srt_missing_msg") + base)
            return
        if from_lang == lang:
            messagebox.showinfo(t("btn_translate").replace("\n", " "),
                                t("err_same_lang"))
            return
        cmd  = self._script("traduire-srt") + [srt, from_lang, lang]
        self._run_cmd(cmd, t("btn_translate").replace("\n"," "),
                      on_success=self._after_translate)

    def _after_translate(self):
        ChoiceDialog(self,
            title=t("dlg_translate_title"),
            message=t("dlg_translate_msg"),
            choices=[
                (t("choice_mkv"),      self._run_include),
                (t("choice_continue"), lambda: None),
                (t("choice_quit"),     self.destroy),
            ],
            extra_widget=self._make_lang_row)

    def _make_lang_row(self, parent):
        row = tk.Frame(parent, bg=BG2)
        row.pack(fill="x", pady=(6,0))
        tk.Label(row, text=t("choice_other_lang"), bg=BG2, fg=FG2,
                 font=FONT_UI).pack(side="left")
        cur = self._get_lang()
        if cur not in TARGET_LANGUAGES:
            cur = "fr"
        var = tk.StringVar(value=lang_label(cur))
        cb  = ttk.Combobox(row, textvariable=var,
                           values=[lang_label(c) for c in TARGET_LANGUAGES],
                           width=18, state="readonly")
        cb.pack(side="left", padx=(8,8))
        cb.bind("<<ComboboxSelected>>",
                lambda e: var.set(lang_code(var.get())))
        def do_translate():
            self.to_lang.set(lang_code(var.get()))
            parent.winfo_toplevel().destroy()
            self._run_translate()
        mkbtn(row, t("choice_translate_btn"), do_translate,
              color="#1a5c38", fg=FG).pack(side="left")

    def _run_include(self):
        video = self._validate()
        if not video: return
        base    = os.path.splitext(video)[0]
        lang    = self._get_lang()
        if lang == NO_TRANSLATION:   # transcription seule ⇒ langue source
            lang = self._resolved_src_lang() or "und"
        srt_en  = base + ".en.srt"
        srt_tgt = base + f".{lang}.srt"
        srt_nat = base + ".srt"

        if (self.opt_dual_sub.get()
                and os.path.isfile(srt_en)
                and os.path.isfile(srt_tgt)):
            self._run_include_dual(video, srt_en, srt_tgt, lang)
            return

        best = next((c for c in (srt_tgt, srt_nat, srt_en)
                     if os.path.isfile(c)), None)

        # Nom de sortie avec suffixe -subs pour éviter l'écrasement
        base_out = os.path.splitext(video)[0] + "-subs.mkv"

        if best:
            self._log_line(t("log_srt_detected", name=os.path.basename(best)))
            self._include_mono(video, best, base_out)
        else:
            self._log_line(t("log_no_srt"))
            srt = filedialog.askopenfilename(
                title=t("dlg_srt_title"),
                initialdir=os.path.dirname(video),
                filetypes=[(t("dlg_ft_srt"), "*.srt"),
                           (t("dlg_ft_all"), "*.*")])
            if not srt:
                self._idle()
                return
            self._include_mono(video, srt, base_out)

    def _is_audio_only(self, filepath: str) -> bool:
        AUDIO_EXTS = {".mp3",".wav",".ogg",".flac",".aac",
                      ".m4a",".opus",".wma"}
        if os.path.splitext(filepath)[1].lower() in AUDIO_EXTS:
            return True
        ffprobe = self._ffprobe()
        if not os.path.isfile(ffprobe):
            return False
        try:
            r = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=codec_type",
                 "-of", "csv=p=0", filepath],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                creationflags=NO_WINDOW, timeout=8)
            return "video" not in r.stdout
        except Exception:
            return False


    def _include_mono(self, video: str, srt: str, output: str) -> None:
        """
        Intègre un seul SRT dans un MKV via ffmpeg.
        Nom de sortie explicitement contrôlé (suffixe -subs).
        Détecte si la source est audio-only pour adapter les -map.
        """
        lang_str   = self._get_lang()
        if lang_str == NO_TRANSLATION:
            lang_str = self._resolved_src_lang() or "und"
        lang3      = ISO_639_2.get(lang_str, lang_str)
        audio_only = self._is_audio_only(video)

        map_src = (["-map", "0:a"]
                   if audio_only
                   else ["-map", "0:v", "-map", "0:a?"])

        cmd = (
            [self._ffmpeg(), "-y", "-i", video, "-i", srt]
            + map_src
            + ["-map", "1:0",
               "-c:v", "copy", "-c:a", "copy", "-c:s", "srt",
               "-metadata:s:s:0", f"language={lang3}",
               "-disposition:s:0", "default",
               output]
        )
        self._log_line(f"\n📦  {os.path.basename(output)}")
        self._run_cmd(
            cmd,
            t("btn_mkv").replace("\n", " "),
            on_success=self._after_include,
        )

    def _run_include_dual(self, video, srt_en, srt_tgt, lang_code_str):
        base   = os.path.splitext(video)[0]
        # Retire l'extension .mkv du base si le source est déjà un .mkv
        # pour éviter "output same as input" (ffmpeg refuse d'écraser en place)
        if base.lower().endswith("-subs"):
            base = base[:-5]   # évite film-subs-subs.mkv
        output = base + "-subs.mkv"
        lang3      = ISO_639_2.get(lang_code_str, lang_code_str)
        lang_name  = LANG_NAMES.get(lang_code_str, lang_code_str)
        audio_only = self._is_audio_only(video)

        self._log_line(t("log_dual_header") + lang_code_str.upper() + ")")
        if audio_only:
            self._log_line(t("log_dual_audio_only"))

        map_src = (["-map", "0:a"] if audio_only
                   else ["-map", "0:v", "-map", "0:a?"])
        cmd = ([self._ffmpeg(), "-y", "-i", video,
                "-i", srt_en, "-i", srt_tgt]
               + map_src
               + ["-map", "1:0", "-map", "2:0",
                  "-c:v", "copy", "-c:a", "copy", "-c:s", "srt",
                  "-metadata:s:s:0", "language=eng",
                  "-metadata:s:s:0", "title=English",
                  "-metadata:s:s:1", f"language={lang3}",
                  "-metadata:s:s:1", f"title={lang_name}",
                  "-disposition:s:1", "default",
                  output])
        self._run_cmd(cmd, t("btn_mkv").replace("\n"," "),
                      on_success=self._after_include)

    def _after_include(self):
        ChoiceDialog(self,
            title=t("dlg_mkv_title"),
            message=t("dlg_mkv_msg"),
            choices=[
                (t("choice_new_file"), lambda: None),
                (t("choice_quit"),     self.destroy),
            ])
