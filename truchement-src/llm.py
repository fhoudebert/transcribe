"""
llm.py — Serveur llama.cpp local : réglages partagés et traduction de texte
=============================================================================
Partagé par l'onglet Livre (ui/book_tab.py), l'onglet Texte 2 (case
« Serveur local ») et la fenêtre de réglage du serveur (⚙ de l'en-tête).

• Réglages : un seul fichier, build/truchement-llm.json (URL, modèle,
  passes, taille des blocs, langues et glossaire du livre, case de Texte 2).
  L'ancien build/truchement-livre.json est relu une fois s'il existe.

• Traduction de texte : la logique (consignes, mode TranslateGemma, passes
  de révision, garde-fous) n'existe qu'à UN endroit, traduire-livre.py ; ce
  module le charge comme un module ordinaire (importlib) et l'utilise sans
  cache disque. Le script vit à la racine, à côté de l'exécutable, et non
  dans le binaire : une correction du script profite donc aussi à Texte 2.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import threading
import urllib.request

import bootstrap


SCRIPT_NAME = "traduire-livre.py"

DEFAULTS: dict = {
    "url": "http://127.0.0.1:8080/v1",
    "model": "",
    "src": "en",
    "tgt": "fr",
    "passes": 2,
    "max_chars": 2500,
    "glossary": "",
    "dir": "",
    "book": "",
    "text_llm": False,
}


# ═══════════════════════════════════════════════════════════════════════════════
# RÉGLAGES
# ═══════════════════════════════════════════════════════════════════════════════

def _settings_dir() -> str:
    build = os.path.join(bootstrap.BASE_DIR, "build")
    return build if os.path.isdir(build) else bootstrap.BASE_DIR


def settings_path() -> str:
    return os.path.join(_settings_dir(), "truchement-llm.json")


def load_settings() -> dict:
    data = dict(DEFAULTS)
    for name in ("truchement-livre.json", "truchement-llm.json"):   # ancien puis actuel
        try:
            with open(os.path.join(_settings_dir(), name), encoding="utf-8") as fh:
                saved = json.load(fh)
            if isinstance(saved, dict):
                data.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass
    return data


def save_settings(data: dict) -> None:
    clean = {k: data.get(k, v) for k, v in DEFAULTS.items()}
    try:
        with open(settings_path(), "w", encoding="utf-8") as fh:
            json.dump(clean, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def server_root(url: str) -> str:
    root = (url or "").strip().rstrip("/")
    return root[:-3] if root.endswith("/v1") else root


def probe_server(url: str, timeout: float = 5) -> tuple[bool, str, str]:
    """
    (ok, modèle, contexte) — urllib et non requests : ce process n'a pas
    forcément le venv. Lève rien ; en cas d'échec ok=False et le 2e champ
    porte la raison.
    """
    root = server_root(url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(root + "/health", timeout=timeout) as r:
            r.read()
    except Exception as exc:
        return False, str(getattr(exc, "reason", None) or exc), ""
    model, ctx = "?", "?"
    try:
        with opener.open(root + "/props", timeout=timeout) as r:
            props = json.loads(r.read().decode("utf-8"))
        gen = props.get("default_generation_settings") or {}
        ctx = str(gen.get("n_ctx") or props.get("n_ctx") or "?")
        model = os.path.basename(props.get("model_path") or "") or "?"
    except Exception:
        pass
    return True, model, ctx


# ═══════════════════════════════════════════════════════════════════════════════
# TRAVAIL EN COURS (fichiers écrits par traduire-livre.py à côté du livre)
# ═══════════════════════════════════════════════════════════════════════════════

def job_base(book: str, tgt: str) -> str:
    """<livre sans extension>.<cible> — même convention que traduire-livre.py."""
    return f"{os.path.splitext(book)[0]}.{tgt}"


def read_job(book: str, tgt: str) -> dict:
    try:
        with open(job_base(book, tgt) + ".job.json", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def job_locked(book: str, tgt: str) -> bool:
    """Un processus vivant traduit-il ce livre (verrou .lock) ?"""
    try:
        with open(job_base(book, tgt) + ".lock", encoding="utf-8") as fh:
            pid = int(fh.read().strip() or 0)
    except (OSError, ValueError):
        return False
    return pid_alive(pid)


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, pid)
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


def request_pause(book: str, tgt: str) -> bool:
    try:
        with open(job_base(book, tgt) + ".pause", "w", encoding="utf-8") as fh:
            fh.write("pause\n")
        return True
    except OSError:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# SCRIPT DE TRADUCTION
# ═══════════════════════════════════════════════════════════════════════════════

def script_path() -> str | None:
    candidates = [
        os.path.join(bootstrap.BASE_DIR, SCRIPT_NAME),
        # Exécution depuis les sources : le script est à côté de main.py.
        os.path.join(os.path.dirname(os.path.abspath(__file__)), SCRIPT_NAME),
    ]
    return next((p for p in candidates if os.path.isfile(p)), None)


_MODULE = None
_MODULE_LOCK = threading.Lock()


def _book_module():
    global _MODULE
    with _MODULE_LOCK:
        if _MODULE is None:
            path = script_path()
            if not path:
                raise RuntimeError(f"{SCRIPT_NAME} introuvable à côté de "
                                   f"l'application")
            spec = importlib.util.spec_from_file_location("traduire_livre", path)
            mod = importlib.util.module_from_spec(spec)
            saved = sys.stdout
            try:
                spec.loader.exec_module(mod)
            finally:
                sys.stdout = saved     # le script reconfigure stdout à l'import
            _MODULE = mod
        return _MODULE


class _MemCache:
    """Cache en mémoire (Texte 2 n'a pas besoin de reprise sur disque)."""

    def __init__(self) -> None:
        self.data: dict = {}

    def get(self, key, p):
        return self.data.get((key, p))

    def put(self, key, p, value) -> None:
        self.data[(key, p)] = value

    def close(self) -> None:
        pass


_CLIENTS: dict = {}


def translate_text(text: str, src: str, tgt: str, settings: dict) -> str:
    """
    Traduit *text* via le serveur local, paragraphe par paragraphe groupés,
    avec les passes réglées. Lève RuntimeError(message lisible) en cas
    d'échec (serveur absent, requests manquant…).
    """
    mod = _book_module()
    try:
        import requests  # noqa: F401  (dépendance de LlamaClient)
    except ImportError:
        raise RuntimeError("le module « requests » est absent du Python portable "
                           "(relancez setup_python.sh ou setup_python.bat)")

    url, model = settings.get("url", ""), settings.get("model", "")
    key = (server_root(url), model)
    client = _CLIENTS.get(key)
    try:
        if client is None:
            client = mod.LlamaClient(url, model, "auto")
            client.probe(wait_loading=30)
            _CLIENTS[key] = client
        cap = max(600, int((client.n_ctx * 0.85 - 400) / 1.3))
        max_chars = max(300, min(int(settings.get("max_chars", 2500)), cap))
        passes = min(max(int(settings.get("passes", 2)), 1), 3)
        engine = mod.Engine(client, _MemCache(), src, tgt, passes, [])
        tr = mod.Translator(engine, max_chars)

        paras = [mod.PlainSeg("p", p.strip())
                 for p in re.split(r"\n[ \t]*\n", text) if p.strip()]
        segs = [p.segment() for p in paras]
        for unit in mod.group_units(segs, max_chars):
            tr.unit(unit)
    except mod.ServerError as exc:
        _CLIENTS.pop(key, None)          # re-sonder au prochain essai
        raise RuntimeError(str(exc))
    return "\n\n".join(p.out if p.out is not None else p.text for p in paras)
