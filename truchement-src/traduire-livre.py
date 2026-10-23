#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
traduire-livre.py — Traduction de qualité d'un livre via un serveur llama.cpp local
====================================================================================

Usage :
    python traduire-livre.py LIVRE.epub|LIVRE.pdf|LIVRE.txt
        [--src en] [--tgt fr] [--url http://127.0.0.1:8080/v1]
        [--model NOM] [--passes 1|2|3] [--max-chars 2500]
        [--glossary FICHIER] [--format auto|chat|translategemma]
        [--limit N] [--fresh] [-o SORTIE]

Lancé par l'onglet « Livre » de truchement (avec le Python portable de la clé),
ou à la main. Dépendances : requests, beautifulsoup4 + lxml, PyMuPDF (pour les
PDF) — toutes présentes dans requirements.txt.

PRINCIPE
────────
1. Découpe : le livre est analysé en SEGMENTS (un par paragraphe, titre,
   élément de liste, cellule…), puis les segments consécutifs d'un même
   chapitre sont regroupés en UNITÉS d'au plus --max-chars caractères.
   Traduire plusieurs paragraphes ensemble donne au modèle le contexte
   (dialogues, pronoms, ton) qu'un paragraphe isolé n'a pas. La taille est
   plafonnée automatiquement d'après le contexte réel du serveur (/props).

2. Passes, pour chaque unité :
     1 = traduction ;
     2 = révision bilingue (original + traduction → traduction corrigée) ;
     3 = relecture finale (fluidité, cohérence des termes), toujours bilingue.
   Une révision dont la sortie est invalide (balises perdues, longueur
   aberrante) est rejetée : on garde la passe précédente.

3. Mise en forme (EPUB) : la mise en forme interne des paragraphes
   (italique, gras, appels de note, liens, ancres de page…) est remplacée
   par des balises neutres <g1>…</g1>, <x2/> que le modèle doit conserver ;
   les balises d'origine sont ensuite restaurées autour du texte traduit.
   Si le modèle les abîme : nouvel essai paragraphe par paragraphe, puis en
   dernier recours texte brut (compté dans le bilan).

4. Reprise : chaque résultat est ajouté au cache <sortie>.cache.jsonl dès
   qu'il est obtenu. Une interruption (bouton Arrêter, coupure, plantage du
   serveur) ne perd rien : relancer reprend là où on en était.

5. Reconstitution : EPUB → EPUB (structure, styles, images, table des
   matières et langue déclarée mises à jour) ; PDF → Markdown (titres
   détectés à la taille de police, en-têtes/pieds de page répétés et
   numéros de page supprimés, paragraphes recollés par-dessus les sauts de
   page, césures retirées) ; TXT → TXT.

SORTIE
──────
Lignes de journal lisibles sur stdout (+ copie horodatée dans <sortie>.log),
et lignes « @@{json} » de progression destinées à l'interface :
    @@{"ev":"plan","units":N,"chars":C,"segments":S,"cached":K}
    @@{"ev":"progress","done":i,"units":N,"done_chars":c,"chars":C,"eta":s}
    @@{"ev":"end","out":"…","stats":{…}}
    @@{"ev":"error","msg":"…"}
    @@{"ev":"paused","done":i,"units":N,"pct":p,"partial":"…"}
Code de retour : 0 succès, 2 serveur injoignable / argument, 3 échec en
cours de traduction, 4 livre déjà en cours ailleurs, 10 en pause,
130 interruption (SIGTERM, arrêt du système).

PAUSE ET REPRISE (même des jours plus tard, après redémarrage)
───────────────────────────────────────────────────────────────
Créer <livre>.<cible>.pause demande une pause propre : le script finit
l'unité en cours, écrit un aperçu <sortie>.partiel.<ext>, note l'état dans
<livre>.<cible>.job.json et sort (code 10). Relancer la même commande
reprend : chaque segment déjà traduit est relu du cache, quel que soit le
nouveau découpage (taille des blocs, contexte du serveur, modèle).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import html.entities
import json
import os
import posixpath
import re
import signal
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

try:  # Windows : stdout en cp1252 par défaut quand il est redirigé
    sys.stdout.reconfigure(encoding="utf-8", errors="replace",
                           line_buffering=True)
except Exception:
    pass


DEFAULT_URL = "http://127.0.0.1:8080/v1"
DEFAULT_MAX_CHARS = 2500
MAX_SEGS_PER_UNIT = 30

LANGS = {
    "ar": "Arabic", "az": "Azerbaijani", "bg": "Bulgarian", "bn": "Bengali",
    "ca": "Catalan", "cs": "Czech", "da": "Danish", "de": "German",
    "el": "Greek", "en": "English", "eo": "Esperanto", "es": "Spanish",
    "et": "Estonian", "eu": "Basque", "fa": "Persian", "fi": "Finnish",
    "fr": "French", "ga": "Irish", "gl": "Galician", "he": "Hebrew",
    "hi": "Hindi", "hu": "Hungarian", "id": "Indonesian", "it": "Italian",
    "ja": "Japanese", "ko": "Korean", "la": "Latin", "lt": "Lithuanian",
    "lv": "Latvian", "ms": "Malay", "nb": "Norwegian Bokmål",
    "nl": "Dutch", "pl": "Polish", "pt": "Portuguese", "ro": "Romanian",
    "ru": "Russian", "sk": "Slovak", "sl": "Slovenian", "sq": "Albanian",
    "sv": "Swedish", "th": "Thai", "tl": "Tagalog", "tr": "Turkish",
    "uk": "Ukrainian", "ur": "Urdu", "vi": "Vietnamese", "zh": "Chinese",
    "zt": "Traditional Chinese",
}


def lang_name(code: str) -> str:
    return LANGS.get(code, code)


# ═══════════════════════════════════════════════════════════════════════════════
# JOURNAL ET ÉVÉNEMENTS
# ═══════════════════════════════════════════════════════════════════════════════

_LOGFILE = None


def log(msg: str) -> None:
    print(msg, flush=True)
    if _LOGFILE is not None:
        try:
            _LOGFILE.write(time.strftime("%Y-%m-%d %H:%M:%S  ") + msg + "\n")
            _LOGFILE.flush()
        except OSError:
            pass


def event(kind: str, **data) -> None:
    data = {"ev": kind, **data}
    print("@@" + json.dumps(data, ensure_ascii=False), flush=True)


