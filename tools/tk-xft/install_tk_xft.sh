#!/usr/bin/env bash
# ==============================================================================
#  install_tk_xft.sh <dossier du Python portable> — Tk avec Xft (Linux)
#
#  Le Tk de python-build-standalone est compilé sans Xft : il ne voit que les
#  polices bitmap X11 (« fixed », chasse fixe, sans emoji). libtcl9tk9.0.so,
#  à côté de ce script, est le MÊME Tk (9.0.4) compilé avec Xft (recette :
#  build_tk_xft.sh) : il remplace celui du Python portable, l'original étant
#  gardé dans lib/tk-x11/. L'interface retrouve alors les polices du bureau.
#
#  Appelé par setup_python.sh ET par compiler_transcribe.sh /
#  compiler_truchement.sh : une simple recompilation suffit à l'installer.
#  Sans effet s'il est déjà en place ; installé seulement si la version de Tk
#  correspond, la somme SHA-256 est bonne et la bibliothèque se charge ici.
#  N'échoue jamais : au pire, le Tk d'origine est conservé (avec un message).
# ==============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:?usage : install_tk_xft.sh <dossier du Python portable>}"
PY="$DEST/bin/python3.12"
TK_XFT="$HERE/libtcl9tk9.0.so"
TK_XFT_SHA256="9b91fb6fbff4de3d0eea9ca97297ab50097916c69a524f3da8df0d081cceb536"
TK_LIB="$DEST/lib/libtcl9tk9.0.so"
TK_ORIG="$DEST/lib/tk-x11/libtcl9tk9.0.so"

[ "$(uname -s)" = Linux ] || exit 0
[ -x "$PY" ] && [ -f "$TK_LIB" ] && [ -f "$TK_XFT" ] || exit 0
cmp -s "$TK_XFT" "$TK_LIB" && exit 0          # déjà en place

tclver="$("$PY" -c 'import tkinter; print(tkinter.Tcl().eval("info patchlevel"))' 2>/dev/null || true)"
if [ "$tclver" != "9.0.4" ]; then
    echo "ℹ️  Tcl/Tk ${tclver:-?} : tools/tk-xft (9.0.4) ne correspond pas, polices X11 conservées"
elif ! echo "$TK_XFT_SHA256  $TK_XFT" | sha256sum -c --quiet - 2>/dev/null; then
    echo "⚠️  tools/tk-xft/libtcl9tk9.0.so : somme de contrôle incorrecte, ignoré"
elif ldd "$TK_XFT" 2>/dev/null | grep -q "not found"; then
    echo "⚠️  Tk avec Xft non installé, bibliothèques absentes de ce système :"
    ldd "$TK_XFT" | grep "not found" | sed 's/^/      /'
    echo "   (paquet libxft2 / libXft) — polices bitmap X11 conservées"
else
    mkdir -p "$(dirname "$TK_ORIG")"
    [ -f "$TK_ORIG" ] || cp "$TK_LIB" "$TK_ORIG"
    cp "$TK_XFT" "$TK_LIB"
    if "$PY" -c "import _tkinter" 2>/dev/null; then
        echo "Tk avec Xft installé : l'interface utilise les polices du système"
    else
        cp "$TK_ORIG" "$TK_LIB"
        echo "⚠️  Tk avec Xft ne se charge pas ici : Tk d'origine restauré"
    fi
fi
exit 0
