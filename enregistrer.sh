x-terminal-emulator -e bash -c '
OUT="audio_$(date +%Y%m%d_%H%M%S).mp3"

echo "🎤 Dictaphone actif"
echo "Fichier : $OUT"
echo "Stop = Ctrl+C"

build/ffmpeg/bin/ffmpeg -f pulse -i default "$OUT"

echo "✔ Enregistrement terminé"
read -p "Fermer ?"
'
