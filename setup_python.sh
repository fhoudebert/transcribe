#!/usr/bin/env bash
# ==============================================================================
#  setup_python.sh — Python portable de transcribe / truchement (Linux)
#
#  Installe un CPython COMPLET et DÉPLAÇABLE (python-build-standalone, build
#  « stripped », Python 3.12.15) dans build/python/venv — l'emplacement
#  historique de l'environnement Python de la clé —, puis les paquets de
#  requirements.txt DIRECTEMENT dedans et les paquets de langues Argos
#  Translate dans build/argos-data/packages.
#
#  Malgré son nom, build/python/venv n'est plus un venv : c'est un Python
#  complet, qui ne dépend PAS du Python du système (un vrai venv retient le
#  chemin absolu de son Python de base, et casse dès que la clé est montée
#  ailleurs). La clé fonctionne sur n'importe quel Linux x86-64, sans python3
#  installé, et le dossier peut être déplacé ou copié tel quel.
#  Un ancien venv créé avec le Python système est remplacé ; une installation
#  faite dans build/python/linux (version précédente de ce script) est
#  déplacée ici. Windows a sa propre copie (setup_python.bat →
#  build\python\venv-windows) ; les deux cohabitent sur la même clé, les
#  paquets Argos sont partagés.
#
#  Compatible exFAT / FAT32 : extraction sur le disque local, puis
#    - liens symboliques supprimés (python3 → python3.12, etc.) : ces systèmes
#      de fichiers ne les acceptent pas, et ils ne font que donner un second
#      nom à des fichiers présents. L'interpréteur est bin/python3.12, et
#      bin/python / bin/python3 sont recréés en petits scripts relais (comme
#      dans l'ancien venv) ;
#    - share/terminfo supprimé (noms ne différant que par la casse, N/ et n/,
#      impossibles sur exFAT ; seul curses le lit), share/man aussi.
#
#  Le Tk fourni est remplacé par le même Tk compilé AVEC Xft (tools/tk-xft) :
#  sans cela, l'interface n'a accès qu'aux polices bitmap X11 (« fixed »).
#
#  Les scripts que pip pose dans bin/ (argospm, pyinstaller…) portent un
#  shebang ABSOLU, donc non déplaçable : on passe toujours par
#  « bin/python3.12 -m … » ou « -c », jamais par ces scripts.
#
#  Relançable sans risque : un Python déjà installé est conservé, les paquets
#  sont ramenés aux versions du gel.
#    --force    réinstalle Python
#    --no-lang  n'installe pas les paquets de langues Argos
# ==============================================================================

set -Eeuo pipefail

PBS_TAG="20261013"
PY_VERSION="3.12.15"
case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)
        TRIPLE=x86_64-unknown-linux-gnu
        SHA256="178d3d83b6e8e99285a65d3fce9c16b87952cc5efdb4d1a0e3ff3be18ff0fc9c" ;;
    *)
        echo "❌ système non pris en charge : $(uname -s) $(uname -m) (Linux x86-64)" >&2
        exit 1 ;;
esac
ASSET="cpython-${PY_VERSION}+${PBS_TAG}-${TRIPLE}-install_only_stripped.tar.gz"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${ASSET}"

FORCE=0; LANGS=1
for arg in "$@"; do
    case "$arg" in
        --force)   FORCE=1 ;;
        --no-lang) LANGS=0 ;;
        *) echo "option inconnue : $arg (--force, --no-lang)" >&2; exit 2 ;;
    esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$ROOT/build/python/venv"
OLD_LINUX="$ROOT/build/python/linux"
PY="$DEST/bin/python3.12"
ARGOS_DATA_DIR="$ROOT/build/argos-data/packages"

# Isolation : ni le site utilisateur (~/.local/lib/python3.12) ni un
# PYTHONPATH/PYTHONHOME hérité ne doivent se mêler de l'installation.
unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1 PIP_USER=0

echo "📁 Racine de l'application : $ROOT"

[ "$FORCE" = 1 ] && rm -rf "$DEST" "$OLD_LINUX"
# Ancien venv créé avec le Python du système (pyvenv.cfg) : c'est justement
# la dépendance qu'on supprime — il est remplacé par le Python portable.
if [ -f "$DEST/pyvenv.cfg" ]; then
    echo "[1/4] Ancien venv (Python du système) trouvé dans build/python/venv : remplacé"
    rm -rf "$DEST"
