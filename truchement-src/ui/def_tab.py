"""
ui/def_tab.py — Onglet Définition + popup DefinitionPopup
===========================================================
Contient :
  • DefinitionPopup   : fenêtre modale affichant lookup_lemma()
  • DefTabMixin       : méthodes de l'onglet recherche FTS5

DefTabMixin est mélangé dans TranslatorApp.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from config import C, F, LANG_NAMES
from dictionary import (
    available_dics, fetch_entry, lookup_lemma,
    search_exact, search_fts, search_like_prefix,
)
from html_renderer import is_html, render_html, setup_html_tags


# ═══════════════════════════════════════════════════════════════════════════════
# POPUP DÉFINITION
# ═══════════════════════════════════════════════════════════════════════════════

class DefinitionPopup(tk.Toplevel):
    """
    Fenêtre modale affichant les résultats d'un lookup_lemma().
    Plusieurs définitions sont séparées par une ligne horizontale.
    """

    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        word: str,
        rows: list,
        dic_label: str,
        t: dict,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.minsize(460, 320)
        self.geometry("640x480")
        self.transient(parent)
        self.bind("<Map>", self._on_map)

        # En-tête
        hdr = tk.Frame(self, bg=C["panel"])
        hdr.pack(fill="x")
        tk.Label(hdr, text=word, bg=C["panel"], fg=C["accent"],
                 font=F["title"], anchor="w").pack(side="left", padx=16, pady=10)
        tk.Label(hdr, text=dic_label, bg=C["panel"], fg=C["muted"],
                 font=F["small"]).pack(side="right", padx=16, pady=10)
        ttk.Separator(self).pack(fill="x")

        # Zone de résultats
        frame = tk.Frame(self, bg=C["card"],
                         highlightbackground=C["border"], highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=16, pady=14)

        vscroll = ttk.Scrollbar(frame, orient="vertical")
        vscroll.pack(side="right", fill="y")
        txt = tk.Text(
            frame, wrap="word", bg=C["card"], fg=C["text"],
            font=F["body"], relief="flat", padx=12, pady=10,
            selectbackground=C["accent"],
            yscrollcommand=vscroll.set, state="normal",
        )
        vscroll.config(command=txt.yview)
        txt.pack(fill="both", expand=True)

        txt.tag_configure("lemma",  foreground=C["teal"],   font=(*F["head"],))
        txt.tag_configure("number", foreground=C["accent"],  font=F["small"])
        txt.tag_configure("sep",    foreground=C["border"])
        setup_html_tags(txt)

        for i, row in enumerate(rows):
            try:
                lemma_val = row[0]
                defn_val  = row[1] if len(row) > 1 else ""
            except (TypeError, KeyError):
                ks = list(row.keys())
                lemma_val = row[ks[0]] if ks else ""
                defn_val  = row[ks[1]] if len(ks) > 1 else ""
            lemma_val = str(lemma_val or word)
            defn_val  = str(defn_val  or "")

            if i > 0:
                txt.insert("end", "\n" + "\u2500" * 64 + "\n", "sep")
            if len(rows) > 1:
                txt.insert("end", f"[{i + 1}]  ", "number")
            txt.insert("end", f"{lemma_val}\n", "lemma")
            defn_str = defn_val or "\u2014"
            if is_html(defn_str):
                render_html(txt, defn_str)
                if txt.get("end-2c", "end-1c") != "\n":
                    txt.insert("end", "\n")
            else:
                txt.insert("end", defn_str + "\n")

        if not rows:
            txt.insert(
                "end",
                t.get("define_not_found", "No definition.").format(word=word),
            )

        txt.configure(state="disabled")

        # Pied de page
        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(fill="x", pady=(0, 12))
        ttk.Button(
            bf, text=t.get("def_close", "✕  Close"),
            style="Ghost.TButton", command=self.destroy,
        ).pack(side="right", padx=16)

        # Centrage
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    def _on_map(self, _event=None) -> None:
        self.unbind("<Map>")
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()


# ═══════════════════════════════════════════════════════════════════════════════
# MIXIN ONGLET DÉFINITION
# ═══════════════════════════════════════════════════════════════════════════════

class DefTabMixin:

    # ── Construction ──────────────────────────────────────────────────────────

    def build_def_tab(self, parent: ttk.Frame) -> None:
        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True, padx=24, pady=18)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        # Titre
        self._def_lbl_title = ttk.Label(
            outer, text="", font=F["title"],
            foreground=C["text"], background=C["bg"],
        )
        self._def_lbl_title.grid(row=0, column=0, sticky="w", pady=(0, 16))

        # Sélection du dictionnaire
        lang_row = ttk.Frame(outer)
        lang_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self._def_lbl_lang = ttk.Label(lang_row, text="", style="Mu.TLabel")
        self._def_lbl_lang.pack(side="left", padx=(0, 8))

        dics     = available_dics()
        dic_opts = self._dic_opts(dics)
        self._def_cb_lang = ttk.Combobox(
            lang_row, values=dic_opts, state="readonly",
            width=38, font=F["body"],
        )
        if dic_opts:
            self._def_cb_lang.current(0)
        self._def_cb_lang.pack(side="left")
        self._def_cb_lang.bind(
            "<<ComboboxSelected>>", lambda _: self._def_show_hint(),
        )

        self._def_refresh_btn = ttk.Button(
            lang_row, text="", style="Ghost.TButton",
            width=3, command=self._def_refresh_dics,
        )
        self._def_refresh_btn.pack(side="left", padx=(6, 0))

        self._def_no_dic_lbl = ttk.Label(
            lang_row, text="", style="Mu.TLabel", foreground=C["muted"],
        )
        self._def_no_dic_lbl.pack(side="left", padx=(10, 0))

        # Ligne de recherche
        search_row = ttk.Frame(outer)
        search_row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        search_row.columnconfigure(0, weight=1)

        entry_frame = tk.Frame(
            search_row, bg=C["card"],
            highlightbackground=C["border"], highlightthickness=1,
        )
        entry_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self._def_entry = tk.Entry(
            entry_frame, bg=C["card"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=F["body"], bd=8, selectbackground=C["accent"],
        )
        self._def_entry.pack(fill="x", expand=True)
        self._def_entry.bind("<Return>",   lambda _: self._def_run("fts"))
        self._def_entry.bind("<KP_Enter>", lambda _: self._def_run("fts"))

        self._def_search_btn = ttk.Button(
            search_row, text="", style="Search.TButton",
            command=lambda: self._def_run("fts"),
        )
        self._def_search_btn.grid(row=0, column=1, padx=(0, 4))

        self._def_prefix_btn = ttk.Button(
            search_row, text="", style="Acc.TButton",
            command=lambda: self._def_run("prefix"),
        )
        self._def_prefix_btn.grid(row=0, column=2, padx=(0, 4))

        self._def_exact_btn = ttk.Button(
            search_row, text="", style="Swap.TButton",
            command=lambda: self._def_run("exact"),
        )
        self._def_exact_btn.grid(row=0, column=3)

        # En-tête résultats
        self._def_results_hdr = ttk.Label(outer, text="", style="Mu.TLabel")
        self._def_results_hdr.grid(row=3, column=0, sticky="w", pady=(0, 4))

        # Zone de résultats
        res_frame = tk.Frame(
            outer, bg=C["card"],
            highlightbackground=C["border"], highlightthickness=1,
        )
        res_frame.grid(row=4, column=0, sticky="nsew")

        vscroll = ttk.Scrollbar(res_frame, orient="vertical")
        vscroll.pack(side="right", fill="y")
        hscroll = ttk.Scrollbar(res_frame, orient="horizontal")
        hscroll.pack(side="bottom", fill="x")

        self._def_txt = tk.Text(
            res_frame, wrap="none", bg=C["card"], fg=C["text"],
            font=F["body"], relief="flat", padx=12, pady=10,
            selectbackground=C["accent"], state="disabled",
            yscrollcommand=vscroll.set, xscrollcommand=hscroll.set,
        )
        vscroll.config(command=self._def_txt.yview)
        hscroll.config(command=self._def_txt.xview)
        self._def_txt.pack(fill="both", expand=True)

        self._def_txt.tag_configure("lemma",  foreground=C["teal"],
                                    font=(*F["head"],))
        self._def_txt.tag_configure("number", foreground=C["accent"],
                                    font=F["small"])
        self._def_txt.tag_configure("sep",    foreground=C["border"])
        self._def_txt.tag_configure("hint",   foreground=C["muted"],
                                    font=F["small"])
        self._def_txt.tag_configure("error",  foreground=C["swap"])
        setup_html_tags(self._def_txt)

        self._def_show_hint()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _dic_opts(codes: list[str]) -> list[str]:
        return [f"{LANG_NAMES.get(c, c)}  [{c}-{c}.db]" for c in codes]

    def _def_refresh_dics(self) -> None:
        dics = available_dics()
        opts = self._dic_opts(dics)
        self._def_cb_lang.configure(values=opts)
        if opts:
            self._def_cb_lang.current(0)
            self._def_no_dic_lbl.configure(text="")
        else:
            self._def_cb_lang.set("")
            self._def_no_dic_lbl.configure(
                text=f"build/dic/*.db — "
                     f"{self._t.get('def_no_dic_tab', '').split(chr(10))[0]}"
            )
        self._def_show_hint()

    def _def_lang_code(self) -> str | None:
        val = self._def_cb_lang.get()
        if not val:
            return None
        m = re.search(r'\[([a-z]{2})-[a-z]{2}\.db\]', val)
        return m.group(1) if m else None

    def _def_show_hint(self) -> None:
        self._def_results_hdr.configure(text="")
        self._def_txt.configure(state="normal")
        self._def_txt.delete("1.0", "end")
        self._def_txt.insert(
            "1.0",
            self._t.get("def_hint", "Type a word and press Enter."),
            "hint",
        )
        self._def_txt.configure(state="disabled")

    # ── Recherche ─────────────────────────────────────────────────────────────

    def _def_run(self, mode: str) -> None:
        """
        Lance la recherche selon *mode* :
          'fts'    → Contenant  (FTS5 MATCH)
          'prefix' → Commençant (LIKE 'query%')
          'exact'  → Définition (= lemme exact)
        """
        query = self._def_entry.get().strip()
        if not query:
            return
        lc_ = self._def_lang_code()
        if not lc_:
            lang_name = "?"
            msg = self._t.get("def_no_dic_tab", "No dictionary.").format(
                lang=lang_name, code="?",
            )
            self._def_results_hdr.configure(text=msg)
            self._def_txt.configure(state="normal")
            self._def_txt.delete("1.0", "end")
            self._def_txt.insert("1.0", msg, "error")
            self._def_txt.configure(state="disabled")
            return

        self._def_set_busy()

        def run() -> None:
            try:
                if mode == "prefix":
                    rows = search_like_prefix(lc_, query)
                elif mode == "exact":
                    rows = search_exact(lc_, query)
                else:
                    rows = search_fts(lc_, query)
                self.after(0, lambda r=rows: self._def_show_results(query, lc_, r, None))
            except FileNotFoundError:
                lang_name = LANG_NAMES.get(lc_, lc_)
                msg = self._t.get("def_no_dic_tab", "No dictionary.").format(
                    lang=lang_name, code=lc_,
                )
                self.after(0, lambda m=msg: self._def_show_results(query, lc_, [], m))
            except RuntimeError as exc:
                msg = self._t.get("def_db_error", "Database error:\n{err}").format(
                    err=exc,
                )
                self.after(0, lambda m=msg: self._def_show_results(query, lc_, [], m))

        threading.Thread(target=run, daemon=True).start()

    def _def_set_busy(self) -> None:
        searching = self._t.get("def_searching", "…")
        self._def_search_btn.configure(state="disabled", text=searching)
        self._def_prefix_btn.configure(state="disabled")
        self._def_exact_btn.configure(state="disabled")
        self._def_results_hdr.configure(text=searching)

    def _def_clear_busy(self) -> None:
        t = self._t
        self._def_search_btn.configure(
            state="normal", text=t.get("def_search_btn", "Containing"),
        )
        self._def_prefix_btn.configure(
            state="normal", text=t.get("def_btn_prefix", "Starting with"),
        )
        self._def_exact_btn.configure(
            state="normal", text=t.get("def_btn_exact", "Definition"),
        )

    def _def_show_results(
        self, query: str, lc_: str,
        rows: list, err: str | None,
    ) -> None:
        t = self._t
        self._def_clear_busy()
        w = self._def_txt
        w.configure(state="normal")
        w.delete("1.0", "end")
        for tag in w.tag_names():
            if tag.startswith("lemma_"):
                w.tag_delete(tag)

        if err:
            self._def_results_hdr.configure(text=err)
            w.insert("1.0", err, "error")
        elif not rows:
            msg = t.get("def_no_results", "No results.").format(word=query)
            self._def_results_hdr.configure(text=msg)
            w.insert("1.0", msg, "hint")
        else:
            hdr = t.get("def_results_n", "{n} result(s)").format(
                n=len(rows), word=query,
            )
            self._def_results_hdr.configure(text=hdr)
            for i, row in enumerate(rows):
                try:
                    lemma = str(row[0] or "?")
                    defn  = str(row[1]) if len(row) > 1 else ""
                except (TypeError, KeyError):
                    ks    = list(row.keys())
                    lemma = str(row[ks[0]]) if ks else "?"
                    defn  = str(row[ks[1]]) if len(ks) > 1 else ""

                if i > 0:
                    w.insert("end", "\n" + "\u2500" * 72 + "\n", "sep")
                if len(rows) > 1:
                    w.insert("end", f"[{i + 1}]  ", "number")

                tag_id = f"lemma_{i}"
                w.insert("end", f"{lemma}\n", ("lemma", tag_id))
                w.tag_configure(
                    tag_id, foreground=C["teal"],
                    font=(*F["head"],), underline=True,
                )
                w.tag_bind(tag_id, "<Enter>",
                           lambda e: self._def_txt.configure(cursor="hand2"))
                w.tag_bind(tag_id, "<Leave>",
                           lambda e: self._def_txt.configure(cursor=""))
                w.tag_bind(
                    tag_id, "<Button-1>",
                    lambda e, lm=lemma, df=defn, lc=lc_:
                        self._def_open_entry_data(lm, df, lc),
                )

                defn_str = defn or "\u2014"
                if is_html(defn_str):
                    render_html(w, defn_str)
                    if w.get("end-2c", "end-1c") != "\n":
                        w.insert("end", "\n")
                else:
                    w.insert("end", defn_str + "\n")

        w.configure(state="disabled")
        w.see("1.0")

    # ── Ouverture d'une fiche ─────────────────────────────────────────────────

    def _def_open_entry(self, lemma: str, lc_: str) -> None:
        t = self._t
        lang_name = LANG_NAMES.get(lc_, lc_)
        try:
            rows = fetch_entry(lc_, lemma)
        except FileNotFoundError:
            messagebox.showinfo(
                t.get("define_title", "Definition"),
                t.get("define_no_dic", "No dictionary.").format(
                    lang=lang_name, code=lc_,
                ),
            )
            return
        except RuntimeError as exc:
            messagebox.showerror(
                t.get("error_title", "Error"),
                t.get("define_error", "Dictionary error:\n{err}").format(err=exc),
            )
            return
        dic_label = t.get("define_from", "Dictionary: {lang}").format(lang=lang_name)
        self.after_idle(lambda: DefinitionPopup(
            self, title=t.get("define_title", "Definition"),
            word=lemma, rows=rows, dic_label=dic_label, t=t,
        ))

    def _def_open_entry_data(self, lemma: str, defn: str, lc_: str) -> None:
        """Ouvre la popup avec les données déjà chargées (évite re-requête)."""
        t = self._t
        lang_name = LANG_NAMES.get(lc_, lc_)
        dic_label = t.get("define_from", "Dictionary: {lang}").format(lang=lang_name)
        self.after_idle(lambda: DefinitionPopup(
            self, title=t.get("define_title", "Definition"),
            word=lemma, rows=[(lemma, defn)],
            dic_label=dic_label, t=t,
        ))

    # ── Définition contextuelle (panneaux de traduction) ──────────────────────

    def _define_selected(self, idx: int, side: str) -> None:
        from config import lang_code
        t    = self._t
        word = self._get_selected_word(idx, side)
        if not word:
            self.lbl_status.configure(text=t.get("define_select", "Select a word first."))
            self.after(3000, lambda: self.lbl_status.configure(text=""))
            return

        lc_       = lang_code(self.cb_src.get() if side == "src" else self.cb_tgt.get())
        lang_name = LANG_NAMES.get(lc_, lc_)

        try:
            rows = lookup_lemma(lc_, word)
        except FileNotFoundError:
            messagebox.showinfo(
                t.get("define_title", "Definition"),
                t.get("define_no_dic", "No dictionary.").format(
                    lang=lang_name, code=lc_,
                ),
            )
            return
        except RuntimeError as exc:
            messagebox.showerror(
                t.get("error_title", "Error"),
                t.get("define_error", "Dictionary error:\n{err}").format(err=exc),
            )
            return

        if not rows:
            messagebox.showinfo(
                t.get("define_title", "Definition"),
                t.get("define_not_found", "No definition found.").format(word=word),
            )
            return

        dic_label = t.get("define_from", "Dictionary: {lang}").format(lang=lang_name)
        self.after_idle(lambda: DefinitionPopup(
            self, title=t.get("define_title", "Definition"),
            word=word, rows=rows, dic_label=dic_label, t=t,
        ))
