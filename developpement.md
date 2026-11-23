# Transcribe & Truchement — technical documentation

Installation details, platforms, building and internals. For an overview, see [README.md](README.md) / [LisezMoi.md](LisezMoi.md). Windows specifics: [README.windows.md](README.windows.md).

🇫🇷 [Version française : developpement.fr.md](developpement.fr.md)

- [Manual installation](#manual-installation)
- [Translating a book with a local LLM](#translating-a-book-with-a-local-llm)
- [Linux on x86-64 or arm64](#linux-on-x86-64-or-arm64)
- [macOS](#macos-apple-silicon-or-intel)
- [Running from a USB stick](#running-from-a-usb-stick)
- [Folder layout](#folder-layout)
- [Command-line scripts](#command-line-scripts)
- [Troubleshooting](#troubleshooting)
- [Python dependencies](#python-dependencies)

---

## Manual installation

1. **Unzip a release** (or clone this repository) into its final location.

2. **Install the portable Python** — a complete, relocatable CPython 3.12.15 from [python-build-standalone](https://github.com/astral-sh/python-build-standalone) (stripped build), placed in `build/python/venv` (Linux, macOS) or `build\python\venv-windows` (Windows). Despite the folder name, it is not a venv tied to the system Python. Argos Translate and the language packages are then installed inside the app folder; no system Python is needed or touched.

   ```bash
   ./setup_python.sh          # Linux, macOS (--no-lang: skip the language packages, --force: reinstall Python)
   setup_python.bat           # Windows (same options)
   ```

   Both can live side by side on the same stick; the language packages are shared.

   `setupPython_and_download.sh` / `.bat` run this step and then download the components listed in [`downloads.csv`](downloads.csv) (steps 3 and 4).

3. **Download one or more Whisper models** into `build/whisper/models/`:

   | Model | Size | Good for |
   |---|---|---|
   | [ggml-base.bin](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin) | ~150 MB | quick drafts, modest hardware |
   | [ggml-medium.bin](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin) | ~1.5 GB | good accuracy / speed balance |
   | [ggml-large-v3-turbo-q8_0.bin](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q8_0.bin) | ~0.9 GB | best quality on capable machines |

4. **Download the dictionaries you want** into `build/dic/` (one SQLite file per language):

   [en-en](https://github.com/fhoudebert/transcribe/releases/download/dic/en-en.db) ·
   [fr-fr](https://github.com/fhoudebert/transcribe/releases/download/dic/fr-fr.db) ·
   [es-es](https://github.com/fhoudebert/transcribe/releases/download/dic/es-es.db) ·
   [de-de](https://github.com/fhoudebert/transcribe/releases/download/dic/de-de.db) ·
   [it-it](https://github.com/fhoudebert/transcribe/releases/download/dic/it-it.db) ·
   [pt-pt](https://github.com/fhoudebert/transcribe/releases/download/dic/pt-pt.db)

   More languages (ru, ro, da, el, ja, tr, sv, zh…) are listed in [`downloads.csv`](downloads.csv).

   Dictionaries are plain SQLite databases — a table `entries {lemma, definition}` plus an `entries_fts` full-text index — so you can build your own or convert existing ones (e.g. with [PyGlossary](https://github.com/ilius/pyglossary)).

5. **Launch** the app:

   ```bash
   ./truchement     # translation & dictionaries
   ./transcribe     # transcription & subtitles
   ```

## Translating a book with a local LLM

The *Book* tab of Truchement translates `.epub` → `.epub`, `.pdf` → Markdown and `.txt` → `.txt` through a local LLM served by [llama.cpp](https://github.com/ggml-org/llama.cpp) (e.g. TranslateGemma 12B).

- The book is cut into paragraph groups sized to the server's context, translated, then revised in a second (and optional third) bilingual pass; italics, notes, links and the table of contents are kept.
- Progress is cached as it goes. *Pause* stops cleanly after the current block and writes a preview of the work done; you can shut the computer down and come back days later — the tab finds the book again and offers *Resume*. An unexpected shutdown is resumed the same way.
- *Trial* translates the first 10 blocks to check quality before a run of several hours.

Start the server first, for instance:

```bash
llama-server --model translategemma-12b-it-q4_k_m.gguf --alias translategemma-12b \
  --host 127.0.0.1 --port 8080 --ctx-size 8192 --n-gpu-layers 99 --jinja
```

The server address is set once (⚙ button, top right) and shared: tick *Local server* under the Translate button of **Text 2** to translate that tab with the LLM instead of Argos.

The work is done by `traduire-livre.py` (deployed next to the executable), which can also be run on its own with the portable Python: `build/python/venv/bin/python3.12 traduire-livre.py --help`.

## Linux on x86-64 or arm64

64-bit ARM includes Raspberry Pi 5 and ARM mini-PCs. One stick per architecture: the portable Python, ffmpeg, yt-dlp, whisper-cli and the two executables are specific to the processor, while models, translation packages and dictionaries are not.

1. On a machine of the target architecture, run `./setupPython_and_download.sh` — it picks the right Python (x86-64 or arm64), ffmpeg and yt-dlp by itself (`downloads.csv`, column `os`: `linux-x64` / `linux-arm64`).
2. Get the executables, either:
   - **from GitHub Actions** — workflow *Release (Linux, Windows, macOS)* (`.github/workflows/release.yml`): run it by hand from the *Actions* tab, or push a tag `v*` (or `linux-*`) to also publish the archives in that release. Unpack `transcribe-linux-<arch>.tar.xz` at the root of the stick (it holds `transcribe`, `truchement`, their scripts, `assets/`, `i18n/` and `build/whisper/`);
   - **or locally**, on that machine: `tools/whisper/build_whisper.sh` (whisper-cli), then `./compiler.sh`.

The workflow builds inside an Ubuntu 22.04 container, so the executables need glibc 2.35 or newer on the target (Ubuntu 22.04+, Debian 12, Raspberry Pi OS Bookworm, Linux Mint 21+). Allow at least 4 GB of RAM; on a Raspberry Pi 5, Whisper `base` and `medium` are usable, `large-v3-turbo` is slow.

## macOS (Apple Silicon or Intel)

Same layout as Linux, one stick (or folder) per processor: `transcribe-macos-arm64.tar.xz` for Apple Silicon (M1…M4), `transcribe-macos-x64.tar.xz` for Intel Macs — both built by the same workflow.

1. Unpack the archive, then — if it was downloaded with a web browser — lift the quarantine macOS puts on downloaded programs (they are signed *ad hoc*, not notarized):

   ```bash
   xattr -dr com.apple.quarantine /path/to/the/folder
   ```

2. Run `./setupPython_and_download.sh` in Terminal: portable Python (python-build-standalone for macOS, native Tk), language packages, ffmpeg / ffprobe ([Martin Riedl's builds](https://ffmpeg.martin-riedl.de)) and yt-dlp (`downloads.csv`, column `os`: `mac-arm64` / `mac-x64`).
3. Launch `./truchement` or `./transcribe` from Terminal (no `.app` bundle). `whisper-cli` uses the GPU through Metal. The recorder needs microphone access for Terminal (System Settings → Privacy & Security → Microphone).

Intel Macs: torch and onnxruntime no longer publish wheels for them, so `requirements.txt` pins the last ones available (torch 2.2.2, onnxruntime 1.23.2); Martin Riedl stops publishing new Intel ffmpeg builds in January 2027.

Locally: `tools/whisper/build_whisper.sh` (needs the Xcode command-line tools and cmake), then `./compiler.sh`.

## Windows

See [README.windows.md](README.windows.md): portable Python, Visual C++ runtime, Windows 11 on ARM, building with `compiler_truchement.bat` / `compiler_transcribe.bat`.

## Running from a USB stick

- Copy the **whole application folder** to the stick — models, dictionaries and the Python environment travel with it.
- Nothing is written to the host machine's user profile; language packages and settings stay inside the app folder (`build/argos-data/`, `build/dic/`…).
- A stick formatted in exFAT can hold both the Linux and Windows environments side by side.
- On Linux, prefer copying with `cp -a` or `rsync -a`. The portable Python holds no symbolic links, so file systems without them (exFAT, FAT32, NTFS) are fine.
- If something was lost in a copy, Truchement's built-in **Diagnose** button tells you exactly what is missing and how to fix it.

## Folder layout

```text
transcribe/                    ← the whole app: copy this folder, and it works
├── transcribe, truchement     ← the executables
├── traduire-livre.py          ← book translation engine (Book tab)
├── build/
│   ├── python/venv/           ← portable Python for Linux / macOS (never touches system Python)
│   ├── python/venv-windows/   ← portable Python for Windows
│   ├── whisper/models/        ← speech-to-text models (*.bin)
│   ├── argos-data/packages/   ← installed translation packages
│   ├── dic/                   ← offline dictionaries (*.db)
│   ├── ffmpeg/                ← media toolbox
│   └── yt-dlp/                ← media downloader
├── i18n/                      ← interface translations
└── *.sh                       ← command-line shortcuts for power users
```

Sources: `transcribe-src/` and `truchement-src/`; executables are built with PyInstaller through `compile_app.py` (`compiler.sh`, `compiler_transcribe.*`, `compiler_truchement.*`).

## Command-line scripts

Everything the GUIs do is also scriptable. A few examples:

| Script | What it does |
|---|---|
| `audio2srt.sh` | audio/video → subtitle file |
| `audio2en.sh` | audio in any language → English text |
| `traduire-srt.sh` | translate an existing `.srt` |
| `traduire-livre.py` | translate a book through a local llama.cpp server (run it with `build/python/venv/bin/python3.12`; `--help` for options) |
| `soustitre.sh` | full video → subtitled video pipeline |
| `creerMKV.sh` / `inclure-srt.sh` | embed subtitle tracks into an `.mkv` |
| `enregistrer.sh` | record from the microphone |
| `download_url.sh` | fetch online media for offline processing |

Typical Transcribe pipeline:

```text
[Video file]
     │
     ├─ 🔍 Analyze ──────────────── audio info + levels
     ├─ 🎚️ Preprocess ───────────── loudnorm / denoise / volume
     ▼
 📝 Transcribe (Whisper) ───────── movie.en.srt
     ▼
 🌐 Translate subtitles ────────── movie.fr.srt   (or any installed language)
     ▼
 📦 Mux with FFmpeg ────────────── movie.mkv  (both subtitle tracks embedded)
```

## Troubleshooting

- **"No languages installed" in Truchement** — the translation packages are missing from `build/argos-data/packages/`. Re-run `setup_python.sh` / `setup_python.bat` (or Baluchon), or use the in-app *Diagnose* button to see where the app is looking.
- **First translation is slow** — the first use of a language pair loads its model into memory (a few seconds). Subsequent translations are near-instant.
- **App works on one machine but not after copying to a stick** — if `build/python/venv/bin/python3.12` refuses to start on Linux, the stick is probably mounted `noexec` (remount it with `exec`). On a key prepared with an older version, `setup_python.sh` / `.bat` replaces the old venv built on the system Python, and moves an install from `build/python/linux` / `windows` into place.

## Python dependencies

- **Transcribe**: torch, stanza, spacy, onnxruntime, numpy, scipy, rich, click, typer, Jinja2, tqdm, PyQt5, pysrt, emoji, minisbd, mwt; possibly pyglossary, PyMuPDF.
- **Truchement**: argostranslate, argostranslate-files, bs4/lxml, pillow (optional); future: pyglossary, PyMuPDF.

See [`requirements.txt`](requirements.txt) for pinned versions.
