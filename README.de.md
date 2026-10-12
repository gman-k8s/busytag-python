# busytag-python

[English](README.md) | **Deutsch**

Kleines Python-Skript, das eine [Busy Tag](https://www.busy-tag.com/) USB-Statusanzeige über deren seriellen Port steuert. `busytag.py` setzt die LED-Farbe und zeigt ein Bild oder einen Text auf dem Display an. Die Steuerung erfolgt über Kommandozeilenoptionen, sodass das Skript aus externer Automatisierung aufgerufen werden kann.

## Voraussetzungen

- Python 3.8 oder neuer
- Busy Tag per USB angeschlossen
- Bibliotheken: `pyserial`, `pillow>=10.1` (werden von den Setup-Skripten installiert)

## Windows

1. Python 3 von [python.org](https://www.python.org/downloads/) oder aus dem Microsoft Store installieren.
2. Die virtuelle Umgebung (`.venv-win`) erstellen und die Bibliotheken installieren:
   ```bat
   setup-venv.bat
   ```
3. Das Skript ausführen (Optionen siehe [Verwendung](#verwendung)):
   ```bat
   .venv-win\Scripts\python busytag.py --led red --text "Hello"
   ```

Zuerst die Busy Tag / Luxafor App schließen: Solange sie läuft, belegt sie den COM-Port.

## Linux

1. Sicherstellen, dass Python 3 und das venv-Modul installiert sind (Debian/Ubuntu: `sudo apt install python3 python3-venv`).
2. Die virtuelle Umgebung (`.venv`) erstellen und die Bibliotheken installieren:
   ```bash
   ./setup-venv.sh
   ```
3. Dem eigenen Benutzer den Zugriff auf serielle Ports erlauben, danach ab- und wieder anmelden:
   ```bash
   sudo usermod -aG dialout $USER
   ```
4. Das Skript ausführen (Optionen siehe [Verwendung](#verwendung)):
   ```bash
   .venv/bin/python busytag.py --led red --text "Hello"
   ```

## WSL

WSL kann Windows-COM-Ports nicht direkt öffnen. Am einfachsten ist es, das Skript unter Windows auszuführen (siehe oben). Um es innerhalb von WSL auszuführen, wird das USB-Gerät mit [usbipd-win](https://github.com/dorssel/usbipd-win) durchgereicht:

1. usbipd-win unter Windows installieren, danach ein neues Terminal öffnen:
   ```powershell
   winget install --interactive --exact dorssel.usbipd-win
   ```
2. Die Bus-ID des Busy Tag ermitteln (z. B. `2-3`):
   ```powershell
   usbipd list
   ```
3. Das Gerät freigeben. Dazu ist ein Terminal mit Administratorrechten nötig; der Schritt ist nur einmal erforderlich:
   ```powershell
   usbipd bind --busid 2-3
   ```
4. Die Busy Tag / Luxafor App schließen. Bei geöffnetem WSL-Fenster das Gerät an WSL anbinden:
   ```powershell
   usbipd attach --wsl --busid 2-3
   ```
5. Mit den Linux-Schritten oben fortfahren.

Schlägt attach mit `Device busy (exported)` fehl, nutzt noch ein Windows-Programm das Gerät: die Busy Tag / Luxafor App schließen und das Busy-Tag-Laufwerk im Explorer auswerfen. Solange das Gerät angebunden ist, kann Windows es nicht verwenden. Zurückgegeben wird es mit `usbipd detach --busid 2-3`. Die Anbindung geht verloren, wenn das Gerät abgezogen oder WSL neu gestartet wird; danach Schritt 4 wiederholen.

## Serieller Port

`busytag.py` findet das Busy Tag automatisch anhand der USB-Hersteller-ID (`303a`, Espressif), z. B. `COM4` unter Windows oder `/dev/ttyACM0` unter Linux. Soll stattdessen ein bestimmter Port verwendet werden, ist `BUSYTAG_PORT` zu setzen:

```bash
BUSYTAG_PORT=/dev/ttyACM0 .venv/bin/python busytag.py
```
```bat
set BUSYTAG_PORT=COM4
.venv-win\Scripts\python busytag.py
```

## Firmware-Prüfung

Beim Start liest `busytag.py` die Firmware-Version (`AT+GFV`) aus und beendet sich, wenn sie älter als `MIN_FIRMWARE` (2.0) ist, da der Bild-Upload mit alter Firmware fehlschlägt. Das Gerät meldet eigene Versionsnummern: Busy-Tag-App-Firmware 1.7.4.0 meldet `2.0`, 1.1.0.0 meldet `1.0`. Die Firmware wird mit der Busy Tag App unter Windows aktualisiert. Um die Prüfung zu überspringen, `BUSYTAG_SKIP_FW_CHECK=1` setzen.

## Verwendung

```bash
.venv/bin/python busytag.py --led red --image images/meeting.png
.venv/bin/python busytag.py --led FF8800
.venv/bin/python busytag.py --image images/away.gif
.venv/bin/python busytag.py --text "Meeting\nbis 15:00"
.venv/bin/python busytag.py --clear
```

Unter Windows `.venv-win\Scripts\python busytag.py` mit denselben Optionen verwenden.

- `--led COLOR`: Hex-Wert `RRGGBB` (optional mit `#`) oder eine Voreinstellung: `off`, `red`, `green`, `blue`, `yellow`, `cyan`, `magenta`, `white`.
- `--image PATH`: anzuzeigendes Bild. Das Display hat 240x280 Pixel.
  - PNG oder GIF mit exakt 240x280 wird unverändert hochgeladen (am schnellsten).
  - Jedes andere Bild, ob statisch oder animiert, wird unter Beibehaltung des Seitenverhältnisses mit schwarzen Rändern auf 240x280 eingepasst; dabei erscheint eine Warnung auf stderr. Animationen bleiben animiert und behalten ihr Timing.
  - Das Programm beendet sich mit einem Fehler, wenn die Datei fehlt, nicht lesbar ist oder nach der Verarbeitung größer als 1 MB ist.
- `--center`: zusammen mit `--image` werden kleinere Bilder in Originalgröße mittig platziert, statt vergrößert zu werden. Größere Bilder werden weiterhin verkleinert.
- `--clear`: löscht die Bilder, die dieses Tool auf das Gerät hochgeladen hat. Uploads werden pro Gerät in `busytag-uploads.json` neben dem Skript festgehalten; Dateien ab Werk oder aus der Busy Tag App werden nie gelöscht. Läuft vor `--image`/`--text`, sodass `--clear --image x.png` nur das neue Bild übrig lässt.
- `--text TEXT`: weißen Text auf schwarzem Grund rendern und anzeigen (`\n` für Zeilenumbrüche). Nicht mit `--image` kombinierbar.

Das Bild wird unter seinem Dateinamen hochgeladen (unsichere Zeichen werden durch `_` ersetzt; konvertierte Bilder erhalten `.png`, Animationen `.gif`). Eine vorhandene Datei gleichen Namens auf dem Gerät wird daher überschrieben. `images/logo.jpg` und `images/logo.png` werden auf dem Gerät beide zu `logo.png`. Der Gerätespeicher ist klein (etwa 3 MB).

Rückgabewerte (Exit-Codes): `0` Erfolg, `1` Fehler (Gerät, Bild oder Firmware), `2` ungültige Argumente. Fehler und Warnungen gehen an stderr.
