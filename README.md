# Transcribe

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Status](https://img.shields.io/badge/status-active-success)

## Description
    
**Transcribe** is a portable application for transcribing and translating audio and video offline.
It allows you, for example, to quickly add subtitles to a video, dictate a TXT file, or transcribe into the language of your choice. Audio processing features such as noise reduction and volume adjustment are also integrated.

**Truchement** is a portable application for translating plain text and files, or for consulting definitions in offline monolingual dictionaries.
dictionnaries are SQLite database with a table 'entries' {lemma, definition} and entries_fts for full text search ( key = lemma )

Both can run directly from a USB drive, as all required dependencies (Whisper, FFmpeg, yt-dlp, and the Python virtual environment) can be embedded within the application.

## Installation

The applications can be used on Linux (Windows support is currently under development) with a few additional installations.

**Baluchon**, an application launcher, can help download heavy dependencies (transcription models, dictionaries, or a Python environment). It can also be used to create shortcuts or launchers, which is convenient if the application is stored on a USB stick.
👉 pour en savoir plus sur Baluchon :
https://github.com/fhoudebert/baluchon

👉without Baluchon
Create a python frozen venv with
'''
build/python/setup_venv_lang
'''  

Download a few transcribe models to build/whisper/models :  
https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin
https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin
https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q8_0.bin

Download a few monolingual dictionnaries to build/dic/  
build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/es-es.db
build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/en-en.db
build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/fr-fr.db
build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/it-it.db
build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/de-de.db
build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/pt-pt.db
#build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/ru-ru.db
#build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/ro-ro.db
#build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/da-da.db
#build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/el-el.db
#build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/ja-ja.db
#build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/tr-tr.db
#build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/sv-sv.db
#build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/zh-zh.db
#build/dic,https://github.com/fhoudebert/transcribe/releases/download/dic/da-da.db

## Typical Pipeline

```text
[Video File]
      │
      ├─ 🔍 Analyze ───────────────────── audio info + levels
      │
      ├─ ③ Audio Preprocessing ────────── loudnorm / noise reduction / volume
      │
      ▼
 📝 subtitle.bat/.sh            → <name>.en.srt
      │
      ▼
 🌐 translate-srt.py            → <name>.fr.srt (or another language)
      │
      ▼
 📦 include-srt / ffmpeg dual   → <name>.mkv
                                  ├─ English subtitle track
                                  └─ French subtitle track (default)
```

## Screenshots

### GUI
![Transcribe](images/transcribe.png)

![Truchement](images/truchement.png)