fi
# Python portable installé par la version précédente dans build/python/linux :
# déplacé (même clé, renommage instantané) plutôt que retéléchargé.
if [ ! -d "$DEST" ] && [ -f "$OLD_LINUX/.complete" ]; then
    echo "[1/4] Python portable déplacé de build/python/linux vers build/python/venv"
    mv "$OLD_LINUX" "$DEST"
fi
# Un Python n'est conservé qu'avec le marqueur d'installation terminée :
# une installation interrompue (fichiers manquants) est refaite.
if [ -d "$DEST" ] && [ ! -f "$DEST/.complete" ]; then
    echo "[1/4] Python incomplet trouvé, réinstallation"
    rm -rf "$DEST"
fi

if [ ! -x "$PY" ]; then
    command -v curl >/dev/null || { echo "❌ curl est nécessaire" >&2; exit 1; }
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    echo "[1/4] Téléchargement de Python $PY_VERSION ($ASSET)"
    curl -fL --retry 3 -o "$TMP/py.tar.gz" "$URL"
    echo "$SHA256  $TMP/py.tar.gz" | sha256sum -c --quiet - \
        || { echo "❌ somme de contrôle incorrecte, téléchargement refusé" >&2; exit 1; }
    tar -xzf "$TMP/py.tar.gz" -C "$TMP"
    find "$TMP/python" -type l -delete
    rm -rf "$TMP/python/share/terminfo" "$TMP/python/share/man"
    # toute autre paire de noms ne différant que par la casse casserait la copie
    collide="$("$TMP/python/bin/python3.12" - "$TMP/python" <<'PYEOF'
import os, sys
seen = set()
for d, dirs, files in os.walk(sys.argv[1]):
    for n in dirs + files:
        p = os.path.join(d, n)
        if p.lower() in seen:
            print(p)
        seen.add(p.lower())
PYEOF
)"
    if [ -n "$collide" ]; then
        echo "❌ noms ne différant que par la casse, impossibles sur exFAT/FAT32 :" >&2
        echo "$collide" | head -5 >&2
        exit 1
    fi
    mkdir -p "$DEST"
    cp -r "$TMP/python/." "$DEST/"
    "$PY" -c "import encodings, ssl, sqlite3, tkinter, pip._internal.cli.main" \
        || { echo "❌ le Python copié est incomplet (clé pleine ?) ; relancez" >&2; rm -rf "$DEST"; exit 1; }
    echo ok > "$DEST/.complete"
else
    echo "[1/4] Python déjà présent : $("$PY" --version)"
fi

# bin/python et bin/python3, comme dans l'ancien venv : petits scripts relais
# (pas de lien symbolique, impossible sur exFAT) vers bin/python3.12.
for name in python python3; do
    if [ ! -e "$DEST/bin/$name" ]; then
        printf '#!/bin/sh\nexec "$(dirname "$0")/python3.12" "$@"\n' > "$DEST/bin/$name"
        chmod +x "$DEST/bin/$name" 2>/dev/null || true
    fi
done

if ! "$PY" -c "pass" 2>/dev/null; then
    echo "❌ $PY ne peut pas s'exécuter." >&2
    echo "   La clé est probablement montée avec l'option 'noexec'. Remontez-la :" >&2
    echo "     sudo mount -o remount,exec \"\$(findmnt -no TARGET -T '$ROOT')\"" >&2
    exit 1
fi

