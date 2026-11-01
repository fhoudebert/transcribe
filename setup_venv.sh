#!/usr/bin/env bash
# ==============================================================================
#  setup_venv.sh — conservé pour compatibilité, renvoie vers setup_python.sh.
#
#  L'ancien venv (créé avec le Python du système) est remplacé par un Python
#  portable complet (python-build-standalone 3.12.15) installé au même endroit,
#  build/python/venv, qui ne dépend plus du Python de la machine.
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# script éventuellement copié dans build/python : racine deux niveaux au-dessus
[ -f "$SCRIPT_DIR/setup_python.sh" ] || SCRIPT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
exec bash "$SCRIPT_DIR/setup_python.sh" --no-lang "$@"
