# DiashowGenerator

Ein einfacher, offline arbeitender Python-basierter Diashow-Generator, der aus einem Ordner mit Bildern ein MP4-Video erstellt. Unterstützt Ken-Burns-Zoom/Pan-Effekte, Übergänge und optionale Musik-Untermalung.

## ✅ Features

- Eingabeordner mit Bildern (`.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`, `.webp`)
- Ausgabe-MP4 (`slideshow.mp4` standardmäßig)
- Ken-Burns-Effekte pro Bild (Zoom, Pan etc.)
- Übergangsmodi: `crossfade`, `fade_black`, `wipe_right`
- Bildsortierung: `name`, `date`, `random`
- Optionaler Musik-Ordner (`.mp3`, `.wav`, `.flac`, `.aac`, `.m4a`, `.ogg`, `.opus`, `.wma`)
- Audioübergänge: `none`, `crossfade`, `fadeout`, `fadeinout`
- Audiowiedergabe-Endlosschleife (optional)
- PyInstaller-Build-Skripte für Windows und macOS im Repo enthalten

## 🚀 Quickstart

### A) Direkter EXE-Start (Windows, kein Build nötig)

```bat
dist\SlideshowGenerator.exe
```


### B) Python-Skript nutzen

1. Virtuelle Umgebung erstellen (Windows):

```bat
python -m venv .venv
.\.venv\Scripts\activate
```

Linux/macOS:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

2. Abhängigkeiten installieren:

```bat
pip install -r requirements.txt
```

3. Diashow erzeugen (CLI):

```bat
python create_slideshow.py --folder "C:\Pfad\zu\Bildern" --output "meine_diashow.mp4"
```

## 🖥️ GUI (empfohlen für einfache Nutzung)

Die grafische Benutzeroberfläche befindet sich in `slideshow_gui.py` und verwendet das gleiche Backend (`create_slideshow.py`).

1. Starten:

```bat
python slideshow_gui.py
```

2. Im GUI:
- Bildordner wählen
- Ausgabedatei wählen
- Dauer / Übergang / Auflösung einstellen
- Optional Musik-Ordner aktivieren
- Auf "Erstellen" klicken

3. Statusmeldungen und Fortschritt erscheinen im Log-Fenster.

> Hinweis: Unter Windows ist eine native Fenstergröße von mindestens 820x750 vorgesehen.

## ⚙️ CLI-Optionen

- `--folder` (erforderlich): Eingabeverzeichnis mit Bildern
- `--output` (default: `slideshow.mp4`): Ausgabedatei
- `--duration` (default: `5.0`): Dauer je Bild (Sekunden)
- `--transition` (default: `1.2`): Übergangszeit zwischen Bildern (Sekunden)
- `--fps` (default: `25`): Bilder pro Sekunde
- `--width` / `--height` (default: `1920x1080`): Ziel-Videoauflösung
- `--sort` (`name`/`date`/`random`)
- `--quality` (default: `8`): Encoderqualität (höher = besser, langsamer)

### Musik

- `--music-folder`: Ordner mit Audio-Dateien
- `--music-sort` (`name`/`date`/`random`)
- `--music-transition` (`none`/`crossfade`/`fadeout`/`fadeinout`)
- `--music-transition-duration` (default: `2.0`)
- `--music-volume` (default: `1.0`)
- `--music-loop` (Flag, aktiviert Looping)

##  Abhängigkeiten

- `imageio[ffmpeg]>=2.28`
- `numpy>=1.24`
- `Pillow>=9.0`

## 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert. Siehe [LICENSE](LICENSE) für Details.

## 💡 Hinweise

- `ffmpeg` wird über `imageio-ffmpeg` automatisch verwendet.
- Falls die Audio-Länge die Video-Dauer unterschreitet, wird bei `--music-loop` aufgefüllt.
- Bei fehlenden Bildern oder Audiodateien gibt das Skript eine Fehlermeldung.