# requirements.txt de la racine (celui du dépôt, à jour) EN PRIORITÉ ; la
# copie historique build/python/requirements.txt n'est qu'un repli : une
# ancienne copie oubliée là masquait les paquets ajoutés depuis (py3langid…).
# ── Tk avec Xft : polices du système ─────────────────────────────────────────
# Le Tk de python-build-standalone est compilé sans Xft : il ne voit que les
# polices bitmap X11 (« fixed »). tools/tk-xft/libtcl9tk9.0.so est le MÊME Tk
# (9.0.4) compilé avec Xft (recette : tools/tk-xft/build_tk_xft.sh) ; il le
# remplace, l'original étant gardé dans lib/tk-x11/. Installé seulement si la
# version correspond, la somme est bonne et la bibliothèque se charge ici.
TK_XFT="$ROOT/tools/tk-xft/libtcl9tk9.0.so"
TK_XFT_SHA256="9b91fb6fbff4de3d0eea9ca97297ab50097916c69a524f3da8df0d081cceb536"
TK_LIB="$DEST/lib/libtcl9tk9.0.so"
TK_ORIG="$DEST/lib/tk-x11/libtcl9tk9.0.so"
if [ -f "$TK_XFT" ] && ! cmp -s "$TK_XFT" "$TK_LIB"; then
    tclver="$("$PY" -c 'import tkinter; print(tkinter.Tcl().eval("info patchlevel"))' 2>/dev/null || true)"
    if [ "$tclver" != "9.0.4" ]; then
        echo "[1/4] ℹ️  Tcl/Tk $tclver : tools/tk-xft (9.0.4) ne correspond pas, polices X11 conservées"
    elif ! echo "$TK_XFT_SHA256  $TK_XFT" | sha256sum -c --quiet - 2>/dev/null; then
        echo "[1/4] ⚠️  tools/tk-xft/libtcl9tk9.0.so : somme de contrôle incorrecte, ignoré"
    elif ldd "$TK_XFT" 2>/dev/null | grep -q "not found"; then
        echo "[1/4] ⚠️  Tk avec Xft non installé, bibliothèques absentes de ce système :"
        ldd "$TK_XFT" | grep "not found" | sed 's/^/        /'
        echo "      (paquet libxft2 / libXft) — polices bitmap X11 conservées"
    else
        mkdir -p "$(dirname "$TK_ORIG")"
        [ -f "$TK_ORIG" ] || cp "$TK_LIB" "$TK_ORIG"
        cp "$TK_XFT" "$TK_LIB"
        if "$PY" -c "import _tkinter" 2>/dev/null; then
            echo "[1/4] Tk avec Xft installé : l'interface utilise les polices du système"
        else
            cp "$TK_ORIG" "$TK_LIB"
            echo "[1/4] ⚠️  Tk avec Xft ne se charge pas ici : Tk d'origine restauré"
        fi
    fi
fi

REQ=""
for candidate in "$ROOT/requirements.txt" "$ROOT/build/python/requirements.txt"; do
    [ -f "$candidate" ] && REQ="$candidate" && break
done
OLD_REQ="$ROOT/build/python/requirements.txt"
if [ "$REQ" = "$ROOT/requirements.txt" ] && [ -f "$OLD_REQ" ] \
        && ! cmp -s "$REQ" "$OLD_REQ"; then
    echo "      ℹ️  build/python/requirements.txt (ancienne copie, différente) est ignoré :"
    echo "         seul requirements.txt à la racine fait foi ; vous pouvez le supprimer."
fi
if [ -n "$REQ" ]; then
    echo "[2/4] Installation des paquets ($REQ) — torch est volumineux, patience"
    "$PY" -m pip install --disable-pip-version-check --no-warn-script-location \
        --root-user-action=ignore -q -r "$REQ"
else
    echo "[2/4] ⚠️  aucun requirements.txt trouvé"
fi

# argospm sans le script bin/argospm (shebang absolu, cf. en-tête)
argospm() {
    "$PY" -c 'import sys; from argostranslate.argospm import main; sys.argv[0] = "argospm"; sys.exit(main())' "$@"
}
if [ "$LANGS" = 1 ]; then
    echo "[3/4] Paquets de langues Argos Translate → $ARGOS_DATA_DIR"
    mkdir -p "$ARGOS_DATA_DIR"
    export ARGOS_PACKAGES_DIR="$ARGOS_DATA_DIR"
    export ARGOS_TRANSLATE_PACKAGE_DIR="$ARGOS_DATA_DIR"   # alias legacy
    if ! argospm list | grep -q "translate"; then
        echo "      volumineux, patience..."
        argospm update
        argospm install translate
    else
        echo "      paquets déjà présents, rien à faire."
    fi
else
    echo "[3/4] Paquets de langues ignorés (--no-lang)"
fi

echo "[4/4] Vérification"
"$PY" -c "import sys, tkinter, argostranslate.translate, ctranslate2, fitz, requests, py3langid; \
print('Python', sys.version.split()[0], '- Tk', tkinter.TkVersion, '- ctranslate2', ctranslate2.__version__)"

if [ -f "$OLD_LINUX/.complete" ]; then
    echo "ℹ️  build/python/linux (installation précédente) n'est plus utilisé : il peut être supprimé."
fi
echo "✅ Python portable prêt : build/python/venv"