def fmt_duration(sec: float) -> str:
    sec = int(max(0, sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d}"
    if m:
        return f"{m} min {s:02d}"
    return f"{s} s"


class Stats:
    def __init__(self) -> None:
        self.calls = 0
        self.cached = 0
        self.group_fallbacks = 0
        self.format_simplified = 0
        self.revisions_rejected = 0
        self.split_long = 0
        self.suspicious = 0
        self.untranslated = 0
        self.tags_rescued = 0

    def as_dict(self) -> dict:
        return dict(self.__dict__)


STATS = Stats()


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE DE REPRISE (JSONL en ajout seul)
# ═══════════════════════════════════════════════════════════════════════════════

class Cache:
    """
    Un résultat par ligne : {"k": clé, "p": passe, "v": texte}. L'ajout
    seul (au lieu de réécrire tout un JSON à chaque bloc) garde un coût
    constant même sur un très gros livre ; une dernière ligne tronquée par
    une coupure est simplement ignorée au rechargement.
    """

    def __init__(self, path: Path, fresh: bool = False) -> None:
        self.path = path
        self.data: dict[tuple[str, int], str] = {}
        if fresh and path.exists():
            path.unlink()
        if path.exists():
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                        self.data[(rec["k"], int(rec["p"]))] = rec["v"]
                    except (ValueError, KeyError, TypeError):
                        continue
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8")
        self._last_sync = time.monotonic()

    def get(self, key: str, p: int) -> str | None:
        return self.data.get((key, p))

    def put(self, key: str, p: int, value: str) -> None:
        self.data[(key, p)] = value
        self._fh.write(json.dumps({"k": key, "p": p, "v": value},
                                  ensure_ascii=False) + "\n")
        self._fh.flush()
        # flush() ne fait que passer au système : sans fsync, une coupure
        # de courant ou un arrêt brutal peut perdre les dernières minutes.
        if time.monotonic() - self._last_sync > 20:
            self.sync()

    def sync(self) -> None:
        try:
            self._fh.flush()
            os.fsync(self._fh.fileno())
        except (OSError, ValueError):
            pass
        self._last_sync = time.monotonic()

    def close(self) -> None:
        self.sync()
        try:
            self._fh.close()
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT llama.cpp
# ═══════════════════════════════════════════════════════════════════════════════

class ServerError(RuntimeError):
    pass


class LlamaClient:
    """
    Deux modes d'appel :
      • « chat » : /v1/chat/completions, consigne + texte dans un seul
        message utilisateur (pas de rôle system : certains gabarits, dont
        ceux de Gemma, le gèrent mal) ;
      • « translategemma » : /completion avec le gabarit de TranslateGemma
        reproduit à la main. Ce modèle est entraîné sur une consigne
        précise ; passée par l'API chat, la structure qu'attend son gabarit
        Jinja (source_lang_code…) n'arrive pas jusqu'à lui. Les passes de
        révision utilisent le même tour de parole Gemma, avec notre consigne.
    """

    def __init__(self, url: str, model: str, fmt: str) -> None:
        import requests
        self._requests = requests
        root = url.strip().rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        self.root = root
        self.model = model.strip()
        self.fmt = fmt
        self.n_ctx = 8192
        self.model_path = ""
        self.session = requests.Session()
        # Serveur local / réseau local : ne pas passer par un éventuel proxy
        # déclaré dans l'environnement (HTTP_PROXY…).
        self.session.trust_env = False

    # ── Sondage ──────────────────────────────────────────────────────────────

    def probe(self, wait_loading: int = 180) -> None:
        deadline = time.monotonic() + wait_loading
        announced = False
        while True:
            try:
                r = self.session.get(self.root + "/health", timeout=5)
            except self._requests.ConnectionError:
                raise ServerError(f"serveur injoignable à {self.root} "
                                  f"(connexion refusée ou adresse inconnue)")
            except Exception as exc:
                raise ServerError(f"serveur injoignable ({self.root}) : {exc}")
            if r.status_code == 503 and time.monotonic() < deadline:
                if not announced:
                    log("Le serveur charge encore le modèle, attente…")
                    announced = True
                time.sleep(3)
                continue
            if r.status_code >= 400:
                raise ServerError(f"/health a répondu {r.status_code}")
            break

        template = ""
        try:
            r = self.session.get(self.root + "/props", timeout=5)
            if r.ok:
                props = r.json()
                gen = props.get("default_generation_settings") or {}
                n_ctx = gen.get("n_ctx") or props.get("n_ctx")
                if isinstance(n_ctx, int) and n_ctx > 0:
                    self.n_ctx = n_ctx
                template = props.get("chat_template") or ""
                self.model_path = props.get("model_path") or ""
        except Exception:
            pass

        if self.fmt == "auto":
            hint = (self.model + " " + self.model_path).lower()
            if "source_lang_code" in template or "translategemma" in hint:
                self.fmt = "translategemma"
            else:
                self.fmt = "chat"

    # ── Appels ───────────────────────────────────────────────────────────────

    def _post(self, path: str, payload: dict) -> dict:
        last = None
        for attempt in range(1, 4):
            try:
                r = self.session.post(self.root + path, json=payload,
                                      timeout=(15, 1800))
                if r.status_code >= 400:
                    raise ServerError(
                        f"HTTP {r.status_code} : {r.text[:300].strip()}")
                return r.json()
            except Exception as exc:
                last = exc
                log(f"  ⚠ appel au serveur échoué ({attempt}/3) : {exc}")
                if attempt < 3:
                    time.sleep(5 * attempt)
        raise ServerError(f"le serveur ne répond plus : {last}")

    def max_tokens_for(self, prompt: str, text: str) -> int:
        want = int(len(text) * 0.7) + 256
        room = self.n_ctx - int(len(prompt) * 0.45) - 64
        return max(256, min(want, room))

    def chat(self, prompt: str, text: str, temperature: float) -> tuple[str, bool]:
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "top_p": 0.95,
            "max_tokens": self.max_tokens_for(prompt, text),
            "stream": False,
            "cache_prompt": True,
        }
        if self.model:
            payload["model"] = self.model
        data = self._post("/v1/chat/completions", payload)
        STATS.calls += 1
        try:
            choice = data["choices"][0]
            out = choice["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise ServerError(f"réponse inattendue : {str(data)[:200]}")
        return out, choice.get("finish_reason") == "length"

    def gemma_raw(self, user_text: str, text: str,
                  temperature: float) -> tuple[str, bool]:
        prompt = ("<start_of_turn>user\n" + user_text
                  + "<end_of_turn>\n<start_of_turn>model\n")
        payload = {
            "prompt": prompt,
            "n_predict": self.max_tokens_for(prompt, text),
            "temperature": temperature,
            "top_p": 0.95,
            "stop": ["<end_of_turn>", "<start_of_turn>"],
            "cache_prompt": True,
        }
        data = self._post("/completion", payload)
        STATS.calls += 1
        out = data.get("content", "")
        truncated = (data.get("stop_type") == "limit"
                     or bool(data.get("stopped_limit")))
        return out, truncated


# ═══════════════════════════════════════════════════════════════════════════════
# CONSIGNES
# ═══════════════════════════════════════════════════════════════════════════════

TAG_RULE = (
    "The text contains markup tags such as <seg n=\"1\">…</seg>, <g1>…</g1> "
    "or <x1/>. Keep every tag exactly as written: one <seg> per original "
    "<seg> with the same number, and each <gN>…</gN> pair around the words "
    "that translate the words it surrounded. Never add, drop or renumber "
    "tags."
)


def has_markup(text: str) -> bool:
    return bool(re.search(r"<(?:seg n=|g\d+>|x\d+/>)", text))


def glossary_block(glossary: list[tuple[str, str]], text: str, tgt: str) -> str:
    lower = text.lower()
    hits = [(a, b) for a, b in glossary if a.lower() in lower]
    if not hits:
        return ""
    lines = "\n".join(f"- {a} → {b}" for a, b in hits)
    return (f"Use these {lang_name(tgt)} terms (glossary):\n{lines}\n\n")


def prompt_translate(src: str, tgt: str, text: str, glossary) -> str:
    S, T = lang_name(src), lang_name(tgt)
    rules = [
        f"Translate the following {S} text into {T}. It is an excerpt from a book.",
        f"Translate faithfully and completely into natural, fluent {T}: "
        "keep the meaning, tone, register, dialogue, proper nouns and "
        "numbers, and the paragraph structure.",
        "Never summarize, never omit anything, never add explanations, "
        "notes or comments.",
    ]
    if has_markup(text):
        rules.append(TAG_RULE)
    return ("\n".join(rules) + "\n\n" + glossary_block(glossary, text, tgt)
            + f"Output only the {T} translation.\n\n{S} TEXT:\n{text}")


def prompt_translategemma(src: str, tgt: str, text: str) -> str:
    # Consigne d'entraînement de TranslateGemma, reproduite à l'identique :
    # s'en écarter dégrade nettement ce modèle spécialisé.
    S, T = lang_name(src), lang_name(tgt)
    return (
        f"You are a professional {S} ({src}) to {T} ({tgt}) translator. "
        f"Your goal is to accurately convey the meaning and nuances of the "
        f"original {S} text while adhering to {T} grammar, vocabulary, and "
        f"cultural sensitivities.\n"
        f"Produce only the {T} translation, without any additional "
        f"explanations or commentary. Please translate the following {S} "
        f"text into {T}:\n\n\n{text}"
    )


def prompt_revise(src: str, tgt: str, original: str, translation: str,
                  glossary, final: bool) -> str:
    S, T = lang_name(src), lang_name(tgt)
    if final:
        head = (
            f"You are proofreading, for the last time, the {T} translation of "
            f"a {S} book. Read it against the original and improve fluency, "
            f"idiomatic {T} and consistency (terms, names, forms of address), "
            f"while staying strictly faithful to the original. Fix any "
            f"remaining error. Do not rewrite what is already good."
        )
    else:
        head = (
            f"You are a meticulous bilingual editor revising the {T} "
            f"translation of a {S} book. Compare the translation with the "
            f"original and correct: mistranslations, omissions, additions, "
            f"false friends, grammar and spelling mistakes, and literal or "
            f"unnatural phrasing. Keep the author's style and register. Do "
            f"not rewrite what is already correct."
        )
    parts = [head, "Never summarize and never add comments."]
    if has_markup(original):
        parts.append(TAG_RULE)
    return (
        "\n".join(parts) + "\n\n" + glossary_block(glossary, original, tgt)
        + f"Output only the revised {T} text.\n\n"
        + f"{S} ORIGINAL:\n{original}\n\n"
        + f"{T} TRANSLATION:\n{translation}\n\n"
        + f"REVISED {T} TRANSLATION:"
    )


_PREAMBLE = re.compile(
    r"^(here(?:'s| is)|voici|translation|traduction|revised|révis|corrected|"
    r"übersetzung|traducción)\b[^\n]{0,80}:\s*\n", re.IGNORECASE)


def clean_output(out: str) -> str:
    s = out.replace("<end_of_turn>", "").strip()
    fence = re.fullmatch(r"```[a-zA-Z]*\n(.*?)\n?```", s, re.DOTALL)
    if fence:
        s = fence.group(1).strip()
    s = _PREAMBLE.sub("", s, count=1).strip()
    s = re.sub(r"^REVISED [A-Z][a-zA-Z ]* TRANSLATION:\s*", "", s).strip()
    return s


def length_ok(source: str, out: str) -> bool:
    """Garde-fou contre les sorties tronquées, résumées ou qui bouclent."""
    n = len(re.sub(r"<[^>]+>", "", source))
    m = len(re.sub(r"<[^>]+>", "", out))
    if n < 80:
        return m > 0 and m < max(400, n * 6)
    return 0.35 * n <= m <= 3.0 * n


# ═══════════════════════════════════════════════════════════════════════════════
# MOTEUR MULTI-PASSES
# ═══════════════════════════════════════════════════════════════════════════════

class Engine:
    def __init__(self, client: LlamaClient, cache: Cache, src: str, tgt: str,
                 passes: int, glossary: list[tuple[str, str]]) -> None:
        self.client = client
        self.cache = cache
        self.src, self.tgt = src, tgt
        self.passes = passes
        self.glossary = glossary

    def key(self, text: str) -> str:
        h = hashlib.sha1()
        h.update(f"{self.client.fmt}|{self.src}|{self.tgt}|".encode())
        h.update(text.encode("utf-8"))
        return h.hexdigest()

    def _call_translate(self, text: str, temperature: float,
                        generic: bool = False) -> tuple[str, bool]:
        c = self.client
        if c.fmt == "translategemma" and generic:
            # Consigne explicite (règle des balises comprise) dans un tour de
            # parole Gemma : la consigne native de TranslateGemma ne dit rien
            # des balises, que le modèle supprime alors volontiers.
            return c.gemma_raw(prompt_translate(self.src, self.tgt, text,
                                                self.glossary),
                               text, temperature)
        if c.fmt == "translategemma":
            return c.gemma_raw(prompt_translategemma(self.src, self.tgt, text),
                               text, temperature)
        return c.chat(prompt_translate(self.src, self.tgt, text, self.glossary),
                      text, temperature)

    def untranslated(self, source: str, out: str) -> bool:
        """Le modèle a-t-il recopié l'original au lieu de le traduire ?"""
        if self.src == self.tgt:
            return False
        def norm(t):
            return re.sub(r"\W+", " ", re.sub(r"<[^>]+>", " ", t)).strip().lower()
        a, b = norm(source), norm(out)
        return len(a) > 20 and a == b

    def _call_revise(self, text: str, current: str, final: bool) -> tuple[str, bool]:
        c = self.client
        prompt = prompt_revise(self.src, self.tgt, text, current,
                               self.glossary, final)
        if c.fmt == "translategemma":
            return c.gemma_raw(prompt, text, 0.1)
        return c.chat(prompt, text, 0.1)

    def run(self, text: str, valid, generic: bool = False) -> str | None:
        """
        Traduit *text* avec toutes les passes. *valid(sortie)* vérifie la
        structure (balises). Retourne None si la passe 1 est inexploitable
        (tronquée ou invalide) : l'appelant redécoupe.
        *generic* : consigne explicite au lieu de la consigne native de
        TranslateGemma (second essai quand les balises n'ont pas survécu).
        """
        k = self.key(("generic|" if generic else "") + text)
        cur = self.cache.get(k, 1)
        if cur is not None:
            STATS.cached += 1
        else:
            cur = None
            for temperature in (0.1, 0.35):
                out, truncated = self._call_translate(text, temperature, generic)
                out = clean_output(out)
                if truncated or not out or not valid(out):
                    return None
                cur = out
                if length_ok(text, out) and not self.untranslated(text, out):
                    break          # sinon : 2e essai, un peu plus de température
            if self.untranslated(text, cur):
                STATS.untranslated += 1
                log(f"  ⚠ bloc renvoyé NON TRADUIT par le modèle : "
                    f"« {re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text)).strip()[:60]}… »")
            elif not length_ok(text, cur):
                STATS.suspicious += 1
                log(f"  ⚠ longueur de traduction suspecte "
                    f"({len(text)} → {len(cur)} car.) : « {text[:60]}… »")
            self.cache.put(k, 1, cur)

        for p in range(2, self.passes + 1):
            rev = self.cache.get(k, p)
            if rev is None:
                out, truncated = self._call_revise(text, cur, final=(p == 3))
                out = clean_output(out)
                if truncated or not out or not valid(out) \
                        or not length_ok(text, out):
                    STATS.revisions_rejected += 1
                    out = cur          # révision rejetée : on garde la passe précédente
                self.cache.put(k, p, out)
                rev = out
            else:
                STATS.cached += 1
            cur = rev
        return cur


# ═══════════════════════════════════════════════════════════════════════════════
# SEGMENTS : encodage/décodage de la mise en forme inline
# ═══════════════════════════════════════════════════════════════════════════════

_TOKEN = re.compile(r"<\s*(/?)\s*([gx])\s*(\d+)\s*(/?)\s*>", re.IGNORECASE)
_SEG = re.compile(r'<seg\s+n\s*=\s*["\']?(\d+)["\']?\s*>(.*?)</seg\s*>',
                  re.DOTALL | re.IGNORECASE)


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unesc(text: str) -> str:
    return html.unescape(text)


def split_sentences(text: str, limit: int) -> list[str]:
    """Découpe un texte trop long en morceaux ≤ limit, aux fins de phrase."""
    sentences = re.split(r"(?<=[.!?…;»\"”])\s+", text)
    chunks, cur = [], ""
    for s in sentences:
        while len(s) > limit:                         # phrase démesurée
            cut = s.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(s[:cut].strip())
            s = s[cut:].strip()
        if cur and len(cur) + 1 + len(s) > limit:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c]


