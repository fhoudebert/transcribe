#!/bin/bash
# ============================================================
# audio2srt — Audio -> SRT (Whisper CLI wrapper)
#
# Usage :
#   audio2srt <fichier> [model] [src_lang|auto] [target_lang]
#
# Ex :
#   audio2srt file.wav large auto fr
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FFMPEG_BIN="$SCRIPT_DIR/build/ffmpeg/bin/ffmpeg"
WHISPER_BIN="$SCRIPT_DIR/build/whisper/whisper-cli"
WHISPER_DIR="$SCRIPT_DIR/build/whisper"

INPUT="${1:-}"
MODEL_NAME="${2:-large}"
SRC_LANG="${3:-auto}"     # auto | fr | en | etc
TARGET_LANG="${4:-}"      # fr | en | etc

MODEL="$WHISPER_DIR/models/ggml-${MODEL_NAME}.bin"

if [ -z "$INPUT" ]; then
  echo "Usage: audio2srt <file> [model] [src_lang|auto] [target_lang]"
  exit 1
fi

if [ ! -f "$INPUT" ]; then
  echo "[ERREUR] Fichier introuvable: $INPUT"
  exit 1
fi

if [ ! -f "$MODEL" ]; then
  echo "[ERREUR] Modèle introuvable: $MODEL"
  exit 1
fi

DIR="$(cd "$(dirname "$INPUT")" && pwd)"
BASE_NAME="$(basename "${INPUT%.*}")"
BASE_FULL="$DIR/$BASE_NAME"

WAV_FILE="$BASE_FULL.wav"
SRT_FILE="$BASE_FULL.srt"

echo "Fichier   : $INPUT"
echo "Modèle    : $MODEL_NAME"
echo "Lang src  : $SRC_LANG"
echo "Lang cible: $TARGET_LANG"

# ── 1. WAV conversion ────────────────────────────────────────
echo ""
echo "=== Extraction audio ==="

"$FFMPEG_BIN" -y \
  -i "$INPUT" \
  -ar 16000 \
  -ac 1 \
  -c:a pcm_s16le \
  "$WAV_FILE"

# ── 2. Build whisper command ────────────────────────────────
CMD=(
  "$WHISPER_BIN"
  -m "$MODEL"
  -f "$WAV_FILE"
  -osrt
)

# langue source
if [ "$SRC_LANG" != "auto" ]; then
  CMD+=(-l "$SRC_LANG")
fi

# traduction si langue cible = en
if [ "$TARGET_LANG" = "en" ]; then
  CMD+=(-tr)
fi

echo ""
echo "=== Whisper ==="
echo "Commande: ${CMD[*]}"

"${CMD[@]}"

# ── 3. Move output ──────────────────────────────────────────
if [ -f "$DIR/$BASE_NAME.srt" ]; then
  mv "$DIR/$BASE_NAME.srt" "$SRT_FILE"
fi

"$SCRIPT_DIR/build/python/venv/bin/python" "$SCRIPT_DIR/nettoyer-srt.py" "$SRT_FILE"
echo ""
echo "Sous-titres générés : $SRT_FILE"
