#!/usr/bin/env bash
set -Eeuo pipefail

ARGOS_BIN="${ARGOS_BIN:-build/python/venv/bin/argos-translate}"

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
    "$ARGOS_BIN" \
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