class Segment:
    """Un bloc de texte à traduire (paragraphe, titre…)."""

    def __init__(self, enc: str, plain: str, apply_fn) -> None:
        self.enc = enc            # texte avec balises neutres, échappé
        self.plain = plain        # texte brut
        self._apply = apply_fn    # (traduction encodée | None, texte brut | None)

    @property
    def has_tags(self) -> bool:
        return bool(_TOKEN.search(self.enc))

    def inline_ok(self, out: str) -> bool:
        return self._apply(out, None, dry_run=True)

    def apply(self, out: str) -> None:
        self._apply(out, None)

    def apply_plain(self, text: str) -> None:
        self._apply(None, text)


def parse_group(out: str, n: int) -> list[str] | None:
    found = {}
    for m in _SEG.finditer(out):
        i = int(m.group(1))
        if i in found:
            return None
        found[i] = m.group(2).strip()
    if sorted(found) != list(range(1, n + 1)):
        return None
    if any(not v for v in found.values()):
        return None
    return [found[i] for i in range(1, n + 1)]


class Translator:
    # Au-delà de ces échecs CONSÉCUTIFS, le modèle est jugé incapable de
    # garder les balises : on cesse de les lui envoyer (chaque tentative
    # ratée coûte un appel complet pour rien).
    GROUP_FAIL_LIMIT = 3
    INLINE_FAIL_LIMIT = 6

    def __init__(self, engine: Engine, max_chars: int) -> None:
        self.engine = engine
        self.max_chars = max_chars
        self.grouping = True
        self.inline = True
        self._group_fails = 0
        self._inline_fails = 0

    # ── Résultat final par segment ───────────────────────────────────────────
    #
    # Le cache des passes est indexé par le texte de l'UNITÉ envoyée au
    # modèle : si le découpage change d'une session à l'autre (taille des
    # blocs modifiée, serveur relancé avec un autre --ctx-size, autre
    # modèle…), ces entrées ne servent plus. On garde donc AUSSI, pour chaque
    # segment, sa traduction finale, indexée par son seul texte : la reprise
    # ne dépend plus ni du découpage ni du modèle.

    def _final_key(self, seg: Segment) -> str:
        e = self.engine
        return hashlib.sha1(
            f"final|{e.src}|{e.tgt}|{seg.enc}".encode("utf-8")).hexdigest()

    def _store_final(self, seg: Segment, value: str, encoded: bool) -> None:
        self.engine.cache.put(self._final_key(seg), self.engine.passes,
                              ("E:" if encoded else "P:") + value)

    def final_of(self, seg: Segment) -> str | None:
        k = self._final_key(seg)
        for p in range(3, self.engine.passes - 1, -1):     # meilleure d'abord
            v = self.engine.cache.get(k, p)
            if v is not None:
                return v
        return None

    def _apply_final(self, seg: Segment, v: str) -> bool:
        kind, value = v[:2], v[2:]
        if kind == "E:" and seg.inline_ok(value):
            seg.apply(value)
            return True
        if kind == "P:":
            seg.apply_plain(value)
            return True
        return False

    def _done(self, seg: Segment, res: str | None, plain: str | None = None) -> None:
        if res is not None:
            seg.apply(res)
            self._store_final(seg, res, True)
        else:
            seg.apply_plain(plain)
            self._store_final(seg, plain, False)

    def _run_tagged(self, text: str, valid) -> str | None:
        """Texte balisé : consigne native, puis consigne explicite (TranslateGemma)."""
        res = self.engine.run(text, valid)
        if res is None and self.engine.client.fmt == "translategemma":
            res = self.engine.run(text, valid, generic=True)
            if res is not None:
                STATS.tags_rescued += 1
        return res

    def _inline_result(self, ok: bool) -> None:
        self._inline_fails = 0 if ok else self._inline_fails + 1
        if self.inline and self._inline_fails >= self.INLINE_FAIL_LIMIT:
            self.inline = False
            log("  ⚠ Le modèle ne conserve pas les balises de mise en forme : "
                "suite en texte brut (italiques, notes… simplifiés)")

    def plain_text(self, text: str, depth: int = 0) -> str:
        """Texte brut, redécoupé tant que le modèle tronque sa sortie."""
        limit = self.max_chars if depth == 0 else max(200, self.max_chars >> depth)
        if len(text) > limit:
            STATS.split_long += 1 if depth == 0 else 0
            return " ".join(self.plain_text(c, depth + 1)
                            for c in split_sentences(text, limit))
        res = self.engine.run(esc(text), lambda o: True)
        if res is not None:
            return unesc(res)
        if depth < 4 and len(text) > 200:
            half = split_sentences(text, max(200, len(text) // 2 + 1))
            if len(half) > 1:
                return " ".join(self.plain_text(c, depth + 1) for c in half)
        raise ServerError("le modèle tronque sa sortie même sur un petit bloc "
                          "(contexte --ctx-size trop petit ?)")

    def single(self, seg: Segment) -> None:
        final = self.final_of(seg)
        if final is not None and self._apply_final(seg, final):
            STATS.cached += 1
            return
        if len(seg.enc) > self.max_chars * 1.2:
            if seg.has_tags:
                STATS.format_simplified += 1
            self._done(seg, None, self.plain_text(seg.plain))
            return
        if seg.has_tags and not self.inline:
            STATS.format_simplified += 1
            self._done(seg, None, self.plain_text(seg.plain))
            return
        if seg.has_tags:
            res = self._run_tagged(seg.enc, seg.inline_ok)
        else:
            res = self.engine.run(seg.enc, seg.inline_ok)
        if seg.has_tags:
            self._inline_result(res is not None)
        if res is not None:
            self._done(seg, res)
            return
        if seg.has_tags:
            STATS.format_simplified += 1
        self._done(seg, None, self.plain_text(seg.plain))

    def unit(self, segs: list[Segment]) -> None:
        # Segments déjà traduits (session précédente, autre découpage) :
        # appliqués tels quels ; seuls les autres partent au modèle.
        pending = []
        for seg in segs:
            final = self.final_of(seg)
            if final is not None and self._apply_final(seg, final):
                STATS.cached += 1
            else:
                pending.append(seg)
        if not pending:
            return
        segs = pending
        if len(segs) == 1 or not self.grouping:
            for s in segs:
                self.single(s)
            return
        text = "\n".join(f'<seg n="{i}">{s.enc}</seg>'
                         for i, s in enumerate(segs, start=1))
        res = self._run_tagged(text,
                               lambda o: parse_group(o, len(segs)) is not None)
        if res is None:
            STATS.group_fallbacks += 1
            self._group_fails += 1
            if self._group_fails >= self.GROUP_FAIL_LIMIT:
                self.grouping = False
                log("  ⚠ Le modèle ne conserve pas le découpage en paragraphes "
                    "groupés : suite paragraphe par paragraphe")
            for s in segs:
                self.single(s)
            return
        self._group_fails = 0
        for s, part in zip(segs, parse_group(res, len(segs))):
            if s.inline_ok(part):
                self._done(s, part)
            else:
                self.single(s)


def group_units(segs: list[Segment], max_chars: int) -> list[list[Segment]]:
    units, cur, size = [], [], 0
    for s in segs:
        n = len(s.enc) + 20
        if cur and (size + n > max_chars or len(cur) >= MAX_SEGS_PER_UNIT):
            units.append(cur)
            cur, size = [], 0
        cur.append(s)
        size += n
    if cur:
        units.append(cur)
    return units


# ═══════════════════════════════════════════════════════════════════════════════
# EPUB
# ═══════════════════════════════════════════════════════════════════════════════

def local(name: str | None) -> str:
    return (name or "").split(":")[-1].lower()


BLOCK = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "dt", "dd", "td",
         "th", "caption", "figcaption", "blockquote", "div", "title"}
STRUCT = BLOCK | {"ul", "ol", "dl", "table", "thead", "tbody", "tfoot", "tr",
                  "section", "article", "aside", "nav", "header", "footer",
                  "figure", "body", "hr", "pre", "main", "hgroup", "details",
                  "summary", "address", "form", "fieldset"}
SKIP = {"script", "style", "pre", "code", "math", "svg", "kbd", "samp", "var"}
VOID = {"br", "img", "wbr", "hr", "image", "input", "col", "source"}
_LETTER = re.compile(r"[^\W\d_]")


def _fix_entities(raw: bytes) -> bytes:
    """
    &nbsp;, &mdash;… sont définis par la DTD XHTML, que lxml ne charge pas :
    l'analyseur XML les supprimerait. On les convertit en références
    numériques, valables partout.
    """
    text = raw.decode("utf-8", errors="replace")

    def rep(m):
        name = m.group(1)
        if name in ("amp", "lt", "gt", "quot", "apos"):
            return m.group(0)
        cp = html.entities.name2codepoint.get(name)
        return f"&#{cp};" if cp else m.group(0)

    return re.sub(r"&([A-Za-z][A-Za-z0-9]*);", rep, text).encode("utf-8")


def parse_xhtml(raw: bytes):
    from bs4 import BeautifulSoup
    try:
        soup = BeautifulSoup(_fix_entities(raw), "xml")
        if soup.find(lambda t: local(t.name) == "body") is not None:
            return soup, "xml"
    except Exception:
        pass
    return BeautifulSoup(raw, "html.parser"), "html"


def make_segment(el) -> Segment:
    """Encode le contenu de *el* avec des balises neutres numérotées."""
    from bs4 import NavigableString, Tag
    from bs4.element import (Comment, CData, ProcessingInstruction,
                             Declaration, Doctype)

    slots: dict[int, tuple[str, object]] = {}
    parts: list[str] = []
    counter = [0]

    def walk(node) -> None:
        for child in node.children:
            if isinstance(child, (Comment, CData, ProcessingInstruction,
                                  Declaration, Doctype)):
                continue
            if isinstance(child, NavigableString):
                parts.append(esc(str(child)))
            elif isinstance(child, Tag):
                counter[0] += 1
                n = counter[0]
                name = local(child.name)
                if (name in VOID or name in SKIP
                        or not child.get_text().strip()):
                    slots[n] = ("x", copy.copy(child))
                    parts.append(f"<x{n}/>")
                else:
                    shell = copy.copy(child)
                    shell.clear()
                    slots[n] = ("g", shell)
                    parts.append(f"<g{n}>")
                    walk(child)
                    parts.append(f"</g{n}>")

    walk(el)
    # [ \t\r\n] et non \s : les espaces insécables (typographie) sont gardées.
    enc = re.sub(r"[ \t\r\n]+", " ", "".join(parts)).strip(" ")
    plain = re.sub(r"\s+", " ", el.get_text(" ")).strip()

    def decode(out: str):
        """Reconstruit la liste de nœuds ; None si les balises sont abîmées."""
        root: list = []
        stack: list[tuple[int | None, list, object]] = [(None, root, None)]
        used: set[int] = set()
        pos = 0
        for m in _TOKEN.finditer(out):
            text = out[pos:m.start()]
            if text:
                stack[-1][1].append(NavigableString(unesc(text)))
            pos = m.end()
            closing, kind, n = m.group(1), m.group(2).lower(), int(m.group(3))
            if n not in slots or slots[n][0] != kind:
                return None
            if kind == "x":
                if n in used:
                    return None
                used.add(n)
                stack[-1][1].append(copy.copy(slots[n][1]))
            elif closing:
                if stack[-1][0] != n:
                    return None
                _, children, tag = stack.pop()
                for c in children:
                    tag.append(c)
                stack[-1][1].append(tag)
            else:
                if n in used:
                    return None
                used.add(n)
                stack.append((n, [], copy.copy(slots[n][1])))
        tail = out[pos:]
        if tail:
            stack[-1][1].append(NavigableString(unesc(tail)))
        if len(stack) != 1:
            return None
        missing = set(slots) - used
        # Une paire <gN> ou un élément porteur de sens (saut de ligne,
        # image) perdu → invalide ; seule une ancre vide peut être recasée.
        if any(slots[n][0] == "g" or local(slots[n][1].name) in VOID | SKIP
               for n in missing):
            return None
        # Ancres vides oubliées (repères de page, cibles de note) : remises
        # en tête plutôt que perdues — les liens qui les visent marchent encore.
        lead = [copy.copy(slots[n][1]) for n in sorted(missing)]
        return lead + root

    def apply(out, plain_text, dry_run=False):
        if out is not None:
            nodes = decode(out)
            if dry_run:
                return nodes is not None
            if nodes is None:
                raise ValueError("balises invalides")
        else:
            anchors = [copy.copy(t) for k, t in slots.values()
                       if k == "x" and local(t.name) not in VOID | SKIP]
            nodes = anchors + [NavigableString(plain_text)]
        el.clear()
        for node in nodes:
            el.append(node)
        return True

    return Segment(enc, plain, apply)


def epub_targets(soup) -> list:
    targets = []
    for el in soup.find_all(True):
        name = local(el.name)
        if name not in BLOCK:
            continue
        if any(local(a.name) in SKIP for a in el.parents):
            continue
        if name == "title" and not any(local(a.name) == "head" for a in el.parents):
            continue
        if el.find(lambda t: local(t.name) in STRUCT) is not None:
            # Élément de sommaire : <li><a>Titre</a><ol>…</ol></li>
            if name == "li":
                for child in el.find_all(recursive=False):
                    if local(child.name) in ("a", "span") and \
                            _LETTER.search(child.get_text()):
                        targets.append(child)
            continue
        if _LETTER.search(el.get_text()):
            targets.append(el)
    return targets


def epub_layout(zin: zipfile.ZipFile) -> tuple[str | None, list[str], list[str]]:
    """(chemin de l'OPF, documents dans l'ordre de lecture, fichiers NCX)."""
    from bs4 import BeautifulSoup
    names = set(zin.namelist())
    opf = None
    try:
        cont = BeautifulSoup(zin.read("META-INF/container.xml"), "xml")
        rf = cont.find(lambda t: local(t.name) == "rootfile")
        if rf and rf.get("full-path") in names:
            opf = rf["full-path"]
    except KeyError:
        pass
    if opf is None:
        opf = next((n for n in zin.namelist() if n.lower().endswith(".opf")), None)
    html_docs = [n for n in zin.namelist()
                 if n.lower().endswith((".xhtml", ".html", ".htm"))]
    if opf is None:
        return None, html_docs, []

    soup = BeautifulSoup(zin.read(opf), "xml")
    base = posixpath.dirname(opf)
    manifest = {}
    ncx = []
    for item in soup.find_all(lambda t: local(t.name) == "item"):
        href = item.get("href")
        if not href:
            continue
        from urllib.parse import unquote
        path = posixpath.normpath(posixpath.join(base, unquote(href)))
        manifest[item.get("id")] = path
        if item.get("media-type") == "application/x-dtbncx+xml":
            ncx.append(path)
    order = []
    for ref in soup.find_all(lambda t: local(t.name) == "itemref"):
        p = manifest.get(ref.get("idref"))
        if p in names and p not in order:
            order.append(p)
    order += [d for d in html_docs if d not in order]
    return opf, order, [n for n in ncx if n in names]


class EpubBook:
    kind = "epub"

    def __init__(self, path: Path, tgt: str, max_chars: int) -> None:
        from bs4 import BeautifulSoup
        self.path = path
        self.tgt = tgt
        with zipfile.ZipFile(path) as zin:
            self.infos = zin.infolist()
            self.raw = {i.filename: zin.read(i.filename) for i in self.infos}
            self.opf, order, ncx = epub_layout(zin)
        self.soups: dict[str, tuple[object, str]] = {}
        self.chapters: list[tuple[str, list[list[Segment]]]] = []
        n_docs = 0
        for name in order:
            soup, mode = parse_xhtml(self.raw[name])
            segs = [make_segment(el) for el in epub_targets(soup)]
            self.soups[name] = (soup, mode)
            if segs:
                n_docs += 1
                self.chapters.append((name, group_units(segs, max_chars)))
        for name in ncx:
            soup = BeautifulSoup(_fix_entities(self.raw[name]), "xml")
            segs = []
            for t in soup.find_all(lambda t: local(t.name) == "text"):
                if _LETTER.search(t.get_text()):
                    segs.append(self._ncx_segment(t))
            self.soups[name] = (soup, "xml")
            if segs:
                self.chapters.append((name, group_units(segs, max_chars)))

    @staticmethod
    def _ncx_segment(t) -> Segment:
        text = re.sub(r"\s+", " ", t.get_text()).strip()

        def apply(out, plain_text, dry_run=False):
            if dry_run:
                return not _TOKEN.search(out)
            t.string = unesc(out) if out is not None else plain_text
            return True

        return Segment(esc(text), text, apply)

    def write(self, out: Path) -> None:
        for name, (soup, mode) in self.soups.items():
            root = soup.find(lambda t: local(t.name) == "html")
            if root is not None:
                for attr in ("lang", "xml:lang"):
                    if attr in root.attrs:
                        root[attr] = self.tgt
        data = {}
        for name, (soup, mode) in self.soups.items():
            data[name] = str(soup).encode("utf-8")
        if self.opf and self.opf in self.raw:
            text = self.raw[self.opf].decode("utf-8", errors="replace")
            text = re.sub(r"(<dc:language[^>]*>)[^<]*(</dc:language>)",
                          rf"\g<1>{self.tgt}\g<2>", text)
            data[self.opf] = text.encode("utf-8")

        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.name + ".part")
        with zipfile.ZipFile(tmp, "w") as zout:
            # « mimetype » en premier et non compressé : exigé par la norme.
            infos = sorted(self.infos, key=lambda i: i.filename != "mimetype")
            for info in infos:
                payload = data.get(info.filename, self.raw[info.filename])
                if info.filename == "mimetype":
                    zout.writestr(info, payload, compress_type=zipfile.ZIP_STORED)
                else:
                    zout.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED)
        os.replace(tmp, out)


