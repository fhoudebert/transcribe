#!/usr/bin/env bash
set -Eeuo pipefail

# argos-translate : ARGOS_BIN s'il est fourni, sinon le module du Python
# portable de la clé (le script bin/argos-translate qu'installe pip porte un
# shebang absolu, non déplaçable : on ne l'utilise pas).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/build/python/linux/bin/python3.12"
[ -x "$PY" ] || PY="$SCRIPT_DIR/build/python/venv/bin/python"
argos_translate() {
    if [ -n "${ARGOS_BIN:-}" ]; then
        "$ARGOS_BIN" "$@"
    else
        "$PY" -c 'import sys; from argostranslate.cli import main; sys.argv[0] = "argos-translate"; sys.exit(main())' "$@"
    fi
}
if [ -z "${ARGOS_PACKAGES_DIR:-}" ] && [ -d "$SCRIPT_DIR/build/argos-data/packages" ]; then
    export ARGOS_PACKAGES_DIR="$SCRIPT_DIR/build/argos-data/packages"
fi

INPUT="$1"
FROM_LANG="${2:-en}"
TO_LANG="${3:-fr}"

BATCH_SIZE="${BATCH_SIZE:-80}"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

IDS="$TMPDIR/ids.txt"
TIMES="$TMPDIR/times.txt"
TEXT="$TMPDIR/text.txt"
TRANS="$TMPDIR/trans.txt"

# -----------------------
# 1. Extraction SRT (STRICT)
# -----------------------
awk -v ids="$IDS" -v times="$TIMES" -v text="$TEXT" '
BEGIN { RS=""; FS="\n" }
{
    print $1 >> ids
    print $2 >> times

    t=""
    for(i=3;i<=NF;i++) {
        t = t $i
        if(i < NF) t = t " "
    }

    print t >> text
}
' "$INPUT"

# -----------------------
# 2. Traduction batch
# -----------------------
> "$TRANS"

split -l "$BATCH_SIZE" "$TEXT" "$TMPDIR/chunk_"

for f in "$TMPDIR"/chunk_*; do
    argos_translate \
        --from-lang "$FROM_LANG" \
        --to-lang "$TO_LANG" \
        < "$f" >> "$TRANS"
done

# -----------------------
# 3. Reconstruction ULTRA SAFE (index-based)
# -----------------------
mapfile -t IDS_ARR < "$IDS"
mapfile -t TIMES_ARR < "$TIMES"
mapfile -t TRANS_ARR < "$TRANS"

BASE="$(basename "$INPUT" .srt)"
BASE="${BASE%.en}"
BASE="${BASE%.fr}"
BASE="${BASE%.es}"

OUTPUT="${BASE}.${TO_LANG}.srt"

: > "$OUTPUT"

N=${#IDS_ARR[@]}

for ((i=0; i<N; i++)); do
    echo "${IDS_ARR[i]}" >> "$OUTPUT"
    echo "${TIMES_ARR[i]}" >> "$OUTPUT"
    echo "${TRANS_ARR[i]:-}" >> "$OUTPUT"
    echo >> "$OUTPUT"
done

echo "✔ OK -> $OUTPUT"
