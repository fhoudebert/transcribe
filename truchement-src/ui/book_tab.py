"""
ui/book_tab.py — Onglet « Livre » : traduction de livre via llama.cpp local
=============================================================================
BookTabMixin, mélangé dans TranslatorApp comme FileTabMixin / DefTabMixin.

Le travail est fait par traduire-livre.py (racine de la clé, à côté de
l'exécutable — déployé par compile_app.py), lancé avec le python du venv en
SOUS-PROCESSUS : une traduction de livre dure des heures, elle doit pouvoir
être arrêtée net (bouton Arrêter) sans rien laisser d'incohérent dans ce
process, et reprendre ensuite grâce au cache du script.

Le script écrit deux sortes de lignes sur stdout :
  • du texte lisible → recopié tel quel dans le journal de l'onglet ;
  • « @@{json} »      → événements (plan, progress, end, error) qui pilotent
                        la barre de progression et le résumé chiffré.

Indépendant des langues argostranslate : un modèle LLM traduit bien plus de
paires que les paquets installés, d'où des sélecteurs source/cible propres à
l'onglet (en → fr par défaut). Les réglages (URL, passes, taille des blocs…)
sont mémorisés dans build/truchement-livre.json.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
from tkinter import ttk, messagebox, filedialog

import bootstrap
from config import C, F, LANG_NAMES, lang_code
from ui.file_tab import _dialog_start


_SCRIPT = "traduire-livre.py"
_DEFAULTS = {
    "url": "http://127.0.0.1:8080/v1",
    "model": "",
    "src": "en",
    "tgt": "fr",
    "passes": 2,
    "max_chars": 2500,
    "glossary": "",
    "dir": "",
}
_TRIAL_UNITS = 10
_JOURNAL_MAX_LINES = 2000
_ERR_FG = "#FF6B6B"


def _settings_path() -> str:
    build = os.path.join(bootstrap.BASE_DIR, "build")
    base = build if os.path.isdir(build) else bootstrap.BASE_DIR
    return os.path.join(base, "truchement-livre.json")


def _load_settings() -> dict:
    data = dict(_DEFAULTS)
    try:
        with open(_settings_path(), encoding="utf-8") as fh:
            saved = json.load(fh)
        if isinstance(saved, dict):
            data.update({k: v for k, v in saved.items() if k in _DEFAULTS})
    except (OSError, ValueError):
        pass
    return data


def _script_path() -> str | None:
    candidates = [
        os.path.join(bootstrap.BASE_DIR, _SCRIPT),
        # Exécution depuis les sources : le script est à côté de main.py.
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     _SCRIPT),
    ]
    return next((p for p in candidates if os.path.isfile(p)), None)


def _python() -> str | None:
    if bootstrap.VENV_PYTHON:
        return bootstrap.VENV_PYTHON
    if not getattr(sys, "frozen", False):
        return sys.executable          # développement : python courant
    return None


def _fmt_duration(sec) -> str:
    if sec is None:
        return "…"
    sec = int(max(0, sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d}"
    if m:
        return f"{m} min {s:02d}"
    return f"{s} s"


def _server_root(url: str) -> str:
    root = url.strip().rstrip("/")
    return root[:-3] if root.endswith("/v1") else root


class BookTabMixin:

    # ── Construction ──────────────────────────────────────────────────────────

    def build_book_tab(self, parent: ttk.Frame) -> None:
        st = _load_settings()
        self._book_settings = st
        self._book_proc: subprocess.Popen | None = None
        self._book_queue: queue.Queue = queue.Queue()
        self._book_stopping = False
        self._book_out = ""
        self._book_last_error = ""

        self._book_file = tk.StringVar(value="")
        self._book_url = tk.StringVar(value=st["url"])
        self._book_model = tk.StringVar(value=st["model"])
        self._book_chunk = tk.StringVar(value=str(st["max_chars"]))
        self._book_gloss = tk.StringVar(value=st["glossary"])
        self._book_dir = st["dir"]

        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True, padx=24, pady=14)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(6, weight=1)

        # Titre + formats
        head = ttk.Frame(outer)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._book_lbl_title = ttk.Label(
            head, text="", font=F["title"],
            foreground=C["text"], background=C["bg"],
        )
        self._book_lbl_title.pack(side="left")
        self._book_lbl_fmt = ttk.Label(head, text="", style="Mu.TLabel")
        self._book_lbl_fmt.pack(side="left", padx=(16, 0), pady=(4, 0))

        # Choix du livre
        pf = tk.Frame(outer, bg=C["card"],
                      highlightbackground=C["border"], highlightthickness=1)
        pf.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        pf.columnconfigure(1, weight=1)
        self._book_pick_btn = ttk.Button(pf, text="", style="Ghost.TButton",
                                         command=self._book_pick)
        self._book_pick_btn.grid(row=0, column=0, padx=8, pady=8)
        self._book_file_lbl = ttk.Label(
            pf, textvariable=self._book_file, background=C["card"],
            foreground=C["muted"], font=F["body"], anchor="w",
        )
        self._book_file_lbl.grid(row=0, column=1, sticky="ew", padx=(4, 12))

        # Réglages — grille à 4 colonnes : libellé | champ | libellé | champ
        cfg = tk.Frame(outer, bg=C["card"],
                       highlightbackground=C["border"], highlightthickness=1)
        cfg.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        cfg.columnconfigure(1, weight=3)
        cfg.columnconfigure(3, weight=2)

        def lbl(row, col, attr):
            w = ttk.Label(cfg, text="", background=C["card"],
                          foreground=C["muted"], font=F["small"])
            w.grid(row=row, column=col, sticky="w", padx=(10, 6), pady=4)
            setattr(self, attr, w)

        def cell(row, col, colspan=1):
            fr = tk.Frame(cfg, bg=C["card"])
            fr.grid(row=row, column=col, columnspan=colspan, sticky="ew",
                    pady=4, padx=(0, 10))
            return fr

        def entry(parent, var, width=None):
            fr = tk.Frame(parent, bg=C["card"], highlightbackground=C["border"],
                          highlightthickness=1)
            fr.pack(side="left", fill="x", expand=True)
            e = tk.Entry(fr, textvariable=var, bg=C["card"], fg=C["text"],
                         disabledbackground=C["card"],
                         disabledforeground=C["muted"],
                         insertbackground=C["accent"], relief="flat",
                         font=F["body"], bd=3, selectbackground=C["accent"],
                         **({"width": width} if width else {}))
            e.pack(fill="x", expand=True)
            return e

        def hint(row, col, attr, colspan=1):
            w = ttk.Label(cfg, text="", background=C["card"],
                          foreground=C["muted"], font=F["small"])
            w.grid(row=row, column=col, columnspan=colspan, sticky="w",
                   padx=(0, 10))
            setattr(self, attr, w)

        # Ligne 0 : serveur (+ bouton Tester) | résultat du test
        lbl(0, 0, "_book_lbl_url")
        c = cell(0, 1)
        self._book_url_entry = entry(c, self._book_url)
        self._book_test_btn = ttk.Button(c, text="", style="Def.TButton",
                                         command=self._book_test_server)
        self._book_test_btn.pack(side="left", padx=(8, 0))
        hint(0, 2, "_book_srv_lbl", colspan=2)

        # Ligne 1 : langues | passes
        lbl(1, 0, "_book_lbl_langs")
        lang_codes = sorted(LANG_NAMES, key=lambda c: LANG_NAMES[c])
        names = [LANG_NAMES[c] for c in lang_codes]
        c = cell(1, 1)
        self._book_cb_src = ttk.Combobox(c, values=names, state="readonly",
                                         width=18, font=F["body"])
        self._book_cb_src.pack(side="left", fill="x", expand=True)
        self._book_swap_btn = ttk.Button(c, text="⇄", width=3,
                                         style="Ghost.TButton",
                                         command=self._book_swap)
        self._book_swap_btn.pack(side="left", padx=6)
        self._book_cb_tgt = ttk.Combobox(c, values=names, state="readonly",
                                         width=18, font=F["body"])
        self._book_cb_tgt.pack(side="left", fill="x", expand=True)
        self._book_cb_src.set(LANG_NAMES.get(st["src"], LANG_NAMES["en"]))
        self._book_cb_tgt.set(LANG_NAMES.get(st["tgt"], LANG_NAMES["fr"]))

        lbl(1, 2, "_book_lbl_passes")
        self._book_cb_passes = ttk.Combobox(cfg, values=[], state="readonly",
                                            width=24, font=F["body"])
        self._book_cb_passes.grid(row=1, column=3, sticky="ew", pady=4,
                                  padx=(0, 10))
        self._book_passes_idx = min(max(int(st["passes"]), 1), 3) - 1

        # Ligne 2 : taille des blocs | modèle
        lbl(2, 0, "_book_lbl_chunk")
        c = cell(2, 1)
        self._book_spin = tk.Spinbox(
            c, from_=500, to=12000, increment=250, width=7,
            textvariable=self._book_chunk, bg=C["card"], fg=C["text"],
            disabledbackground=C["card"], disabledforeground=C["muted"],
            buttonbackground=C["panel"], insertbackground=C["accent"],
            relief="flat", font=F["body"], highlightthickness=1,
            highlightbackground=C["border"],
        )
        self._book_spin.pack(side="left")
        lbl(2, 2, "_book_lbl_model")
        self._book_model_entry = entry(cell(2, 3), self._book_model)

        # Ligne 3 : glossaire (+ …) | aide
        lbl(3, 0, "_book_lbl_gloss")
        c = cell(3, 1)
        self._book_gloss_entry = entry(c, self._book_gloss)
        self._book_gloss_btn = ttk.Button(c, text="…", width=3,
                                          style="Ghost.TButton",
                                          command=self._book_pick_glossary)
        self._book_gloss_btn.pack(side="left", padx=(6, 0))
        hint(3, 2, "_book_lbl_gloss_hint", colspan=2)

        # Boutons
        br = ttk.Frame(outer)
        br.grid(row=3, column=0, sticky="w", pady=(2, 8))
        self._book_go_btn = ttk.Button(br, text="", style="Acc.TButton",
                                       command=lambda: self._book_start(0))
        self._book_go_btn.pack(side="left", padx=(0, 8))
        self._book_trial_btn = ttk.Button(
            br, text="", style="Def.TButton",
            command=lambda: self._book_start(_TRIAL_UNITS),
        )
        self._book_trial_btn.pack(side="left", padx=(0, 8))
        self._book_stop_btn = ttk.Button(br, text="", style="Ghost.TButton",
                                         command=self._book_stop,
                                         state="disabled")
        self._book_stop_btn.pack(side="left", padx=(0, 8))
        self._book_open_btn = ttk.Button(br, text="", style="Ghost.TButton",
                                         command=self._book_open_folder,
                                         state="disabled")
        self._book_open_btn.pack(side="left")

        # Progression
        self._book_progress = ttk.Progressbar(outer, mode="determinate",
                                              maximum=1, value=0)
        self._book_progress.grid(row=4, column=0, sticky="ew")
        self._book_prog_lbl = ttk.Label(outer, text="", style="Mu.TLabel")
        self._book_prog_lbl.grid(row=5, column=0, sticky="w", pady=(4, 6))

        # Journal synthétique
        jf = tk.Frame(outer, bg=C["card"], highlightbackground=C["border"],
                      highlightthickness=1)
        jf.grid(row=6, column=0, sticky="nsew")
        jf.columnconfigure(0, weight=1)
        jf.rowconfigure(0, weight=1)
        self._book_log = tk.Text(
            jf, height=8, wrap="word", bg=C["card"], fg=C["text"],
            font=F["mono"], relief="flat", bd=6, state="disabled",
            insertbackground=C["accent"], selectbackground=C["accent"],
        )
        self._book_log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(jf, orient="vertical", command=self._book_log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._book_log.configure(yscrollcommand=sb.set)
        self._book_log.tag_configure("ok", foreground=C["teal"])
        self._book_log.tag_configure("warn", foreground=C["gold"])
        self._book_log.tag_configure("err", foreground=_ERR_FG)
        self._book_log.tag_configure("head", foreground=C["accent"])
        self._book_log.tag_configure("muted", foreground=C["muted"])

    # ── i18n ──────────────────────────────────────────────────────────────────

    def _book_refresh_i18n(self) -> None:
        t = self._t
        g = t.get
        self._book_lbl_title.configure(text=g("book_title", "Book translation"))
        self._book_lbl_fmt.configure(text=g("book_formats", ""))
        self._book_pick_btn.configure(text=g("book_pick_btn", "📂  Choose a book…"))
        self._book_lbl_url.configure(text=g("book_server", "Server") + " :")
        self._book_test_btn.configure(text=g("book_test_btn", "Test"))
        self._book_lbl_langs.configure(text=g("book_langs", "Languages") + " :")
        self._book_lbl_passes.configure(text=g("book_passes", "Passes") + " :")
        self._book_lbl_chunk.configure(text=g("book_chunk", "Block size") + " :")
        self._book_lbl_model.configure(text=g("book_model", "Model") + " :")
        self._book_lbl_gloss.configure(text=g("book_glossary", "Glossary") + " :")
        self._book_lbl_gloss_hint.configure(text=g("book_glossary_hint", ""))
        self._book_go_btn.configure(text=g("book_translate_btn", "Translate book  →"))
        self._book_trial_btn.configure(
            text=g("book_trial_btn", "Trial ({n} blocks)").format(n=_TRIAL_UNITS))
        self._book_stop_btn.configure(text=g("book_stop_btn", "■  Stop"))
        self._book_open_btn.configure(text=g("book_open_btn", "📁  Open folder"))

        cur = self._book_cb_passes.current()
        idx = cur if cur >= 0 else self._book_passes_idx
        self._book_cb_passes.configure(values=[
            g("book_passes_1", "1 — translation"),
            g("book_passes_2", "2 — + bilingual revision"),
            g("book_passes_3", "3 — + final proofreading"),
        ])
        self._book_cb_passes.current(idx)
        if not os.path.isfile(self._book_file.get()):
            self._book_file.set(g("book_none", "No book selected"))

    # ── Sélections ────────────────────────────────────────────────────────────

    def _book_pick(self) -> None:
        if self._book_proc is not None:
            return
        initialdir, initialfile = _dialog_start(self._book_dir)
        opts = {}
        if initialdir:
            opts["initialdir"] = initialdir
        if initialfile:
            opts["initialfile"] = initialfile
        path = filedialog.askopenfilename(
            title=self._t.get("book_pick_btn", "Choose a book"),
            filetypes=[("EPUB, PDF, TXT", "*.epub *.pdf *.txt"),
                       ("EPUB", "*.epub"), ("PDF", "*.pdf"),
                       ("Text", "*.txt"), ("All files", "*.*")],
            **opts,
        )
        if path:
            self._book_file.set(path)
            self._book_dir = os.path.dirname(os.path.abspath(path))
            self._book_file_lbl.configure(foreground=C["text"])
            self._book_open_btn.configure(state="disabled")
            self._book_out = ""

    def _book_pick_glossary(self) -> None:
        initialdir, _ = _dialog_start(self._book_gloss.get() or self._book_dir)
        path = filedialog.askopenfilename(
            title=self._t.get("book_glossary", "Glossary"),
            filetypes=[("Text", "*.txt *.tsv *.csv"), ("All files", "*.*")],
            **({"initialdir": initialdir} if initialdir else {}),
        )
        if path:
            self._book_gloss.set(path)

    def _book_swap(self) -> None:
        s, t = self._book_cb_src.get(), self._book_cb_tgt.get()
        self._book_cb_src.set(t)
        self._book_cb_tgt.set(s)

    def _book_save_settings(self) -> dict:
        try:
            max_chars = int(self._book_chunk.get())
        except ValueError:
            max_chars = _DEFAULTS["max_chars"]
        max_chars = min(max(max_chars, 300), 12000)
        self._book_chunk.set(str(max_chars))
        st = {
            "url": self._book_url.get().strip() or _DEFAULTS["url"],
            "model": self._book_model.get().strip(),
            "src": lang_code(self._book_cb_src.get()) or "en",
            "tgt": lang_code(self._book_cb_tgt.get()) or "fr",
            "passes": max(self._book_cb_passes.current(), 0) + 1,
            "max_chars": max_chars,
            "glossary": self._book_gloss.get().strip(),
            "dir": self._book_dir or "",
        }
        self._book_settings = st
        try:
            with open(_settings_path(), "w", encoding="utf-8") as fh:
                json.dump(st, fh, ensure_ascii=False, indent=2)
        except OSError:
            pass
        return st

    # ── Test du serveur ───────────────────────────────────────────────────────

    def _book_test_server(self) -> None:
        root = _server_root(self._book_url.get())
        self._book_save_settings()
        self._book_srv_lbl.configure(text=self._t.get("book_testing", "…"),
                                     foreground=C["muted"])
        self._book_test_btn.configure(state="disabled")

        def work() -> None:
            # urllib et non requests : ce process n'a pas forcément le venv.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                with opener.open(root + "/health", timeout=5) as r:
                    r.read()
                model, ctx = "?", "?"
                try:
                    with opener.open(root + "/props", timeout=5) as r:
                        props = json.loads(r.read().decode("utf-8"))
                    gen = props.get("default_generation_settings") or {}
                    ctx = gen.get("n_ctx") or props.get("n_ctx") or "?"
                    model = os.path.basename(props.get("model_path") or "") or "?"
                except Exception:
                    pass
                msg = self._t.get("book_server_ok", "✔ {model} · ctx {ctx}") \
                    .format(model=model, ctx=ctx)
                color = C["teal"]
            except Exception as exc:
                reason = getattr(exc, "reason", None) or exc
                msg = self._t.get("book_server_ko", "✖ {err}").format(err=reason)
                color = _ERR_FG

            def done() -> None:
                self._book_srv_lbl.configure(text=msg, foreground=color)
                self._book_test_btn.configure(state="normal")
            try:
                self.after(0, done)
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True, name="book-test").start()

    # ── Lancement / arrêt ─────────────────────────────────────────────────────

    def _book_start(self, limit: int) -> None:
        t = self._t
        if self._book_proc is not None:
            messagebox.showinfo(t["error_title"], t.get("book_running", "Running."))
            return
        path = self._book_file.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showinfo(t["error_title"],
                                t.get("book_no_file", "Choose a book."))
            return
        script = _script_path()
        if not script:
            messagebox.showerror(t["error_title"],
                                 t.get("book_no_script", _SCRIPT + " ?"))
            return
        py = _python()
        if not py:
            messagebox.showerror(t["error_title"], self._venv_missing_msg())
            return
        st = self._book_save_settings()

        cmd = [py, "-u", script, path,
               "--src", st["src"], "--tgt", st["tgt"],
               "--url", st["url"], "--passes", str(st["passes"]),
               "--max-chars", str(st["max_chars"])]
        if st["model"]:
            cmd += ["--model", st["model"]]
        if st["glossary"]:
            cmd += ["--glossary", st["glossary"]]
        if limit:
            cmd += ["--limit", str(limit)]

        from translator import _clean_subprocess_env
        env = _clean_subprocess_env()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", bufsize=1, env=env, creationflags=flags,
                cwd=os.path.dirname(os.path.abspath(path)),
            )
        except OSError as exc:
            messagebox.showerror(t["error_title"], str(exc))
            return

        self._book_proc = proc
        self._book_stopping = False
        self._book_out = ""
        self._book_last_error = ""
        self._book_started = time.monotonic()
        self._book_set_running(True)
        self._book_progress.configure(maximum=1, value=0)
        self._book_prog_lbl.configure(text="")

        def reader() -> None:
            try:
                for line in proc.stdout:
                    self._book_queue.put(line.rstrip("\r\n"))
            finally:
                self._book_queue.put(None)        # fin de flux

        threading.Thread(target=reader, daemon=True, name="book-reader").start()
        self.after(150, self._book_poll)

    def _book_set_running(self, running: bool) -> None:
        on, off = ("disabled", "normal") if running else ("normal", "disabled")
        for w in (self._book_go_btn, self._book_trial_btn, self._book_pick_btn,
                  self._book_test_btn, self._book_gloss_btn):
            w.configure(state=on)
        for w in (self._book_cb_src, self._book_cb_tgt, self._book_cb_passes):
            w.configure(state="disabled" if running else "readonly")
        for w in (self._book_url_entry, self._book_model_entry,
                  self._book_gloss_entry, self._book_spin):
            w.configure(state=on)
        self._book_stop_btn.configure(state=off)

    def _book_stop(self) -> None:
        proc = self._book_proc
        if proc is None:
            return
        self._book_stopping = True
        self._book_stop_btn.configure(state="disabled")
        try:
            proc.terminate()
        except OSError:
            pass

    def _book_shutdown(self) -> None:
        """Appelé à la fermeture de la fenêtre : ne pas laisser tourner le script."""
        proc = self._book_proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    # ── Lecture de la sortie du script ────────────────────────────────────────

    def _book_poll(self) -> None:
        finished = False
        try:
            while True:
                line = self._book_queue.get_nowait()
                if line is None:
                    finished = True
                    break
                self._book_handle_line(line)
        except queue.Empty:
            pass
        if finished:
            self._book_finish()
        else:
            try:
                self.after(150, self._book_poll)
            except tk.TclError:
                pass

    def _book_handle_line(self, line: str) -> None:
        if line.startswith("@@"):
            try:
                ev = json.loads(line[2:])
            except ValueError:
                return
            self._book_event(ev)
            return
        if not line.strip():
            return
        s = line.lstrip()
        tag = None
        if s.startswith("✔"):
            tag = "ok"
        elif s.startswith("⚠"):
            tag = "warn"
        elif s.startswith(("✖", "Traceback", "Error", "Exception")):
            tag = "err"
        elif s.startswith("[") or s.startswith("─"):
            tag = "head"
        elif line.startswith("  "):
            tag = "muted"
        self._book_append(line, tag)

    def _book_append(self, line: str, tag: str | None = None) -> None:
        w = self._book_log
        w.configure(state="normal")
        w.insert("end", line + "\n", (tag,) if tag else ())
        n = int(w.index("end-1c").split(".")[0])
        if n > _JOURNAL_MAX_LINES:
            w.delete("1.0", f"{n - _JOURNAL_MAX_LINES}.0")
        w.see("end")
        w.configure(state="disabled")

    def _book_event(self, ev: dict) -> None:
        kind = ev.get("ev")
        if kind == "plan":
            self._book_progress.configure(maximum=max(ev.get("chars", 1), 1),
                                          value=0)
            self._book_units = ev.get("units", 0)
            self._book_show_progress(0, self._book_units, 0, None)
        elif kind == "progress":
            self._book_progress.configure(value=ev.get("done_chars", 0))
            total = max(ev.get("chars", 1), 1)
            pct = int(100 * ev.get("done_chars", 0) / total)
            self._book_show_progress(ev.get("done", 0), ev.get("units", 0),
                                     pct, ev.get("eta"))
        elif kind == "end":
            self._book_out = ev.get("out", "")
        elif kind == "error":
            self._book_last_error = ev.get("msg", "")

    def _book_show_progress(self, done: int, total: int, pct: int, eta) -> None:
        elapsed = time.monotonic() - getattr(self, "_book_started", time.monotonic())
        text = self._t.get(
            "book_progress",
            "{done}/{total} blocks · {pct} % · elapsed {elapsed} · remaining ~{eta}",
        ).format(done=done, total=total, pct=pct,
                 elapsed=_fmt_duration(elapsed), eta=_fmt_duration(eta))
        self._book_prog_lbl.configure(text=text)
        self.lbl_status.configure(text=f"📖 {pct} %")

    def _book_finish(self) -> None:
        proc = self._book_proc
        rc = proc.wait() if proc is not None else -1
        self._book_proc = None
        self._book_set_running(False)
        t = self._t
        if rc == 0 and self._book_out:
            self._book_progress.configure(value=self._book_progress["maximum"])
            self._book_open_btn.configure(state="normal")
            msg = t.get("book_done", "Book translated: {path}").format(
                path=self._book_out)
            self._book_prog_lbl.configure(text=msg)
            self.lbl_status.configure(text=msg)
            self.after(8000, lambda: self.lbl_status.configure(text=""))
        elif self._book_stopping:
            msg = t.get("book_stopped", "Stopped — run again to resume.")
            self._book_append(msg, "warn")
            self._book_prog_lbl.configure(text=msg)
            self.lbl_status.configure(text="")
        else:
            msg = t.get("book_failed", "Interrupted (code {rc}).").format(rc=rc)
            if self._book_last_error:
                msg += "\n" + self._book_last_error
            self._book_prog_lbl.configure(text=msg.split("\n")[0])
            self.lbl_status.configure(text="")
            messagebox.showerror(t["error_title"], msg)

    def _book_open_folder(self) -> None:
        path = self._book_out or self._book_file.get()
        if not path or not os.path.exists(path):
            return
        folder = os.path.dirname(os.path.abspath(path))
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", folder])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
