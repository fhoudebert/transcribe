#!/usr/bin/env bash
# ==============================================================================
#  build_tk_xft.sh — recompile libtcl9tk9.0.so (Tk 9.0.4) AVEC Xft
#
#  Pourquoi : le Tk du Python portable (python-build-standalone) est compilé
#  sans Xft sous Linux : il ne voit que les polices bitmap X11 (« fixed »,
#  helvetica 75 dpi…), d'où une interface laide et sans accents lissés.
#  Problème connu en amont (astral-sh/python-build-standalone#740).
#  setup_python.sh remplace donc lib/libtcl9tk9.0.so du Python portable par
#  ce Tk, MÊME VERSION (9.0.4, celle de PBS 20261013), compilé avec Xft :
#  il utilise les polices du système via fontconfig, comme le Tk des
#  distributions.
#
#  Compilé avec zig cc en visant glibc 2.17 (comme PBS) : la bibliothèque
#  fonctionne sur toutes les distributions encore en service. Dépendances
#  ajoutées : libXft.so.2, libfontconfig.so.1, libX11.so.6 (présentes sur tout
#  bureau Linux ; PyInstaller les embarque de toute façon dans les binaires).
#
#  Prérequis (Debian/Ubuntu) : gcc make git libxft-dev libfontconfig-dev
#  libx11-dev patchelf, et pip (pour ziglang). Résultat : ./libtcl9tk9.0.so
#  À refaire seulement si PBS_TAG change la version de Tk (setup_python.sh
#  vérifie la version et n'installe ce Tk que si elle correspond).
# ==============================================================================
set -Eeuo pipefail
TK_TAG="core-9-0-4"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
cd "$W"

python3 -m pip install -q --target "$W/zig" ziglang
ZIG="$W/zig/ziglang/zig"
mkdir sysinc
for d in X11 fontconfig freetype2 ft2build.h; do ln -s "/usr/include/$d" "sysinc/$d"; done
# Seuls les en-têtes X11/fontconfig/freetype du système sont vus : la libc
# vient de zig (glibc 2.17), pas de /usr/include.
printf '#!/bin/sh\nexec %s cc -target x86_64-linux-gnu.2.17 -idirafter %s/sysinc -idirafter %s/sysinc/freetype2 "$@"\n' "$ZIG" "$W" "$W" > zcc
printf '#!/bin/sh\nexec %s ar "$@"\n' "$ZIG" > zar
printf '#!/bin/sh\nexec %s ranlib "$@"\n' "$ZIG" > zranlib
chmod +x zcc zar zranlib

git clone -q --depth 1 --branch "$TK_TAG" https://github.com/tcltk/tcl.git tcl
git clone -q --depth 1 --branch "$TK_TAG" https://github.com/tcltk/tk.git tk

# Tcl : seuls tclConfig.sh et libtclstub.a servent (Tk se lie aux stubs).
(cd tcl/unix && CC="$W/zcc" AR="$W/zar" RANLIB="$W/zranlib" \
    ./configure --disable-zipfs >/dev/null && make -j"$(nproc)" libtclstub.a >/dev/null)

(cd tk/unix && PKG_CONFIG=/bin/false CC="$W/zcc" AR="$W/zar" RANLIB="$W/zranlib" \
    ./configure --with-tcl="$W/tcl/unix" --enable-xft --disable-xss --disable-zipfs \
        --x-includes="$W/sysinc" --x-libraries=/usr/lib/x86_64-linux-gnu >/dev/null \
 && make -j"$(nproc)" libtcl9tk9.0.so >/dev/null)

cp tk/unix/libtcl9tk9.0.so "$HERE/libtcl9tk9.0.so"
strip --strip-unneeded "$HERE/libtcl9tk9.0.so"
patchelf --remove-rpath "$HERE/libtcl9tk9.0.so"
patchelf --set-soname libtcl9tk9.0.so "$HERE/libtcl9tk9.0.so"
readelf -d "$HERE/libtcl9tk9.0.so" | grep -E "NEEDED|SONAME"
sha256sum "$HERE/libtcl9tk9.0.so"
echo "→ reporter la somme dans TK_XFT_SHA256 de setup_python.sh"
