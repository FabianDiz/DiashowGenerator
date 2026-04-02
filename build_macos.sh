#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  Slideshow Generator – macOS Build
#  Erstellt: dist/SlideshowGenerator (Binary) + dist/SlideshowGenerator.app
# ─────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

echo "============================================"
echo " Slideshow Generator - macOS Build"
echo "============================================"
echo ""

# Virtuelle Umgebung aktivieren
if [ -d ".venv" ]; then
    echo "[1/4] Aktiviere .venv ..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "[1/4] Aktiviere venv ..."
    source venv/bin/activate
else
    echo "[1/4] Keine venv gefunden - verwende System-Python"
fi

# PyInstaller installieren falls nicht vorhanden
echo "[2/4] Pruefe PyInstaller ..."
if ! python -m pip show pyinstaller &>/dev/null; then
    echo "     Installiere PyInstaller ..."
    python -m pip install pyinstaller --quiet
fi

# Alten Build aufraumen
echo "[3/4] Raeume alten Build auf ..."
rm -rf build
rm -rf "dist/SlideshowGenerator"
rm -rf "dist/SlideshowGenerator.app"

# Build starten
echo "[4/4] Erstelle Executable ..."
echo ""
python -m PyInstaller slideshow_generator.spec

echo ""
if [ -f "dist/SlideshowGenerator" ] || [ -d "dist/SlideshowGenerator.app" ]; then
    echo "============================================"
    echo " FERTIG!"
    [ -f "dist/SlideshowGenerator" ]       && echo "  Binary:  dist/SlideshowGenerator"
    [ -d "dist/SlideshowGenerator.app" ]   && echo "  App:     dist/SlideshowGenerator.app"
    echo "============================================"
    # macOS Quarantine-Flag entfernen (verhindert Gatekeeper-Warnung beim ersten Start)
    if [ -d "dist/SlideshowGenerator.app" ]; then
        echo ""
        echo "  Entferne Quarantine-Flag ..."
        xattr -dr com.apple.quarantine "dist/SlideshowGenerator.app" 2>/dev/null || true
    fi
else
    echo "============================================"
    echo " FEHLER: Executable wurde nicht erstellt."
    echo " Siehe Build-Ausgabe oben fuer Details."
    echo "============================================"
    exit 1
fi