# ═══════════════════════════════════════════════════════════════════════════════
# PDF ET TEXTE
# ═══════════════════════════════════════════════════════════════════════════════

_END_SENTENCE = re.compile(r"[.!?:;»\"”)\]…]$")


def join_lines(a: str, b: str) -> str:
    """Recolle deux lignes en retirant la césure éventuelle."""
    if not a:
        return b
    if a.endswith("-") and b[:1].islower() and len(a) > 1 and a[-2].isalpha():
        return a[:-1] + b
    return a + " " + b


class PlainSeg:
    def __init__(self, kind: str, text: str) -> None:
        self.kind = kind
        self.text = text
        self.out: str | None = None

    def segment(self) -> Segment:
        def apply(out, plain_text, dry_run=False):
            if dry_run:
                return not _TOKEN.search(out)
            self.out = unesc(out) if out is not None else plain_text
            return True
        return Segment(esc(self.text), self.text, apply)


def pdf_paragraphs(path: Path) -> list[PlainSeg]:
    try:
        import pymupdf as fitz          # PyMuPDF ≥ 1.24
    except ImportError:
        import fitz                     # anciennes versions
    pages = []
    sizes = Counter()
    with fitz.open(path) as doc:
        for page in doc:
            blocks = []
            for b in page.get_text("dict").get("blocks", []):
                if b.get("type") != 0:
                    continue
                text, weight, nch = "", 0.0, 0
                for line in b.get("lines", []):
                    lt = "".join(s.get("text", "") for s in line.get("spans", []))
                    lt = re.sub(r"\s+", " ", lt).strip()
                    for s in line.get("spans", []):
                        n = len(s.get("text", "").strip())
                        weight += s.get("size", 0) * n
                        nch += n
                        sizes[round(s.get("size", 0), 1)] += n
                    if lt:
                        text = join_lines(text, lt)
                if text:
                    blocks.append((text, weight / max(nch, 1)))
            pages.append(blocks)

    body = sizes.most_common(1)[0][0] if sizes else 10.0

    def norm(t: str) -> str:
        return re.sub(r"\d+", "#", t.lower()).strip()

    running: set[str] = set()
    if len(pages) >= 4:
        cnt = Counter()
        for blocks in pages:
            cnt.update({norm(t) for t, _ in blocks[:2] + blocks[-2:]
                        if len(t) < 120})
        running = {k for k, v in cnt.items()
                   if v >= max(3, 0.3 * len(pages))}

    paras: list[PlainSeg] = []
    for blocks in pages:
        for text, size in blocks:
            if re.fullmatch(r"[\d\s\-–—.|]+|(page|p\.)\s*\d+", text, re.I):
                continue                                   # numéro de page
            if norm(text) in running:
                continue                                   # en-tête / pied
            kind = "p"
            if size >= body * 1.6 and len(text) < 150:
                kind = "h1"
            elif size >= body * 1.2 and len(text) < 200:
                kind = "h2"
            prev = paras[-1] if paras else None
            if (kind == "p" and prev is not None and prev.kind == "p"
                    and not _END_SENTENCE.search(prev.text)
                    and text[:1].islower()):
                prev.text = join_lines(prev.text, text)    # suite (saut de page)
                continue
            paras.append(PlainSeg(kind, text))
    if not paras:
        raise RuntimeError("aucun texte extrait du PDF (scanné ? une OCR est "
                           "nécessaire)")
    return paras


