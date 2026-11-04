#!/usr/bin/env bash
# ==============================================================================
#  build_whisper.sh — compile whisper-cli (whisper.cpp) pour Linux x86-64/arm64
#
#  whisper.cpp ne publie pas de binaire Linux : ce script le compile et
#  dépose dans build/whisper/ le programme whisper-cli et ses bibliothèques
#  (libwhisper, libggml*), trouvées à côté de lui (RPATH $ORIGIN).
#
#  Portable d'une machine à l'autre de la même architecture :
#    • GGML_NATIVE=OFF : pas d'optimisation propre au processeur de
#      compilation (sinon -march=native : plantage sur un processeur plus
#      ancien) ;
#    • GGML_BACKEND_DL + GGML_CPU_ALL_VARIANTS : une bibliothèque ggml-cpu par
#      génération de processeur (SSE/AVX/AVX2/AVX-512 ; NEON, dotprod, SVE…),
#      la meilleure est choisie au lancement ;
#    • GGML_OPENMP=OFF : pas de dépendance à libgomp (ggml a ses threads).
#
#  arm64 : la variante la plus récente de ggml exige -march=armv9.2-a…+sme,
#  inconnu de gcc < 14 (gcc 11 d'Ubuntu 22.04 : « unknown value for
#  -march »). Le script vérifie le compilateur et prend sinon un clang récent
#  (clang-15 et plus, paquet clang-15 sur Ubuntu 22.04).
#
#  Usage : tools/whisper/build_whisper.sh [dossier_de_sortie]
#          (défaut : build/whisper à la racine de l'application)
#  Prérequis : git cmake g++ make ; arm64 : gcc ≥ 14 ou clang ≥ 15
# ==============================================================================
set -Eeuo pipefail
WHISPER_TAG="v1.8.6"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/build/whisper}"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT

# arm64 : compilateur capable de la variante armv9.2 (SME) de ggml
if [ "$(uname -m)" = aarch64 ] || [ "$(uname -m)" = arm64 ]; then
    ARM_MARCH="armv9.2-a+dotprod+fp16+sve+i8mm+sve2+sme"
    accepts() { echo 'int main(void){return 0;}' | "$1" -march="$ARM_MARCH" -x c -c -o /dev/null - 2>/dev/null; }
    if ! accepts "${CC:-cc}"; then
        for v in 20 19 18 17 16 15; do
            if command -v "clang-$v" >/dev/null && accepts "clang-$v"; then
                export CC="clang-$v" CXX="clang++-$v"; break
            fi
        done
        accepts "${CC:-cc}" || { echo "❌ aucun compilateur n'accepte -march=$ARM_MARCH :" \
            "installez clang-15 (ou plus) ou gcc ≥ 14" >&2; exit 1; }
    fi
    echo "Compilateur : ${CC:-cc}"
fi

git -c advice.detachedHead=false clone -q --depth 1 --branch "$WHISPER_TAG" https://github.com/ggml-org/whisper.cpp.git "$W/src"
cmake -S "$W/src" -B "$W/b" -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON -DGGML_NATIVE=OFF \
    -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON -DGGML_OPENMP=OFF \
    -DWHISPER_BUILD_TESTS=OFF -DWHISPER_SDL2=OFF -DWHISPER_CURL=OFF \
    -DCMAKE_BUILD_RPATH='$ORIGIN' -DCMAKE_INSTALL_RPATH='$ORIGIN' \
    -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON >/dev/null
cmake --build "$W/b" --target whisper-cli -j"$(nproc)" >/dev/null

mkdir -p "$OUT"
rm -f "$OUT"/whisper-cli "$OUT"/lib*.so*
cp "$W/b/bin/whisper-cli" "$OUT/"
# Bibliothèques en FICHIERS réels (aucun lien symbolique : impossible sur une
# clé exFAT), sous le nom exact que cherche le chargeur :
#   - libwhisper.so.1, libggml.so.0, libggml-base.so.0 (« SONAME ») ;
#   - libggml-cpu-<variante>.so, chargées au lancement par ggml.
find "$W/b" -name "lib*.so.[0-9]" -exec cp -L {} "$OUT/" \;
find "$W/b" -name "libggml-cpu-*.so" -exec cp -L {} "$OUT/" \;
strip --strip-unneeded "$OUT/whisper-cli" "$OUT"/lib*.so* 2>/dev/null || true
chmod +x "$OUT/whisper-cli"
echo "whisper-cli $WHISPER_TAG ($(uname -m)) → $OUT"
ls "$OUT"
