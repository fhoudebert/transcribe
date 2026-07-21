#!/usr/bin/env bash
# ==============================================================================
#  compiler_transcribe.sh — Compile transcribe (PyInstaller, binaire onefile)
#  puis déploie à la racine de l'application : binaire, assets (fusionnés
#  avec ceux de truchement), i18n.
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

echo "🚀 Compilation transcribe..."
cd "$SCRIPT_DIR/transcribe-src"
"$PYI" \
        --onefile \
        --noconfirm \
        --name transcribe \
        --icon=assets/icone.png \
        --add-data "traduire-srt.py:." \
        --add-data "assets:assets" \
        --windowed \
        transcribe.py

# ── Déploiement à la racine ───────────────────────────────────────────────────
# deploy_dir <src> <dest> : fusionne src/ dans dest/ (créé si besoin) SANS
# supprimer ce qui vient d'autres sources (assets/ est partagé entre
# transcribe et truchement). Cas particulier : i18n/.locale mémorise la
# langue choisie par l'utilisateur → copiée uniquement si absente à la
# racine, pour ne pas écraser sa préférence à chaque recompilation.
deploy_dir() {
    local src="$1" dest="$2" f base
    [ -d "$src" ] || return 0
    mkdir -p "$dest"
    for f in "$src"/* "$src"/.[!.]*; do
        [ -e "$f" ] || continue
        base="$(basename "$f")"
        if [ "$base" = ".locale" ] && [ -e "$dest/$base" ]; then
            continue
        fi
        cp -r "$f" "$dest/"
    done
}

echo "📦 Déploiement à la racine de l'application..."
install -m 0755 "$SCRIPT_DIR/transcribe-src/dist/transcribe" "$SCRIPT_DIR/transcribe"
deploy_dir "$SCRIPT_DIR/transcribe-src/assets" "$SCRIPT_DIR/assets"
deploy_dir "$SCRIPT_DIR/transcribe-src/i18n"   "$SCRIPT_DIR/i18n"

echo "🎉 Compilation terminée avec succès : $SCRIPT_DIR/transcribe"
