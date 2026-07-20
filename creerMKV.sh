#!/bin/bash
# ============================================================
# mkvmux.sh — vidéo + sous-titres FR/EN → MKV
#
# Usage:
#   mkvmux.sh mavideo.mp4
# ============================================================
set -euo pipefail

VIDEO="${1:-}"

if [ -z "$VIDEO" ]; then
  echo "Usage: mkvmux.sh <video.mp4>"
  exit 1
fi

if [ ! -f "$VIDEO" ]; then
  echo "[ERREUR] Vidéo introuvable: $VIDEO"
  exit 1
fi

DIR="$(dirname "$VIDEO")"
BASE="$(basename "${VIDEO%.*}")"

FR_SRT="$DIR/$BASE.fr.srt"
EN_SRT="$DIR/$BASE.en.srt"

OUTPUT="$DIR/$BASE.mkv"

# ── Build ffmpeg command ────────────────────────────────────
CMD=(ffmpeg -y -i "$VIDEO")

HAS_FR=0
HAS_EN=0

if [ -f "$FR_SRT" ]; then
  CMD+=(-i "$FR_SRT")
  HAS_FR=1
  echo "Sous-titre FR trouvé"
fi

if [ -f "$EN_SRT" ]; then
  CMD+=(-i "$EN_SRT")
  HAS_EN=1
  echo "Sous-titre EN trouvé"
fi

# ── Mappings ────────────────────────────────────────────────
CMD+=(-map 0)

if [ "$HAS_FR" -eq 1 ]; then
  CMD+=(-map 1)
fi

if [ "$HAS_EN" -eq 1 ]; then
  if [ "$HAS_FR" -eq 1 ]; then
    CMD+=(-map 2)
  else
    CMD+=(-map 1)
  fi
fi

# ── Codec copy vidéo/audio + sous-titres ────────────────────
CMD+=(
  -c:v copy
  -c:a copy
  -c:s srt
)

# ── Métadonnées langues ─────────────────────────────────────
if [ "$HAS_FR" -eq 1 ]; then
  CMD+=(-metadata:s:s:0 language=fra)
fi

if [ "$HAS_EN" -eq 1 ]; then
  if [ "$HAS_FR" -eq 1 ]; then
    CMD+=(-metadata:s:s:1 language=eng)
  else
    CMD+=(-metadata:s:s:0 language=eng)
  fi
fi

CMD+=("$OUTPUT")

# ── Execution ───────────────────────────────────────────────
echo ""
echo "=== Création MKV ==="
echo "Sortie: $OUTPUT"
echo "Commande: ${CMD[*]}"
echo ""

"${CMD[@]}"

echo ""
echo "✔ MKV créé: $OUTPUT"
