#!/usr/bin/env python3
"""
traduire-srt.py  —  Traduction rapide de fichiers SRT via argostranslate

Usage :
    python3 traduire-srt.py <fichier.en.srt> [from_lang=en] [to_lang=fr]

Stratégie de batch :
    Toutes les lignes de texte sont jointes avec un séparateur unique
    (§§§N§§§) puis envoyées en UN SEUL appel à argostranslate.
    Cela évite le coût de démarrage du modèle × N lignes et améliore
    la cohérence contextuelle des traductions.

Dépendances :
    pip install argostranslate
"""

import sys
import re
import os
import faulthandler

# En cas de crash natif (SIGSEGV dans torch/ctranslate2…), affiche la pile
# Python fautive au lieu d'un simple « code -11 » dans le journal de l'IHM.
faulthandler.enable()

# Sortie UTF-8 quelle que soit la locale : le journal de l'IHM lit en
# UTF-8, or sous Windows un stdout redirigé (PIPE) est encodé en cp1252
# → UnicodeEncodeError sur « ▶ », « → », etc.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ─────────────────────────────────────────────
#  Environnement d'exécution autonome (clé USB)
# ─────────────────────────────────────────────

# Paquets argos de l'application, comme à l'installation par
# setup_venv_lang.sh : cherchés à côté du script (déployé à la racine),
# sinon au niveau supérieur (exécution depuis transcribe-src en dev).
_HERE = os.path.dirname(os.path.abspath(__file__))
for _root in (_HERE, os.path.dirname(_HERE)):
    _pkg = os.path.join(_root, "build", "argos-data", "packages")
    if os.path.isdir(_pkg):
        os.environ.setdefault("ARGOS_PACKAGES_DIR", _pkg)
        os.environ.setdefault("ARGOS_TRANSLATE_PACKAGE_DIR", _pkg)  # alias legacy
        break

# Application hors-ligne, traduction CPU : ne jamais initialiser CUDA.
# Le chargement du modèle (mwt/spacy) importe torch ; si torch interroge un
# pilote NVIDIA qui ne correspond pas aux roues cuda du venv, l'init peut
# provoquer un SIGSEGV. CUDA_VISIBLE_DEVICES vide ⇒ torch répond « pas de
# GPU » sans toucher au pilote.
os.environ.setdefault("ARGOS_DEVICE_TYPE", "cpu")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

# ─────────────────────────────────────────────
#  Constantes
# ─────────────────────────────────────────────

# Séparateur improbable dans un sous-titre
SEP = "§§§{}§§§"
SEP_RE = re.compile(r"§§§(\d+)§§§")

# Taille max d'un lot en nombre de lignes de sous-titres
# (garde-fou : argostranslate accepte de grands textes, mais on évite
#  les timeouts ou coupures au-delà de ~500 segments)
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "400"))


# ─────────────────────────────────────────────
#  Parsing SRT
# ─────────────────────────────────────────────