class FlatBook:
    """PDF → Markdown, TXT → TXT."""

    def __init__(self, path: Path, max_chars: int) -> None:
        self.path = path
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            self.kind = "pdf"
            self.paras = pdf_paragraphs(path)
        else:
            self.kind = "txt"
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            self.paras = [PlainSeg("p", re.sub(r"\s+", " ", p).strip())
                          for p in re.split(r"\n\s*\n", text) if p.strip()]
        segs = [p.segment() for p in self.paras if _LETTER.search(p.text)]
        self.chapters = [(path.name, group_units(segs, max_chars))]

    def write(self, out: Path) -> None:
        lines = []
        for p in self.paras:
            text = p.out if p.out is not None else p.text
            if self.kind == "pdf" and p.kind == "h1":
                lines.append("# " + text)
            elif self.kind == "pdf" and p.kind == "h2":
                lines.append("## " + text)
            else:
                lines.append(text)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n\n".join(lines) + "\n", encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRAMME PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def load_glossary(path: str | None) -> list[tuple[str, str]]:
    if not path:
        return []
    pairs = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for sep in ("=", "\t", "→", ";"):
            if sep in line:
                a, b = line.split(sep, 1)
                if a.strip() and b.strip():
                    pairs.append((a.strip(), b.strip()))
                break
    return pairs


