#!/bin/bash
# ==============================================================================
#  setup_venv_lang.sh — Prépare l'environnement Python portable + langues
#
#  Conçu pour une installation sur clé USB (exFAT/FAT32/NTFS inclus) :
#
#    • venv créé avec --copies : AUCUN lien symbolique. Les symlinks d'un
#      venv classique ne survivent ni à exFAT (qui ne les supporte pas),
#      ni à une copie sous Windows — c'était la cause première des erreurs
#      NO_VENV_PYTHON / "argostranslate n'est pas installé" diagnostiquées
#      par bootstrap.py. On supprime la classe de bugs à la racine.
#
#    • ARGOS_PACKAGES_DIR pointé vers build/argos-data/packages AVANT
#      l'installation des paquets de langues : ils sont écrits directement
#      sur la clé, pas dans le profil utilisateur (~/.local/share/…), et
#      l'application les retrouve depuis n'importe quelle machine/compte.
#
#  Le script peut être lancé depuis la racine de l'application OU depuis
#  build/python : il détecte sa position.
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Racine de l'application (dossier contenant build/)
if [ -d "$SCRIPT_DIR/build" ]; then
    APP_ROOT="$SCRIPT_DIR"                       # script à la racine
else
    APP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"  # script dans build/python
fi

VENV_DIR="$APP_ROOT/build/python/venv"
ARGOS_DATA_DIR="$APP_ROOT/build/argos-data/packages"

echo "📁 Racine de l'application : $APP_ROOT"

echo "🧹 (optionnel) suppression de l'ancien venv..."
rm -rf "$VENV_DIR"

echo "📦 Création du virtualenv (mode --copies : sans liens symboliques,"
echo "   compatible exFAT / FAT32 / NTFS / copie Windows)..."
#
# PIÈGE exFAT : même avec --copies, le module venv de CPython crée TOUJOURS
# un lien symbolique lib64 → lib sur Linux 64 bits (Lib/venv/__init__.py,
# issue 21197) — impossible sur exFAT/FAT32, d'où :
#     Error: [Errno 1] Operation not permitted: 'lib' -> '.../venv/lib64'
# Mais cette création est gardée par `if not os.path.exists(link_path)`
# (issue 21643) : en pré-créant lib64 comme VRAI dossier, venv saute le
# symlink. Sur Debian/Ubuntu (site-packages sous lib/), lib64 reste un
# dossier vide inoffensif ; sur Fedora/openSUSE (platlib = lib64/), pip y
# installe directement — cohérent dans les deux cas, et bootstrap.py
# scanne de toute façon lib/ ET lib64/.
mkdir -p "$VENV_DIR/lib64"
python3 -m venv --copies "$VENV_DIR"

# Vérification : sur une clé montée avec l'option noexec, le python copié
# ne peut pas s'exécuter — mieux vaut un message clair maintenant qu'un
# échec obscur plus tard.
if ! "$VENV_DIR/bin/python" -c "pass" 2>/dev/null; then
    echo "❌ $VENV_DIR/bin/python ne peut pas s'exécuter."
    echo "   La clé est probablement montée avec l'option 'noexec'."
    echo "   Remontez-la avec exec, par exemple :"
    echo "     sudo mount -o remount,exec \"\$(findmnt -no TARGET -T '$APP_ROOT')\""
    exit 1
fi

echo "🔌 Activation du virtualenv..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "⬆️  Mise à jour de pip..."
pip install --upgrade pip

REQ=""
for candidate in "$APP_ROOT/build/python/requirements.txt" "$APP_ROOT/requirements.txt"; do
    [ -f "$candidate" ] && REQ="$candidate" && break
done
if [ -n "$REQ" ]; then
    echo "📥 Installation des dépendances Python ($REQ)..."
    pip install -r "$REQ"
else
    echo "⚠️  Aucun requirements.txt trouvé"
fi

echo "🌐 Installation des paquets de langues Argos Translate"
echo "   → directement dans $ARGOS_DATA_DIR (autonome sur la clé)"
echo "   Veuillez patienter, c'est volumineux !"
mkdir -p "$ARGOS_DATA_DIR"
export ARGOS_PACKAGES_DIR="$ARGOS_DATA_DIR"
export ARGOS_TRANSLATE_PACKAGE_DIR="$ARGOS_DATA_DIR"   # alias legacy

if ! argospm list | grep -q "translate"; then
    argospm update
    argospm install translate
else
    echo "   Paquets déjà présents, rien à faire."
fi

echo "✅ Environnement prêt"
echo "👉 Activation manuelle : source $VENV_DIR/bin/activate"
