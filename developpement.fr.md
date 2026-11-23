# Transcribe & Truchement — documentation technique

Installation détaillée, plateformes, compilation et fonctionnement interne. Pour une présentation, voir [LisezMoi.md](LisezMoi.md) / [README.md](README.md). Particularités Windows : [README.windows.md](README.windows.md).

🇬🇧 [English version: developpement.md](developpement.md)

- [Installation manuelle](#installation-manuelle)
- [Traduire un livre avec un LLM local](#traduire-un-livre-avec-un-llm-local)
- [Linux sur x86-64 ou arm64](#linux-sur-x86-64-ou-arm64)
- [macOS](#macos-apple-silicon-ou-intel)
- [Fonctionnement depuis une clé USB](#fonctionnement-depuis-une-clé-usb)
- [Arborescence](#arborescence)
- [Scripts en ligne de commande](#scripts-en-ligne-de-commande)
- [Dépannage](#dépannage)
- [Dépendances Python](#dépendances-python)

---

## Installation manuelle

1. **Décompressez une version** (ou clonez ce dépôt) à son emplacement définitif.

2. **Installez le Python portable** — un CPython 3.12.15 complet et déplaçable issu de [python-build-standalone](https://github.com/astral-sh/python-build-standalone) (build « stripped »), placé dans `build/python/venv` (Linux, macOS) ou `build\python\venv-windows` (Windows). Malgré le nom du dossier, ce n'est pas un venv lié au Python du système. Argos Translate et les paquets de langues sont ensuite installés dans le dossier de l'application ; aucun Python système n'est nécessaire ni modifié.

   ```bash
   ./setup_python.sh          # Linux, macOS (--no-lang : sans les paquets de langues, --force : réinstaller Python)
   setup_python.bat           # Windows (mêmes options)
   ```

   Les deux peuvent cohabiter sur la même clé ; les paquets de langues sont partagés.

   `setupPython_and_download.sh` / `.bat` exécutent cette étape puis téléchargent les composants listés dans [`downloads.csv`](downloads.csv) (étapes 3 et 4).

3. **Téléchargez un ou plusieurs modèles Whisper** dans `build/whisper/models/` :

   | Modèle | Taille | Usage |
   |---|---|---|
   | [ggml-base.bin](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin) | ~150 Mo | brouillons rapides, machines modestes |
   | [ggml-medium.bin](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin) | ~1,5 Go | bon compromis précision / vitesse |
   | [ggml-large-v3-turbo-q8_0.bin](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q8_0.bin) | ~0,9 Go | meilleure qualité sur machines puissantes |

4. **Téléchargez les dictionnaires souhaités** dans `build/dic/` (un fichier SQLite par langue) :

   [en-en](https://github.com/fhoudebert/transcribe/releases/download/dic/en-en.db) ·
   [fr-fr](https://github.com/fhoudebert/transcribe/releases/download/dic/fr-fr.db) ·
   [es-es](https://github.com/fhoudebert/transcribe/releases/download/dic/es-es.db) ·
   [de-de](https://github.com/fhoudebert/transcribe/releases/download/dic/de-de.db) ·
   [it-it](https://github.com/fhoudebert/transcribe/releases/download/dic/it-it.db) ·
   [pt-pt](https://github.com/fhoudebert/transcribe/releases/download/dic/pt-pt.db)

   D'autres langues (ru, ro, da, el, ja, tr, sv, zh…) sont listées dans [`downloads.csv`](downloads.csv).

   Les dictionnaires sont de simples bases SQLite — une table `entries {lemma, definition}` et un index plein texte `entries_fts` — : vous pouvez créer les vôtres ou convertir des dictionnaires existants (par exemple avec [PyGlossary](https://github.com/ilius/pyglossary)).

5. **Lancez** l'application :

   ```bash
   ./truchement     # traduction et dictionnaires
   ./transcribe     # transcription et sous-titres
   ```

## Traduire un livre avec un LLM local

L'onglet *Livre* de Truchement traduit `.epub` → `.epub`, `.pdf` → Markdown et `.txt` → `.txt` grâce à un LLM local servi par [llama.cpp](https://github.com/ggml-org/llama.cpp) (par exemple TranslateGemma 12B).

- Le livre est découpé en groupes de paragraphes dimensionnés selon le contexte du serveur, traduit, puis révisé lors d'une deuxième passe bilingue (et d'une troisième, facultative) ; italiques, notes, liens et table des matières sont conservés.
- La progression est enregistrée au fur et à mesure. *Pause* s'arrête proprement après le bloc en cours et écrit un aperçu du travail fait ; vous pouvez éteindre l'ordinateur et revenir des jours plus tard — l'onglet retrouve le livre et propose *Reprendre la traduction*. Un arrêt inattendu se reprend de la même façon.
- *Essai* traduit les 10 premiers blocs pour vérifier la qualité avant un traitement de plusieurs heures.

Démarrez d'abord le serveur, par exemple :

```bash
llama-server --model translategemma-12b-it-q4_k_m.gguf --alias translategemma-12b \
  --host 127.0.0.1 --port 8080 --ctx-size 8192 --n-gpu-layers 99 --jinja
```

L'adresse du serveur se règle une fois (bouton ⚙, en haut à droite) et est partagée : cochez *Serveur local* sous le bouton Traduire de l'onglet **Texte 2** pour traduire cet onglet avec le LLM plutôt qu'avec Argos.

Le travail est effectué par `traduire-livre.py` (déposé à côté de l'exécutable), qui peut aussi être lancé seul avec le Python portable : `build/python/venv/bin/python3.12 traduire-livre.py --help`.

## Linux sur x86-64 ou arm64

L'ARM 64 bits comprend le Raspberry Pi 5 et les mini-PC ARM. Une clé par architecture : le Python portable, ffmpeg, yt-dlp, whisper-cli et les deux exécutables dépendent du processeur, contrairement aux modèles, paquets de traduction et dictionnaires.

1. Sur une machine de l'architecture visée, lancez `./setupPython_and_download.sh` — il choisit seul le bon Python (x86-64 ou arm64), ffmpeg et yt-dlp (`downloads.csv`, colonne `os` : `linux-x64` / `linux-arm64`).
2. Récupérez les exécutables :
   - **depuis GitHub Actions** — workflow *Release (Linux, Windows, macOS)* (`.github/workflows/release.yml`) : lancez-le à la main depuis l'onglet *Actions*, ou poussez un tag `v*` (ou `linux-*`) pour publier aussi les archives dans cette release. Décompressez `transcribe-linux-<arch>.tar.xz` à la racine de la clé (il contient `transcribe`, `truchement`, leurs scripts, `assets/`, `i18n/` et `build/whisper/`) ;
   - **ou localement**, sur cette machine : `tools/whisper/build_whisper.sh` (whisper-cli), puis `./compiler.sh`.

Le workflow compile dans un conteneur Ubuntu 22.04 : les exécutables demandent glibc 2.35 ou plus récent sur la cible (Ubuntu 22.04+, Debian 12, Raspberry Pi OS Bookworm, Linux Mint 21+). Prévoir au moins 4 Go de RAM ; sur un Raspberry Pi 5, Whisper `base` et `medium` sont utilisables, `large-v3-turbo` est lent.

## macOS (Apple Silicon ou Intel)

Même organisation que sous Linux, une clé (ou un dossier) par processeur : `transcribe-macos-arm64.tar.xz` pour Apple Silicon (M1…M4), `transcribe-macos-x64.tar.xz` pour les Mac Intel — tous deux produits par le même workflow.

1. Décompressez l'archive puis — si elle a été téléchargée avec un navigateur — levez la quarantaine que macOS applique aux programmes téléchargés (ils sont signés *ad hoc*, non notariés) :

   ```bash
   xattr -dr com.apple.quarantine /chemin/vers/le/dossier
   ```

2. Lancez `./setupPython_and_download.sh` dans le Terminal : Python portable (python-build-standalone pour macOS, Tk natif), paquets de langues, ffmpeg / ffprobe ([builds de Martin Riedl](https://ffmpeg.martin-riedl.de)) et yt-dlp (`downloads.csv`, colonne `os` : `mac-arm64` / `mac-x64`).
3. Lancez `./truchement` ou `./transcribe` depuis le Terminal (pas de paquet `.app`). `whisper-cli` utilise le GPU via Metal. L'enregistreur a besoin de l'accès au micro pour le Terminal (Réglages Système → Confidentialité et sécurité → Microphone).

Mac Intel : torch et onnxruntime ne publient plus de wheels pour eux, `requirements.txt` fixe donc les dernières disponibles (torch 2.2.2, onnxruntime 1.23.2) ; Martin Riedl cesse de publier de nouveaux builds ffmpeg Intel en janvier 2027.

Localement : `tools/whisper/build_whisper.sh` (nécessite les outils en ligne de commande Xcode et cmake), puis `./compiler.sh`.

## Windows

Voir [README.windows.md](README.windows.md) : Python portable, runtime Visual C++, Windows 11 sur ARM, compilation avec `compiler_truchement.bat` / `compiler_transcribe.bat`.

## Fonctionnement depuis une clé USB

- Copiez **tout le dossier de l'application** sur la clé — modèles, dictionnaires et environnement Python voyagent avec lui.
- Rien n'est écrit dans le profil utilisateur de la machine hôte ; paquets de langues et réglages restent dans le dossier de l'application (`build/argos-data/`, `build/dic/`…).
- Une clé formatée en exFAT peut accueillir côte à côte les environnements Linux et Windows.
- Sous Linux, copiez de préférence avec `cp -a` ou `rsync -a`. Le Python portable ne contient aucun lien symbolique : les systèmes de fichiers qui n'en gèrent pas (exFAT, FAT32, NTFS) conviennent.
- Si un élément s'est perdu à la copie, le bouton **Diagnostic** de Truchement indique précisément ce qui manque et comment y remédier.

## Arborescence

```text
transcribe/                    ← toute l'application : copiez ce dossier, et ça marche
├── transcribe, truchement     ← les exécutables
├── traduire-livre.py          ← moteur de traduction de livres (onglet Livre)
├── build/
│   ├── python/venv/           ← Python portable Linux / macOS (ne touche jamais au Python système)
│   ├── python/venv-windows/   ← Python portable Windows
│   ├── whisper/models/        ← modèles de reconnaissance vocale (*.bin)
│   ├── argos-data/packages/   ← paquets de traduction installés
│   ├── dic/                   ← dictionnaires hors ligne (*.db)
│   ├── ffmpeg/                ← boîte à outils multimédia
│   └── yt-dlp/                ← téléchargeur de médias
├── i18n/                      ← traductions de l'interface
└── *.sh                       ← raccourcis en ligne de commande
```

Sources : `transcribe-src/` et `truchement-src/` ; les exécutables sont produits avec PyInstaller via `compile_app.py` (`compiler.sh`, `compiler_transcribe.*`, `compiler_truchement.*`).

## Scripts en ligne de commande

Tout ce que font les interfaces graphiques est aussi scriptable. Quelques exemples :

| Script | Rôle |
|---|---|
| `audio2srt.sh` | audio/vidéo → fichier de sous-titres |
| `audio2en.sh` | audio dans n'importe quelle langue → texte anglais |
| `traduire-srt.sh` | traduire un `.srt` existant |
| `traduire-livre.py` | traduire un livre via un serveur llama.cpp local (à lancer avec `build/python/venv/bin/python3.12` ; `--help` pour les options) |
| `soustitre.sh` | chaîne complète vidéo → vidéo sous-titrée |
| `creerMKV.sh` / `inclure-srt.sh` | intégrer des pistes de sous-titres dans un `.mkv` |
| `enregistrer.sh` | enregistrer depuis le micro |
| `download_url.sh` | récupérer des médias en ligne pour un traitement hors ligne |

Chaîne de traitement type de Transcribe :

```text
[Fichier vidéo]
     │
     ├─ 🔍 Analyse ──────────────── infos audio + niveaux
     ├─ 🎚️ Prétraitement ────────── loudnorm / débruitage / volume
     ▼
 📝 Transcription (Whisper) ────── film.en.srt
     ▼
 🌐 Traduction des sous-titres ─── film.fr.srt   (ou toute langue installée)
     ▼
 📦 Multiplexage FFmpeg ────────── film.mkv  (les deux pistes intégrées)
```

## Dépannage

- **« Aucune langue installée » dans Truchement** — les paquets de traduction manquent dans `build/argos-data/packages/`. Relancez `setup_python.sh` / `setup_python.bat` (ou Baluchon), ou utilisez le bouton *Diagnostic* pour voir où l'application cherche.
- **La première traduction est lente** — la première utilisation d'une paire de langues charge son modèle en mémoire (quelques secondes). Les suivantes sont quasi instantanées.
- **L'application marche sur une machine mais plus après copie sur une clé** — si `build/python/venv/bin/python3.12` refuse de démarrer sous Linux, la clé est probablement montée en `noexec` (remontez-la avec `exec`). Sur une clé préparée avec une version antérieure, `setup_python.sh` / `.bat` remplace l'ancien venv lié au Python du système, et déplace une installation située dans `build/python/linux` / `windows`.

## Dépendances Python

- **Transcribe** : torch, stanza, spacy, onnxruntime, numpy, scipy, rich, click, typer, Jinja2, tqdm, PyQt5, pysrt, emoji, minisbd, mwt ; éventuellement pyglossary, PyMuPDF.
- **Truchement** : argostranslate, argostranslate-files, bs4/lxml, pillow (facultatif) ; à l'étude : pyglossary, PyMuPDF.

Voir [`requirements.txt`](requirements.txt) pour les versions fixées.