def default_output(source: Path, tgt: str, limit: int) -> Path:
    ext = {".epub": ".epub", ".pdf": ".md"}.get(source.suffix.lower(), ".txt")
    trial = ".essai" if limit else ""
    return source.with_name(f"{source.stem}.{tgt}{trial}{ext}")


# ═══════════════════════════════════════════════════════════════════════════════
# TRAVAIL EN COURS : fichier de suivi, verrou, demande de pause
# ═══════════════════════════════════════════════════════════════════════════════
#
# Tout ce qu'il faut pour reprendre un autre jour vit À CÔTÉ DU LIVRE :
#   <livre>.<cible>.cache.jsonl  les traductions (ajout seul, fsync régulier)
#   <livre>.<cible>.job.json     réglages, avancement, état (running, paused,
#                                interrupted, error, done) — lu par l'onglet
#                                Livre pour proposer « Reprendre »
#   <livre>.<cible>.pause        demande de pause (créée par l'interface) :
#                                vérifiée entre deux unités, donc sans perdre
#                                l'unité en cours
#   <livre>.<cible>.lock         empêche deux traductions du même livre
#   <livre>.<cible>.partiel.ext  livre reconstitué au moment de la pause :
#                                début traduit, suite en langue d'origine

EXIT_PAUSED = 10
EXIT_LOCKED = 4


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
        k32.CloseHandle(handle)
        return bool(ok) and code.value == 259          # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Job:
    def __init__(self, base: Path) -> None:
        self.path = Path(str(base) + ".job.json")
        self.pause_path = Path(str(base) + ".pause")
        self.lock_path = Path(str(base) + ".lock")
        self.data: dict = {}
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        self._last_save = 0.0

    def lock(self) -> bool:
        try:
            pid = int(self.lock_path.read_text().strip() or 0)
        except (OSError, ValueError):
            pid = 0
        if pid and pid != os.getpid() and pid_alive(pid):
            return False
        self.lock_path.write_text(str(os.getpid()))
        return True

    def unlock(self) -> None:
        try:
            self.lock_path.unlink()
        except OSError:
            pass

    def pause_requested(self) -> bool:
        return self.pause_path.exists()

    def clear_pause(self) -> None:
        try:
            self.pause_path.unlink()
        except OSError:
            pass

    def save(self, force: bool = True, **fields) -> None:
        self.data.update(fields)
        now = time.monotonic()
        if not force and now - self._last_save < 30:
            return
        self._last_save = now
        self.data["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass


def partial_output(out: Path) -> Path:
    return out.with_name(out.stem + ".partiel" + out.suffix)


def main() -> int:
    global _LOGFILE
    ap = argparse.ArgumentParser(
        description="Traduction de livre (EPUB, PDF, TXT) via llama.cpp local.")
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--src", default="en")
    ap.add_argument("--tgt", default="fr")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--model", default="")
    ap.add_argument("--passes", type=int, choices=(1, 2, 3), default=2)
    ap.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    ap.add_argument("--glossary")
    ap.add_argument("--format", choices=("auto", "chat", "translategemma"),
                    default="auto")
    ap.add_argument("--limit", type=int, default=0,
                    help="essai : ne traduire que les N premières unités")
    ap.add_argument("--fresh", action="store_true",
                    help="ignorer le cache de reprise")
    args = ap.parse_args()

    source = Path(args.input).resolve()
    if not source.is_file():
        event("error", msg=f"fichier introuvable : {source}")
        log(f"Fichier introuvable : {source}")
        return 2
    if source.suffix.lower() not in (".epub", ".pdf", ".txt"):
        event("error", msg="formats acceptés : EPUB, PDF, TXT")
        log("Formats acceptés : EPUB, PDF, TXT")
        return 2

    out = Path(args.output).resolve() if args.output else \
        default_output(source, args.tgt, args.limit)
    stem = out.with_suffix("")
    try:
        _LOGFILE = open(str(stem) + ".log", "a", encoding="utf-8")
    except OSError:
        _LOGFILE = None

    base = Path(str(stem).replace(".essai", ""))
    job = Job(base)
    if not job.lock():
        event("error", msg="ce livre est déjà en cours de traduction "
                           "(autre fenêtre ou autre processus)")
        log("✖ Ce livre est déjà en cours de traduction par un autre processus.")
        return EXIT_LOCKED
    try:
        return run(args, source, out, base, job)
    finally:
        job.unlock()


def run(args, source: Path, out: Path, base: Path, job: Job) -> int:
    stem = out.with_suffix("")
    # Une demande de pause restée d'une session précédente ne doit pas
    # arrêter celle-ci dès le premier bloc.
    job.clear_pause()

    # Arrêt du système ou bouton Arrêter (SIGTERM) : sortie propre, cache
    # synchronisé et état « interrupted » enregistré.
    def _on_term(signum, frame):
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGTERM, _on_term)
    except (ValueError, OSError, AttributeError):
        pass

    try:
        import requests  # noqa: F401
        import bs4  # noqa: F401
    except ImportError as exc:
        event("error", msg=f"module manquant dans le Python portable : {exc.name}")
        log(f"Module Python manquant : {exc.name} (pip install -r requirements.txt)")
        return 2

    log("─" * 60)
    log(f"Livre   : {source.name}")
    log(f"Langues : {lang_name(args.src)} → {lang_name(args.tgt)} · "
        f"{args.passes} passe(s)")

    client = LlamaClient(args.url, args.model, args.format)
    try:
        client.probe()
    except ServerError as exc:
        event("error", msg=str(exc))
        log(f"✖ {exc}")
        log("  Démarrez llama-server (ex. llama-vulkan.bat) et vérifiez l'URL.")
        return 2

    # Taille d'unité plafonnée par le contexte réel : la passe de révision
    # porte original + traduction en entrée ET la révision en sortie.
    cap = max(600, int((client.n_ctx * 0.85 - 400) / 1.3))
    max_chars = max(300, min(args.max_chars, cap))
    model = os.path.basename(client.model_path) or args.model or "?"
    log(f"Serveur : {client.root} · modèle {model} · contexte {client.n_ctx} "
        f"· mode {client.fmt}")
    if max_chars < args.max_chars:
        log(f"  Taille des blocs ramenée à {max_chars} car. (contexte serveur)")

    glossary = load_glossary(args.glossary)
    if glossary:
        log(f"Glossaire : {len(glossary)} entrée(s)")
        if client.fmt == "translategemma":
            log("  (TranslateGemma : glossaire appliqué aux passes de révision)")

    try:
        if source.suffix.lower() == ".epub":
            book = EpubBook(source, args.tgt, max_chars)
        else:
            book = FlatBook(source, max_chars)
    except Exception as exc:
        event("error", msg=f"lecture du livre impossible : {exc}")
        log(f"✖ Lecture du livre impossible : {exc}")
        return 2

    cache = Cache(Path(str(base) + ".cache.jsonl"), fresh=args.fresh)
    engine = Engine(client, cache, args.src, args.tgt, args.passes, glossary)
    tr = Translator(engine, max_chars)

    plan = [(name, u) for name, units in book.chapters for u in units]
    full_units = len(plan)
    full_chars = sum(len(s.plain) for _, u in plan for s in u)
    if args.limit:
        plan = plan[:args.limit]
    unit_chars = [sum(len(s.plain) for s in u) for _, u in plan]
    total_chars = sum(unit_chars) or 1
    n_segs = sum(len(u) for _, u in plan)
    already = sum(1 for _, u in plan
                  if all(tr.final_of(s) is not None for s in u))
    n_chapters = len({name for name, _ in plan})
    log(f"Découpe : {n_chapters} chapitre(s), {n_segs} segments, "
        f"{len(plan)} unités, {total_chars:,} car.".replace(",", "\u202f")
        .replace("\u202f ", ", "))
    sha = file_sha256(source)
    # Un travail terminé (ou --fresh) ne prête pas sa date de début au suivant.
    previous = job.data if not args.fresh and job.data.get("status") != "done" else {}
    if previous.get("sha256") and previous["sha256"] != sha:
        log("⚠ Le livre a changé depuis le début de la traduction : les "
            "paragraphes inchangés sont repris, les autres seront traduits.")
    if already:
        since = previous.get("created")
        since = f" (travail commencé le {since})" if since else ""
        log(f"Reprise : {already} unité(s) sur {len(plan)} déjà traduites{since}")
    if args.limit:
        pct = 100 * sum(len(s.plain) for _, u in plan for s in u) // max(full_chars, 1)
        log(f"⚠ MODE ESSAI : {len(plan)} unité(s) sur {full_units} (~{pct} % du "
            f"livre) — le reste sera laissé dans la langue d'origine")
    event("plan", units=len(plan), chars=total_chars, segments=n_segs,
          cached=already, chapters=n_chapters, mode=client.fmt,
          n_ctx=client.n_ctx, max_chars=max_chars)

    trial = bool(args.limit)
    if not trial:
        job.save(
            book=str(source), sha256=sha, output=str(out),
            src=args.src, tgt=args.tgt, passes=args.passes,
            max_chars=args.max_chars, url=args.url, model=args.model,
            glossary=args.glossary or "", format=args.format,
            created=previous.get("created") or time.strftime("%Y-%m-%d %H:%M"),
            status="running", pid=os.getpid(),
            units=len(plan), done_units=already, chars=total_chars,
        )

    def stop_here(i_done: int, done_c: int, status: str, why: str) -> int:
        """Pause ou interruption : état stable sur disque, puis sortie."""
        cache.close()
        partial = None
        if not trial and i_done > 0:
            try:
                partial = partial_output(out)
                book.write(partial)
            except Exception as exc:          # noqa: BLE001
                log(f"  (livre partiel non écrit : {exc})")
                partial = None
        pct = int(100 * done_c / max(total_chars, 1))
        if not trial:
            job.save(status=status, done_units=i_done, done_chars=done_c,
                     pct=pct, partial=str(partial) if partial else "")
        log(f"⏸ {why} après {i_done}/{len(plan)} unités ({pct} %). "
            f"Reprise possible à tout moment, même après redémarrage.")
        if partial:
            log(f"  Aperçu du travail fait : {partial.name}")
        event("paused", done=i_done, units=len(plan), pct=pct,
              partial=str(partial) if partial else "", status=status)
        return EXIT_PAUSED if status == "paused" else 130

    t0 = time.monotonic()
    done_chars = 0
    fresh_chars = 0
    current = None
    chapter_idx = 0
    i_done = 0
    try:
        for i, ((name, unit), nch) in enumerate(zip(plan, unit_chars), start=1):
            if job.pause_requested():
                job.clear_pause()
                return stop_here(i_done, done_chars, "paused", "En pause")
            if name != current:
                current = name
                chapter_idx += 1
                log(f"[{chapter_idx}/{n_chapters}] {name}")
            calls_before = STATS.calls
            tr.unit(unit)
            i_done = i
            done_chars += nch
            if not trial:
                job.save(force=False, done_units=i, done_chars=done_chars,
                         pct=int(100 * done_chars / total_chars))
            if STATS.calls > calls_before:
                fresh_chars += nch
            elapsed = time.monotonic() - t0
            remaining = total_chars - done_chars
            eta = (elapsed / fresh_chars * remaining) if fresh_chars else None
            event("progress", done=i, units=len(plan), done_chars=done_chars,
                  chars=total_chars, elapsed=int(elapsed),
                  eta=int(eta) if eta is not None else None)
    except ServerError as exc:
        event("error", msg=str(exc))
        log(f"✖ Arrêt : {exc}")
        log("  Les blocs déjà traduits sont conservés : relancez pour reprendre.")
        cache.close()
        if not trial:
            job.save(status="error", error=str(exc), done_units=i_done,
                     done_chars=done_chars,
                     pct=int(100 * done_chars / total_chars))
        return 3
    except KeyboardInterrupt:
        return stop_here(i_done, done_chars, "interrupted", "Interrompu")

    cache.close()
    book.write(out)
    if not trial:
        try:
            partial_output(out).unlink()
        except OSError:
            pass
        job.save(status="done", done_units=len(plan), done_chars=total_chars,
                 pct=100, partial="")
    elapsed = time.monotonic() - t0
    s = STATS
    log(f"✔ Terminé en {fmt_duration(elapsed)} : {out.name}")
    details = [f"{s.calls} appel(s) au modèle", f"{s.cached} reprise(s) du cache"]
    if s.group_fallbacks:
        details.append(f"{s.group_fallbacks} groupe(s) retraduit(s) paragraphe par paragraphe")
    if s.format_simplified:
        details.append(f"{s.format_simplified} paragraphe(s) à mise en forme simplifiée")
    if s.revisions_rejected:
        details.append(f"{s.revisions_rejected} révision(s) rejetée(s)")
    if s.suspicious:
        details.append(f"{s.suspicious} traduction(s) de longueur suspecte")
    if s.untranslated:
        details.append(f"{s.untranslated} bloc(s) renvoyé(s) non traduit(s)")
    if s.tags_rescued:
        details.append(f"{s.tags_rescued} bloc(s) balisé(s) repris avec la consigne explicite")
    log("  " + " · ".join(details))
    if args.limit and len(plan) < full_units:
        log(f"⚠ Essai terminé : seules les {len(plan)} premières unités sur "
            f"{full_units} sont traduites dans {out.name}. Lancez « Traduire "
            f"le livre » pour le livre entier (l'essai sera repris du cache).")
    event("end", out=str(out), stats=s.as_dict(), elapsed=int(elapsed))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
