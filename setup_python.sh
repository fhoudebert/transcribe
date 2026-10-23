#!/usr/bin/env bash
# ==============================================================================
#  setup_python.sh — Python portable de transcribe / truchement (Linux)
#
#  Installe un CPython COMPLET et DÉPLAÇABLE (python-build-standalone, build
#  « stripped », Python 3.12.15) dans build/python/linux, puis les paquets de
#  requirements.txt DIRECTEMENT dedans (pas de venv) et les paquets de langues
#  Argos Translate dans build/argos-data/packages.
#
#  Contrairement à l'ancien venv (build/python/venv), il ne dépend PAS du
#  Python du système : la clé fonctionne sur n'importe quel Linux x86-64, sans
#  python3 installé, et le dossier peut être déplacé ou copié tel quel.
#  Windows a sa propre copie (setup_python.bat → build\python\windows) ; les
#  deux cohabitent sur la même clé, les paquets Argos sont partagés.
#
#  Compatible exFAT / FAT32 : extraction sur le disque local, puis
#    - liens symboliques supprimés (python3 → python3.12, etc.) : ces systèmes
#      de fichiers ne les acceptent pas, et ils ne font que donner un second
#      nom à des fichiers présents. L'interpréteur est donc bin/python3.12 ;
#    - share/terminfo supprimé (noms ne différant que par la casse, N/ et n/,
#      impossibles sur exFAT ; seul curses le lit), share/man aussi.
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
DEST="$ROOT/build/python/linux"
PY="$DEST/bin/python3.12"
ARGOS_DATA_DIR="$ROOT/build/argos-data/packages"

# Isolation : ni le site utilisateur (~/.local/lib/python3.12) ni un
# PYTHONPATH/PYTHONHOME hérité ne doivent se mêler de l'installation.
unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1 PIP_USER=0

echo "📁 Racine de l'application : $ROOT"

[ "$FORCE" = 1 ] && rm -rf "$DEST"
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

if ! "$PY" -c "pass" 2>/dev/null; then
    echo "❌ $PY ne peut pas s'exécuter." >&2
    echo "   La clé est probablement montée avec l'option 'noexec'. Remontez-la :" >&2
    echo "     sudo mount -o remount,exec \"\$(findmnt -no TARGET -T '$ROOT')\"" >&2
    exit 1
fi

REQ=""
for candidate in "$ROOT/build/python/requirements.txt" "$ROOT/requirements.txt"; do
    [ -f "$candidate" ] && REQ="$candidate" && break
done
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
"$PY" -c "import sys, tkinter, argostranslate.translate, ctranslate2, fitz, requests; \
print('Python', sys.version.split()[0], '- Tk', tkinter.TkVersion, '- ctranslate2', ctranslate2.__version__)"

if [ -d "$ROOT/build/python/venv" ]; then
    echo "ℹ️  L'ancien venv build/python/venv n'est plus utilisé : il peut être supprimé."
fi
echo "✅ Python portable prêt : build/python/linux"