def parse_srt(path: str) -> list[dict]:
    """
    Lit un fichier SRT et retourne une liste de blocs :
        {"id": "1", "time": "00:00:01,000 --> 00:00:03,000", "text": "Hello world"}
    Les lignes de texte multi-lignes sont jointes par un espace.
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()

    blocks = []
    for chunk in re.split(r"\n\n+", raw.strip()):
        lines = chunk.splitlines()
        if len(lines) < 2:
            continue
        block_id = lines[0].strip()
        time_line = lines[1].strip()
        text = " ".join(l.strip() for l in lines[2:] if l.strip())
        blocks.append({"id": block_id, "time": time_line, "text": text})
    return blocks


def write_srt(blocks: list[dict], translations: list[str], output_path: str):
    """Reconstruit le SRT avec les traductions (index-safe)."""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, block in enumerate(blocks):
            f.write(block["id"] + "\n")
            f.write(block["time"] + "\n")
            f.write((translations[i] if i < len(translations) else "") + "\n")
            f.write("\n")


# ─────────────────────────────────────────────
#  Chargement argostranslate
# ─────────────────────────────────────────────

def load_translator(from_lang: str, to_lang: str):
    """
    Retourne la fonction de traduction argostranslate pour la paire de langues.
    Fonctionne entièrement hors-ligne : utilise uniquement les paquets installés
    localement, sans aucun appel réseau.

    En cas de paire manquante, affiche les paires disponibles et quitte.
    """
    try:
        from argostranslate import translate
    except ImportError:
        print("✘ argostranslate non installé. Lancez : pip install argostranslate",
              file=sys.stderr)
        sys.exit(1)

    # get_translation() parcourt les paquets installés et retourne directement
    # l'objet Translation (pas de CachedTranslation) — API stable offline.
    translation = translate.get_translation_from_codes(from_lang, to_lang)

    if translation is None:
        # Affiche ce qui est disponible pour aider l'utilisateur
        installed = translate.get_installed_languages()
        pairs = []
        for src in installed:
            for tgt in installed:
                if src.code != tgt.code:
                    t = translate.get_translation_from_codes(src.code, tgt.code)
                    if t is not None:
                        pairs.append(f"{src.code}→{tgt.code}")
        print(f"✘ Paire {from_lang}→{to_lang} non installée.", file=sys.stderr)
        if pairs:
            print(f"  Paires disponibles : {', '.join(sorted(pairs))}", file=sys.stderr)
        else:
            print("  Aucun paquet de langue installé.", file=sys.stderr)
            print("  Installez un paquet, par exemple :", file=sys.stderr)
            print("    argospm install translate-en_fr", file=sys.stderr)
        sys.exit(1)

    print(f"  Modèle chargé : {from_lang} → {to_lang}", flush=True)
    return translation.translate


# ─────────────────────────────────────────────
#  Traduction par lot unique
# ─────────────────────────────────────────────

def translate_batch(texts: list[str], translate_fn) -> list[str]:
    """
    Joint toutes les lignes avec des séparateurs numérotés,
    traduit en UN seul appel, puis redécoupe.

    Exemple d'entrée jointe :
        §§§0§§§ Hello world §§§1§§§ How are you §§§2§§§ Goodbye

    Après traduction (fr) :
        §§§0§§§ Bonjour §§§1§§§ Comment allez-vous §§§2§§§ Au revoir
    """
    n = len(texts)
    if n == 0:
        return []

    # Construction du texte joint
    joined = " ".join(f"{SEP.format(i)} {t}" for i, t in enumerate(texts))

    # Traduction unique
    translated = translate_fn(joined)

    # Redécoupage par séparateurs
    # On reconstruit un tableau indexé
    result = [""] * n
    parts = SEP_RE.split(translated)
    # parts alterne : [texte_avant_sep0, idx0, texte0, idx1, texte1, …]
    # ex: ["", "0", " Bonjour ", "1", " Comment va ?", "2", " Au revoir"]
    i = 1
    while i + 1 < len(parts):
        try:
            idx = int(parts[i])
        except ValueError:
            i += 2
            continue
        if 0 <= idx < n:
            result[idx] = parts[i + 1].strip()
        i += 2

    # Fallback : si un segment est vide (séparateur mangé par le modèle),
    # on réessaie individuellement pour ce segment seulement
    missing = [i for i, v in enumerate(result) if not v]
    if missing:
        print(f"  → {len(missing)} segment(s) retraduit(s) individuellement…",
              flush=True)
        for idx in missing:
            result[idx] = translate_fn(texts[idx])

    return result


def translate_blocks(blocks: list[dict], translate_fn) -> list[str]:
    """
    Traduit tous les blocs en lots de BATCH_SIZE avec progression.
    Retourne la liste des traductions dans le même ordre que blocks.
    """
    texts = [b["text"] for b in blocks]
    n = len(texts)
    translations = []

    for start in range(0, n, BATCH_SIZE):
        end = min(start + BATCH_SIZE, n)
        batch = texts[start:end]
        pct = int(100 * end / n)
        print(f"  → Lot {start+1}–{end} / {n}  ({pct}%)…", flush=True)
        translations.extend(translate_batch(batch, translate_fn))

    return translations


# ─────────────────────────────────────────────
#  Point d'entrée
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage : traduire-srt.py <fichier.srt> [from=en] [to=fr]")
        sys.exit(1)

    input_path = sys.argv[1]
    from_lang  = sys.argv[2] if len(sys.argv) > 2 else "en"
    to_lang    = sys.argv[3] if len(sys.argv) > 3 else "fr"

    if not os.path.isfile(input_path):
        print(f"✘ Fichier introuvable : {input_path}", file=sys.stderr)
        sys.exit(1)

    # Nom de sortie : retire les extensions de langue connues puis ajoute to_lang
    base = input_path
    for ext in [f".{from_lang}.srt", ".srt"]:
        if base.endswith(ext):
            base = base[: -len(ext)]
            break
    output_path = f"{base}.{to_lang}.srt"

    print(f"▶ Traduction SRT  {from_lang} → {to_lang}")
    print(f"  Entrée  : {input_path}")
    print(f"  Sortie  : {output_path}")

    # Parsing
    blocks = parse_srt(input_path)
    print(f"  Segments: {len(blocks)}")

    # Chargement du traducteur
    print(f"  Chargement du modèle argostranslate…", flush=True)
    translate_fn = load_translator(from_lang, to_lang)

    # Traduction
    translations = translate_blocks(blocks, translate_fn)

    # Écriture
    write_srt(blocks, translations, output_path)
    print(f"✔ OK → {output_path}")


if __name__ == "__main__":
    main()
