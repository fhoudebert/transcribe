"""
tool_check.py — vérifie que ffmpeg, ffprobe et yt-dlp sont utilisables.

Un binaire « présent » n'est pas forcément utilisable : droit d'exécution
perdu à la copie, clé montée en « noexec », version d'un autre système ou
d'une autre architecture (clé préparée sur un PC x86-64 puis branchée sur un
arm64, .exe sous Linux…), téléchargement tronqué, bibliothèque ou DLL
absente. Sans diagnostic, l'utilisateur ne voit qu'un code d'erreur ou un
traitement qui échoue sans raison apparente.

check(name, path) lance « <outil> -version » (« --version » pour yt-dlp) et
renvoie None si tout va bien, sinon un message explicite et traduit : cause
probable + remède. Les succès sont mémorisés (chemin, taille, date) : l'essai
n'est refait que si le fichier change.
"""

from __future__ import annotations

import errno
import os
import platform
import subprocess
import sys

from app_config import IS_WINDOWS, NO_WINDOW
from i18n import t

_OK: dict[str, tuple] = {}

# Codes de sortie Windows (NTSTATUS) en entier non signé / signé
_WIN_DLL_NOT_FOUND = (0xC0000135, -1073741515)   # DLL absente
_WIN_ENTRY_POINT   = (0xC0000139, -1073741511)   # DLL d'une autre version
_WIN_BAD_IMAGE     = (0xC000007B, -1073741701)   # 32/64 bits mélangés


def _sig(path: str):
    st = os.stat(path)
    return (st.st_size, st.st_mtime_ns)


def _mount_point(path: str) -> str:
    p = os.path.dirname(os.path.abspath(path))
    while not os.path.ismount(p):
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return p


def _quarantined(path: str) -> bool:
    try:
        return subprocess.run(["xattr", "-p", "com.apple.quarantine", path],
                              capture_output=True).returncode == 0
    except OSError:
        return False


def _app_root(path: str) -> str:
    """Racine de l'application : le dossier qui contient build/."""
    p = os.path.abspath(path)
    while True:
        parent = os.path.dirname(p)
        if os.path.basename(p) == "build" or parent == p:
            return parent
        p = parent


def _system() -> str:
    return f"{platform.system()} {platform.machine()}"


def _last_line(text: str) -> str:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return lines[-1] if lines else ""


def _fix(name: str, path: str) -> str:
    """Remède commun : réinstaller via setupPython_and_download."""
    folder = os.path.dirname(path)
    if name in ("ffmpeg", "ffprobe"):
        folder = os.path.dirname(folder)            # build/ffmpeg
    script = "setupPython_and_download." + ("bat" if IS_WINDOWS else "sh")
    msg = t("tool_fix", folder=folder, script=script)
    if name == "yt-dlp":
        msg += "\n" + t("tool_fix_ytdlp")
    return msg


def check(name: str, path: str, timeout: int = 20) -> str | None:
    """None si l'outil démarre, sinon un message d'erreur explicite."""
    if not os.path.isfile(path):
        return t("tool_missing", name=name, path=path) + _fix(name, path)

    try:
        sig = _sig(path)
    except OSError:
        sig = None
    if sig is not None and _OK.get(path) == sig:
        return None

    # Droit d'exécution (Linux) : bit x absent, ou clé montée « noexec »
    if not IS_WINDOWS and not os.access(path, os.X_OK):
        noexec = False
        try:                        # os.ST_NOEXEC : Linux seulement
            noexec = bool(os.statvfs(path).f_flag & getattr(os, "ST_NOEXEC", 0))
        except OSError:
            pass
        if noexec:
            return t("tool_noexec_mount", name=name, path=path,
                     mount=_mount_point(path))
        return t("tool_not_exec", name=name, path=path)

    # macOS : fichier marqué « téléchargé d'Internet » (archive ouverte depuis
    # le navigateur) → Gatekeeper refuse de le lancer, ou le tue (SIGKILL)
    if sys.platform == "darwin" and _quarantined(path):
        return t("tool_quarantine", name=name, path=path, root=_app_root(path))

    arg = "--version" if name == "yt-dlp" else "-version"
    try:
        r = subprocess.run([path, arg], capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           creationflags=NO_WINDOW, timeout=timeout)
    except subprocess.TimeoutExpired:
        return t("tool_timeout", name=name, path=path, s=timeout)
    except OSError as e:
        bad_format = (
            e.errno == errno.ENOEXEC
            or getattr(e, "winerror", None) in (193, 216)
            # fichier présent mais « introuvable » : c'est son chargeur
            # (ld-linux…) qui manque → binaire d'un autre système
            or isinstance(e, FileNotFoundError))
        if bad_format:
            return (t("tool_bad_format", name=name, path=path,
                      system=_system()) + _fix(name, path))
        if isinstance(e, PermissionError):
            return t("tool_not_exec", name=name, path=path)
        return (t("tool_fails", name=name, path=path, code="—",
                  detail=str(e)) + _fix(name, path))

    if r.returncode != 0:
        code = r.returncode
        detail = _last_line(r.stderr) or _last_line(r.stdout)
        if IS_WINDOWS and code in _WIN_DLL_NOT_FOUND + _WIN_ENTRY_POINT:
            return t("tool_dll", name=name, path=path) + _fix(name, path)
        if IS_WINDOWS and code in _WIN_BAD_IMAGE:
            return (t("tool_bad_format", name=name, path=path,
                      system=_system()) + _fix(name, path))
        if sys.platform == "darwin" and code == -9 and not detail:
            # SIGKILL sans un mot : signature refusée par macOS
            return t("tool_mac_killed", name=name, path=path) + _fix(name, path)
        if not IS_WINDOWS and code < 0:             # tué par un signal
            detail = detail or t("tool_signal", sig=-code)
        shown = (hex(code & 0xFFFFFFFF)
                 if IS_WINDOWS and (code < 0 or code > 0xFFFF) else code)
        return (t("tool_fails", name=name, path=path, code=shown,
                  detail=detail or "—") + _fix(name, path))

    if sig is not None:
        _OK[path] = sig
    return None
