"""
recorder_window.py  —  Fenêtre dictaphone (RecorderWindow).
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

from dialog_windows import ChoiceDialog

class RecorderWindow(tk.Toplevel):
    """
    Fenêtre autonome de dictaphone.
    Enregistre via ffmpeg (WASAPI/dshow Windows, pulse Linux).
    Propose : sauvegarder le MP3, transcrire via audio2en, charger
    dans la fenêtre principale.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._parent       = parent
        self._proc         = None
        self._tmp_file     = None
        self._running      = False
        self._elapsed      = 0
        self._timer_id     = None
        self._dshow_devs: list[str] = []

        self.title(t("rec_title"))
        self.configure(bg=BG2)
        self.resizable(False, False)
        self.grab_set()
        self.focus_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.update_idletasks()
        w = 520
        h = 460 if IS_WINDOWS else 400
        px = parent.winfo_x() + parent.winfo_width()  // 2
        py = parent.winfo_y() + parent.winfo_height() // 2
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

        self._build()

        if IS_WINDOWS:
            threading.Thread(target=self._enum_dshow, daemon=True).start()

    # ── Construction UI ──────────────────────────────────────

    def _build(self):
        tk.Label(self, text=t("rec_title"), font=FONT_H1,
                 bg=BG2, fg=FG).pack(pady=(18, 3))
        tk.Label(self, text=t("rec_subtitle"),
                 font=FONT_SMALL, bg=BG2, fg=FG2).pack()

        tk.Frame(self, height=1, bg=BORDER).pack(fill="x", padx=20, pady=10)

        # ── Backend audio (Windows seulement) ──
        if IS_WINDOWS:
            self._backend = tk.StringVar(value="wasapi")

            brow = tk.Frame(self, bg=BG2)
            brow.pack(padx=20, fill="x", pady=(0, 4))
            tk.Label(brow, text=t("rec_backend"), bg=BG2, fg=FG2,
                     font=FONT_UI).pack(side="left")
            for val, lbl in [("wasapi", t("rec_wasapi")),
                              ("dshow",  t("rec_dshow"))]:
                tk.Radiobutton(
                    brow, text=lbl, variable=self._backend, value=val,
                    bg=BG2, fg=FG2, selectcolor=BG3,
                    activebackground=BG2, activeforeground=FG,
                    font=FONT_UI, cursor="hand2",
                    command=self._on_backend_change,
                ).pack(side="left", padx=(10, 0))

            # Ligne dshow (masquée si WASAPI)
            self._dshow_frame = tk.Frame(self, bg=BG2)
            self._dshow_frame.pack(padx=20, fill="x", pady=(0, 2))
            tk.Label(self._dshow_frame, text=t("rec_micro"), bg=BG2, fg=FG2,
                     font=FONT_UI).pack(side="left")
            self._dev_var = tk.StringVar(value="")
            self._dev_cb  = ttk.Combobox(
                self._dshow_frame, textvariable=self._dev_var,
                values=[t("rec_enum")], width=36,
                state="normal", font=FONT_UI,
            )
            self._dev_cb.pack(side="left", padx=(8, 0))
            self._dev_hint = tk.Label(
                self, text=t("rec_enum_progress"),
                font=FONT_SMALL, bg=BG2, fg=FG2, anchor="w")
            self._dev_hint.pack(padx=20, anchor="w", pady=(0, 2))

            # Info WASAPI
            self._wasapi_info = tk.Label(
                self,
                text=t("rec_wasapi_info"),
                font=FONT_SMALL, bg=BG2, fg=FG2, justify="left")
            self._wasapi_info.pack(padx=20, anchor="w")

            self._on_backend_change()   # affichage initial

        else:
            tk.Label(self,
                     text=t("rec_pulse_info"),
                     font=FONT_SMALL, bg=BG2, fg=FG2,
                     ).pack(padx=20, anchor="w")

        tk.Frame(self, height=1, bg=BORDER).pack(fill="x", padx=20, pady=8)

        # ── Timer + indicateur ──
        ind = tk.Frame(self, bg=BG2)
        ind.pack(pady=8)
        self._dot = tk.Label(ind, text="⏺",
                             font=(FONT_H1[0], 30), bg=BG2, fg=BG4)
        self._dot.pack(side="left", padx=(0, 10))
        self._timer_var = tk.StringVar(value="00:00")
        tk.Label(ind, textvariable=self._timer_var,
                 font=(FONT_MONO[0], 26, "bold"), bg=BG2, fg=FG,
                 ).pack(side="left")

        # Barre de niveau animée
        self._level_canvas = tk.Canvas(self, bg=BG2, height=16,
                                       highlightthickness=0)
        self._level_canvas.pack(fill="x", padx=30, pady=(0, 6))
        self._level_phase = 0

        self._status_var = tk.StringVar(value=t("rec_ready"))
        tk.Label(self, textvariable=self._status_var,
                 font=FONT_SMALL, bg=BG2, fg=FG2).pack()

        tk.Frame(self, height=1, bg=BORDER).pack(fill="x", padx=20, pady=8)

        # ── Langue parlée ──
        lrow = tk.Frame(self, bg=BG2)
        lrow.pack(padx=20, fill="x", pady=(0, 8))
        tk.Label(lrow, text=t("rec_lang"), bg=BG2, fg=FG2,
                 font=FONT_UI).pack(side="left")
        self._rec_lang = tk.StringVar(value="fr")
        _vals = [lang_label(c) for c in ALL_LANGUAGES]
        self._lang_cb_rec = ttk.Combobox(
            lrow, textvariable=self._rec_lang,
            values=_vals, width=22, state="readonly", font=FONT_UI,
        )
        self._lang_cb_rec.pack(side="left", padx=(8, 0))
        self._rec_lang.set(lang_label("fr"))
        self._lang_cb_rec.bind(
            "<<ComboboxSelected>>",
            lambda e: self._rec_lang.set(
                lang_code(self._rec_lang.get())))
        tk.Label(lrow, text=t("rec_lang_hint"),
                 bg=BG2, fg=BG4, font=FONT_SMALL).pack(side="left")

        # ── Boutons principaux ──
        brow = tk.Frame(self, bg=BG2)
        brow.pack(pady=4, padx=20, fill="x")

        self._btn_rec = mkbtn(brow, t("rec_btn_start"),
                              self._toggle, color=DANGER)
        self._btn_rec.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self._btn_save = mkbtn(brow, t("rec_btn_save"),
                               self._save, color=BG4, fg=FG2)
        self._btn_save.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._btn_save.config(state="disabled")

        self._btn_tx = mkbtn(brow, t("rec_btn_transcribe"),
                             self._transcribe, color=ACCENT)
        self._btn_tx.pack(side="left", expand=True, fill="x")
        self._btn_tx.config(state="disabled")

        self._btn_load = mkbtn(self, t("rec_btn_load"),
                               self._load_in_main,
                               color="#1a5c38", fg=FG)
        self._btn_load.pack(pady=(6, 16), padx=20, fill="x")
        self._btn_load.config(state="disabled")

    # ── Backend Windows ──────────────────────────────────────

    def _on_backend_change(self):
        if not IS_WINDOWS:
            return
        if self._backend.get() == "wasapi":
            self._dshow_frame.pack_forget()
            self._dev_hint.pack_forget()
            self._wasapi_info.pack(padx=20, anchor="w")
        else:
            self._wasapi_info.pack_forget()
            self._dshow_frame.pack(padx=20, fill="x", pady=(0, 2))
            self._dev_hint.pack(padx=20, anchor="w", pady=(0, 2))

    def _enum_dshow(self):
        """Énumère les périphériques DirectShow en arrière-plan."""
        ffmpeg = self._parent._ffmpeg()
        if not os.path.isfile(ffmpeg):
            return
        try:
            out = subprocess.run(
                [ffmpeg, "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                creationflags=NO_WINDOW, timeout=8,
            ).stderr
        except Exception:
            return

        devices, in_audio = [], False
        for line in out.splitlines():
            if "DirectShow audio devices" in line:
                in_audio = True; continue
            if "DirectShow video devices" in line and in_audio:
                break
            if in_audio:
                m = re.search(r'"([^"]+)"\s*\(audio\)', line)
                if m:
                    devices.append(m.group(1))

        if devices:
            preferred = [d for d in devices if "realtek" in d.lower()]
            others    = [d for d in devices if "realtek" not in d.lower()]
            self.after(0, self._update_dev_cb, preferred + others)

    def _update_dev_cb(self, devices: list[str]):
        if not hasattr(self, "_dev_cb"):
            return
        self._dev_cb.config(values=devices, state="normal")
        if devices:
            self._dev_var.set(devices[0])
            hint = devices[0]
            if "realtek" in hint.lower():
                hint = f"{t('rec_realtek')}{hint}"
            self._dev_hint.config(text=hint)

    # ── Enregistrement ───────────────────────────────────────

    def _toggle(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        ffmpeg = self._parent._ffmpeg()
        if not os.path.isfile(ffmpeg):
            ext = ".exe" if IS_WINDOWS else ""
            messagebox.showerror(
                t("rec_ffmpeg_missing"),
                f"build/ffmpeg/bin/ffmpeg{ext} introuvable.", parent=self)
            return

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._tmp_file = os.path.join(
            tempfile.gettempdir(), f"transcribe_rec_{ts}.mp3")

        base_out = ["-ar", "44100", "-ac", "1",
                    "-codec:a", "libmp3lame", "-q:a", "4",
                    self._tmp_file]

        if IS_WINDOWS:
            if self._backend.get() == "wasapi":
                cmd = [ffmpeg, "-y", "-f", "wasapi",
                       "-i", "default"] + base_out
            else:
                dev = self._dev_var.get().strip()
                if not dev:
                    messagebox.showwarning(
                        t("rec_no_device_title"),
                        t("rec_no_device_msg"),
                        parent=self)
                    return
                cmd = [ffmpeg, "-y", "-f", "dshow",
                       "-i", f"audio={dev}"] + base_out
        else:
            cmd = [ffmpeg, "-y", "-f", "pulse",
                   "-i", "default"] + base_out

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=NO_WINDOW,
            )
        except FileNotFoundError as e:
            messagebox.showerror("Erreur", str(e), parent=self)
            return

        self._running = True
        self._elapsed = 0
        self._btn_rec.config(text=t("rec_btn_stop"),
                             bg=WARN, activebackground=_adj(WARN, 28))
        self._status_var.set(t("rec_running"))
        self._dot.config(fg=DANGER)
        for b in (self._btn_save, self._btn_tx, self._btn_load):
            b.config(state="disabled")
        self._tick()
        self._animate()
        threading.Thread(target=self._watch, daemon=True).start()

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.write(b"q")
                self._proc.stdin.flush()
            except Exception:
                self._proc.terminate()
            self._proc.wait()
        self._running = False
        if self._timer_id:
            self.after_cancel(self._timer_id)
        self._btn_rec.config(text=t("rec_btn_start"),
                             bg=DANGER, activebackground=_adj(DANGER, 28))
        self._dot.config(fg=BG4)
        self._level_canvas.delete("all")
        self._on_stopped()

    def _watch(self):
        """Détecte si ffmpeg s'arrête inopinément."""
        if self._proc:
            self._proc.wait()
        if self._running:
            self.after(0, self._stop)

    def _tick(self):
        if not self._running:
            return
        self._elapsed += 1
        m, s = divmod(self._elapsed, 60)
        self._timer_var.set(f"{m:02d}:{s:02d}")
        self._timer_id = self.after(1000, self._tick)

    def _animate(self):
        if not self._running:
            return
        import math
        c = self._level_canvas
        c.delete("all")
        w = c.winfo_width() or 460
        nb = 28
        bw = max(4, w // nb - 2)
        for i in range(nb):
            amp = 0.3 + 0.7 * abs(
                math.sin(self._level_phase * 0.18 + i * 0.45))
            h_bar = int(amp * 14) + 2
            x = i * (bw + 2) + 4
            col = DANGER if amp > 0.8 else (WARN if amp > 0.5 else GREEN)
            c.create_rectangle(x, 16 - h_bar, x + bw, 16,
                                fill=col, outline="")
        self._level_phase += 1
        self.after(80, self._animate)

    def _on_stopped(self):
        size_kb = 0
        if self._tmp_file and os.path.isfile(self._tmp_file):
            size_kb = os.path.getsize(self._tmp_file) // 1024
        self._status_var.set(
            f"{t('rec_done')}{size_kb}{t('rec_done_unit')}")
        for b in (self._btn_save, self._btn_tx, self._btn_load):
            b.config(state="normal")

    # ── Actions post-enregistrement ──────────────────────────

    def _save(self):
        if not self._tmp_file or not os.path.isfile(self._tmp_file):
            return
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = filedialog.asksaveasfilename(
            parent=self,
            title=t("rec_save_title"),
            initialdir=self._parent.root_dir,
            initialfile=f"{t('rec_save_default')}{ts}.mp3",
            defaultextension=".mp3",
            filetypes=[(t("filter_mp3"), "*.mp3"), (t("filter_all"), "*.*")],
        )
        if not dst:
            return
        shutil.copy2(self._tmp_file, dst)
        self._status_var.set(t('rec_saved') + os.path.basename(dst))
        self._parent.video_path.set(dst)
        self._parent._log_line(f"💾 Sauvegardé : {dst}")

    def _transcribe(self):
        """
        Sauvegarde le MP3 (hors /tmp), puis lance audio2en dessus.
        -l <lang> est passé à Whisper pour la langue source.
        """
        if not self._tmp_file or not os.path.isfile(self._tmp_file):
            return
        lang = lang_code(self._rec_lang.get())
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst  = filedialog.asksaveasfilename(
            parent=self,
            title=t("rec_tx_title"),
            initialdir=self._parent.root_dir,
            initialfile=f"{t('rec_save_default')}{ts}.mp3",
            defaultextension=".mp3",
            filetypes=[(t("filter_mp3"), "*.mp3"), (t("filter_all"), "*.*")],
        )
        if not dst:
            return
        try:
            shutil.copy2(self._tmp_file, dst)
        except OSError as e:
            messagebox.showerror(t("rec_copy_err"), str(e), parent=self)
            return
        self._parent.video_path.set(dst)
        self._parent._log_line(f"📂 Transcription [{lang}] : {dst}")
        self.destroy()
        cmd = self._parent._script("audio2en") + [
            dst, self._parent._model(), lang]
        self._parent._run_cmd(
            cmd, t("rec_tx_label", lang=lang))

    def _load_in_main(self):
        if not self._tmp_file or not os.path.isfile(self._tmp_file):
            return
        self._parent.video_path.set(self._tmp_file)
        self._parent._log_line(f"📂 Chargé : {self._tmp_file}")
        self._status_var.set(t("rec_loaded"))
        self.destroy()

    # ── Fermeture ────────────────────────────────────────────

    def _on_close(self):
        if self._running:
            if not messagebox.askyesno(
                    t("rec_close_title"),
                    t("rec_close_msg"),
                    parent=self):
                return
            self._stop()
        if self._tmp_file and os.path.isfile(self._tmp_file):
            try:
                os.remove(self._tmp_file)
            except OSError:
                pass
        self.destroy()
