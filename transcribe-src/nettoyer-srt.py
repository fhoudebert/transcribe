#!/usr/bin/env python3
"""
nettoyer-srt.py — Corrige les chevauchements de minutage d'un fichier SRT
==========================================================================
whisper-cli produit des segments jointifs : la fin d'un sous-titre est
exactement le début du suivant (00:00:25,000 --> 00:00:25,000). Certains
lecteurs affichent alors les deux blocs sur la même image, d'où les
superpositions à l'écran. Ce script impose un écart strictement positif.

MÉTHODE — on recule la fin, on ne décale pas le début
-----------------------------------------------------
Le début d'un sous-titre est calé sur l'attaque de la parole : le retarder
désynchronise le texte. La fin, elle, tombe le plus souvent dans un silence.
On raccourcit donc le bloc précédent, et on ne touche au début du suivant que
si le raccourcissement rendait le bloc plus court que --min-ms.

L'écart par défaut est de 40 ms, soit une image à 25 fps. Un écart plus fin
(1 ms) ne survit pas à un lecteur ou à un multiplexage qui arrondit à l'image.
Réglage courant en sous-titrage professionnel : 80 ms (deux images).

Le script traite aussi les vrais chevauchements (fin postérieure au début
suivant) et les blocs mal formés (fin antérieure au début), qui apparaissent
quand whisper hésite sur les horodatages.

Usage :
    nettoyer-srt.py fichier.srt [fichier2.srt ...]
    nettoyer-srt.py --gap-ms 80 --min-ms 500 fichier.srt
    nettoyer-srt.py --dry-run fichier.srt      # diagnostic seul
    nettoyer-srt.py -o sortie.srt entree.srt   # sans écrasement
"""

from __future__ import annotations

import re
import sys

GAP_MS = 40      # écart minimal entre deux blocs (1 image à 25 fps)
MIN_MS = 300     # durée minimale d'un bloc — en deçà, illisible

TIME_RE = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})(.*)"
)


def to_ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms.ljust(3, "0"))


def to_stamp(ms: int) -> str:
    ms = max(0, ms)
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse(raw: str) -> list[dict]:
    """Découpe le SRT en blocs {start, end, extra, text}.

    Les blocs sans ligne de temps exploitable sont ignorés plutôt que de faire
    échouer le fichier entier : mieux vaut corriger ce qui peut l'être.
    """
    blocks = []
    for chunk in re.split(r"\r?\n\s*\r?\n+", raw.strip()):
        lines = chunk.splitlines()
        idx = next((i for i, l in enumerate(lines) if TIME_RE.search(l)), None)
        if idx is None:
            continue
        m = TIME_RE.search(lines[idx])
        blocks.append({
            "start": to_ms(*m.group(1, 2, 3, 4)),
            "end": to_ms(*m.group(5, 6, 7, 8)),
            "extra": m.group(9).rstrip(),      # coordonnées X1:… éventuelles
            "text": [l for l in lines[idx + 1:] if l.strip()],
        })
    return blocks


def fix(blocks: list[dict], gap: int, min_dur: int) -> int:
    """Impose fin[i] + gap <= début[i+1]. Retourne le nombre de blocs modifiés.

    Deux passes. La première recule les fins, sans jamais descendre sous la
    durée minimale. La seconde ne s'occupe que du résidu — les cas où reculer
    la fin ne suffisait pas — en décalant le début, ce qui se propage
    naturellement aux blocs suivants puisqu'on avance dans l'ordre.
    """
    before = [(b["start"], b["end"]) for b in blocks]

    # Blocs mal formés : fin avant début
    for b in blocks:
        if b["end"] < b["start"]:
            b["end"] = b["start"] + min_dur

    # Passe 1 — reculer la fin du bloc précédent
    for cur, nxt in zip(blocks, blocks[1:]):
        limit = nxt["start"] - gap
        if cur["end"] > limit:
            cur["end"] = max(limit, cur["start"] + min_dur)

    # Passe 2 — résidu : décaler le début, en cascade
    prev_end = None
    for b in blocks:
        if prev_end is not None and b["start"] < prev_end + gap:
            b["start"] = prev_end + gap
        if b["end"] < b["start"] + min_dur:
            b["end"] = b["start"] + min_dur
        prev_end = b["end"]

    return sum(1 for b, old in zip(blocks, before)
               if (b["start"], b["end"]) != old)


def render(blocks: list[dict]) -> str:
    out = []
    for i, b in enumerate(blocks, 1):
        out.append(str(i))
        out.append(f"{to_stamp(b['start'])} --> {to_stamp(b['end'])}{b['extra']}")
        out.extend(b["text"])
        out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    gap, min_dur, dry_run, output, paths = GAP_MS, MIN_MS, False, None, []

    it = iter(argv[1:])
    for arg in it:
        if arg == "--gap-ms":
            gap = int(next(it))
        elif arg == "--min-ms":
            min_dur = int(next(it))
        elif arg == "--dry-run":
            dry_run = True
        elif arg in ("-o", "--output"):
            output = next(it)
        elif arg in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            paths.append(arg)

    if not paths:
        print("Usage : nettoyer-srt.py [--gap-ms N] [--min-ms N] [--dry-run] "
              "[-o sortie.srt] fichier.srt ...", file=sys.stderr)
        return 2
    if output and len(paths) > 1:
        print("[ERREUR] -o est incompatible avec plusieurs fichiers",
              file=sys.stderr)
        return 2

    for path in paths:
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as fh:
                raw = fh.read()
        except OSError as e:
            print(f"[ERREUR] {path} : {e}", file=sys.stderr)
            return 1

        blocks = parse(raw)
        if not blocks:
            print(f"{path} : aucun bloc exploitable, fichier laissé intact")
            continue

        changed = fix(blocks, gap, min_dur)
        name = output or path
        if dry_run:
            print(f"{path} : {changed}/{len(blocks)} bloc(s) à corriger "
                  f"(écart {gap} ms) — aucune écriture")
            continue

        with open(name, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(blocks))
        print(f"{name} : {changed}/{len(blocks)} bloc(s) corrigé(s) "
              f"(écart {gap} ms)")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
