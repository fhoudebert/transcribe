#!/usr/bin/env bash
# ==============================================================================
#  compiler_truchement.sh — Compile truchement (PyInstaller, binaire onefile)
#
#  ARCHITECTURE : le binaire n'embarque PAS argostranslate/torch/numpy — ces
#  paquets vivent dans le venv de la clé et sont chargés À L'EXÉCUTION par
#  bootstrap.py (injection sys.path). PyInstaller ne peut donc pas déduire
#  leurs besoins par analyse statique de main.py : il faut embarquer la
#  BIBLIOTHÈQUE STANDARD COMPLÈTE dans le binaire, sinon le premier module
#  stdlib importé par la chaîne argos et absent du gel échoue à l'exécution :
#      ModuleNotFoundError: No module named 'pickletools'
#  (pickletools aujourd'hui, un autre demain : on inclut tout, ~8 Mo.)
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/build/python/venv"
PYI="$VENV/bin/pyinstaller"

echo "🚀 Activation de l'environnement Python..."
if [ ! -x "$VENV/bin/python" ]; then
    echo "❌ venv introuvable : $VENV — lancez d'abord setupPython_and_download.sh"
    exit 1
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

if [ ! -x "$PYI" ]; then
    echo "📥 PyInstaller absent du venv, installation..."
    pip install pyinstaller
fi
echo "✅ Environnement Python prêt."

# ── Stdlib complète en imports cachés ─────────────────────────────────────────
# Modules privés (_*) exclus : ils suivent automatiquement leurs modules
# publics. Exclusions : suites de test et modules interactifs sans objet.
HIDDEN_STDLIB="$("$VENV/bin/python" - <<'PY'
import sys
skip = {"antigravity", "this", "idlelib", "turtledemo", "test", "lib2to3"}
mods = sorted(m for m in sys.stdlib_module_names
              if not m.startswith("_") and m not in skip)
print(" ".join(f"--hidden-import={m}" for m in mods))
PY
)"
echo "📚 Stdlib embarquée : $(echo "$HIDDEN_STDLIB" | wc -w) modules"

echo "🚀 Compilation truchement..."
cd "$SCRIPT_DIR/truchement-src"
# shellcheck disable=SC2086  # HIDDEN_STDLIB doit être éclaté en arguments
"$PYI" \
        --onefile \
        --noconfirm \
        --name truchement \
        --exclude-module matplotlib \
        --exclude-module numpy \
        --exclude-module torch \
        $HIDDEN_STDLIB \
        --icon=assets/dico.png \
        --add-data "assets:assets" \
        --windowed \
        main.py

echo "📦 Installation du binaire à la racine de l'application..."
install -m 0755 "$SCRIPT_DIR/truchement-src/dist/truchement" "$SCRIPT_DIR/truchement"

echo "🎉 Compilation terminée avec succès : $SCRIPT_DIR/truchement"
