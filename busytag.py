import argparse, io, json, os, re, sys, time, serial
from serial.tools import list_ports
from PIL import Image, ImageDraw, ImageFont, ImageSequence

BUSYTAG_VID = 0x303A  # Espressif (ESP32 im Busy Tag)

def find_port():
    # Manuell überschreibbar, z.B. BUSYTAG_PORT=COM4 oder BUSYTAG_PORT=/dev/ttyACM0
    if os.environ.get("BUSYTAG_PORT"):
        return os.environ["BUSYTAG_PORT"]
    for p in list_ports.comports():  # Windows: COMx, Linux: /dev/ttyACMx
        if p.vid == BUSYTAG_VID:
            return p.device
    sys.exit("Busy Tag not found. Is it connected? Otherwise set BUSYTAG_PORT.")

def open_port(port):
    try:
        return serial.Serial(port, 460800, timeout=2)
    except serial.SerialException as e:
        if e.errno != 13 or os.name != "posix":  # 13 = Permission denied
            raise
        import grp, pwd
        user = pwd.getpwuid(os.getuid()).pw_name
        group = grp.getgrgid(os.stat(port).st_gid)
        if group.gr_gid in os.getgroups():
            sys.exit(f"Permission denied for {port}, although group '{group.gr_name}' is active.")
        if user in group.gr_mem:
            # Gruppe eingetragen, aber in dieser Sitzung noch nicht aktiv
            sys.exit(f"Permission denied for {port}: group '{group.gr_name}' is not active yet.\n"
                     f"Log in again (WSL: run 'wsl --shutdown' in Windows, then repeat usbipd attach)\n"
                     f"or for this shell only: newgrp {group.gr_name}")
        sys.exit(f"Permission denied for {port}. Add your user to group '{group.gr_name}':\n"
                 f"  sudo usermod -aG {group.gr_name} $USER\n"
                 f"Then log in again (WSL: run 'wsl --shutdown' in Windows, then repeat usbipd attach).")

ERRORS = {"0": "Unknown error", "1": "Unknown command", "2": "Invalid argument",
          "3": "File not found", "4": "Invalid size"}

def read_reply(c, until=("OK",)):
    # Zeilen lesen bis OK (bzw. until) oder ERROR:<code>; +evn-Ereignisse ignorieren
    lines = []
    while True:
        raw = ser.readline()
        if not raw:
            sys.exit(f"{c}: no reply from device (timeout)")
        line = raw.decode(errors="ignore").strip()
        if line.startswith("ERROR:"):
            code = line.split(":", 1)[1]
            sys.exit(f"{c}: device replied {line} ({ERRORS.get(code, 'unknown code')})")
        if line in until:
            return lines
        if line and not line.startswith("+evn:"):
            lines.append(line)

def cmd(c):
    ser.write((c + "\r\n").encode())
    return read_reply(c)

# AT+GFV meldet eine eigene Versionsnummer (App 1.1.0.0 -> +FV:1.0, App 1.7.4.0 -> +FV:2.0).
# Mit +FV:1.0 schlägt AT+UF immer mit ERROR:3 fehl, mit +FV:2.0 funktioniert es.
MIN_FIRMWARE = (2, 0)

def check_firmware():
    # Überspringen mit BUSYTAG_SKIP_FW_CHECK=1
    if os.environ.get("BUSYTAG_SKIP_FW_CHECK") == "1":
        return
    ser.reset_input_buffer()
    ser.write(b"AT+GFV\r\n")
    while True:  # Antwort "+FV:<version>", OK folgt nicht bei jeder Firmware
        raw = ser.readline()
        if not raw:
            sys.exit("AT+GFV: no reply from device (timeout). Set BUSYTAG_SKIP_FW_CHECK=1 to skip the firmware check.")
        line = raw.decode(errors="ignore").strip()
        if line.startswith("+FV:"):
            break
    time.sleep(0.2); ser.reset_input_buffer()  # evtl. nachfolgendes OK verwerfen
    found = line[4:].strip()
    try:
        version = tuple(int(x) for x in found.split("."))
    except ValueError:
        sys.exit(f"Unknown firmware version format '{found}'. Set BUSYTAG_SKIP_FW_CHECK=1 to skip the firmware check.")
    if version < MIN_FIRMWARE:
        need = ".".join(map(str, MIN_FIRMWARE))
        sys.exit(f"Busy Tag firmware {found} is too old, {need} or newer is required (image upload fails on older firmware).\n"
                 f"Update the firmware with the Busy Tag app on Windows to 1.7.4.0 or newer (WSL: 'usbipd detach --busid <id>' first).\n"
                 f"Set BUSYTAG_SKIP_FW_CHECK=1 to skip this check.")

DISPLAY_SIZE = (240, 280)       # Auflösung des Busy-Tag-Displays
MAX_UPLOAD = 1024 * 1024        # max. Dateigröße für AT+UF

LED_PRESETS = {"off": "000000", "red": "FF0000", "green": "00FF00", "blue": "0000FF",
               "yellow": "FFFF00", "cyan": "00FFFF", "magenta": "FF00FF", "white": "FFFFFF"}

def warn(msg):
    print(f"Warning: {msg}", file=sys.stderr)

def parse_color(value):
    # Preset-Name oder Hex-Code RRGGBB (optional mit #)
    v = value.strip().lower()
    if v in LED_PRESETS:
        return LED_PRESETS[v]
    v = v.lstrip("#")
    if re.fullmatch(r"[0-9a-f]{6}", v):
        return v.upper()
    raise argparse.ArgumentTypeError(
        f"invalid color '{value}': use RRGGBB hex or one of {', '.join(LED_PRESETS)}")

def device_name(path, ext):
    # Nur sichere Zeichen; Komma würde das AT-Kommando zerlegen
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.splitext(os.path.basename(path))[0])
    return stem + ext

def to_png(img):
    buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()

def fit_frame(frame, center):
    # Auf schwarze Fläche in Displaygröße setzen; skalieren unter Beibehaltung des Seitenverhältnisses
    frame = frame.convert("RGBA")
    scale = min(DISPLAY_SIZE[0] / frame.width, DISPLAY_SIZE[1] / frame.height)
    if center:
        scale = min(scale, 1)   # nur verkleinern, nie vergrößern
    if scale != 1:
        frame = frame.resize((max(1, round(frame.width * scale)), max(1, round(frame.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGB", DISPLAY_SIZE, "black")
    canvas.paste(frame, ((DISPLAY_SIZE[0] - frame.width) // 2, (DISPLAY_SIZE[1] - frame.height) // 2), frame)
    return canvas

def prepare_image(path, center=False):
    # Liefert (Dateiname auf dem Gerät, Bytes). Bricht ab, wenn das Bild nicht passt.
    if not os.path.isfile(path):
        sys.exit(f"Image not found: {path}")
    try:
        img = Image.open(path)
        img.load()
    except Exception as e:
        sys.exit(f"Cannot read image {path}: {e}")
    frames = getattr(img, "n_frames", 1)
    size = f"{img.size[0]}x{img.size[1]}"
    target = f"{DISPLAY_SIZE[0]}x{DISPLAY_SIZE[1]}"

    if img.format in ("PNG", "GIF") and img.size == DISPLAY_SIZE:
        with open(path, "rb") as f:
            name, data = device_name(path, "." + img.format.lower()), f.read()
    else:
        if img.size == DISPLAY_SIZE:
            warn(f"{path} is {img.format}, converting. Use PNG or GIF to skip this step.")
        else:
            how = "centering" if center and img.width <= DISPLAY_SIZE[0] and img.height <= DISPLAY_SIZE[1] else "rescaling"
            warn(f"{path} is {size}, {how} to {target} (black borders keep the aspect ratio). "
                 f"Use {target} images to skip this step.")
        try:
            if frames > 1:
                # Animation Bild für Bild umrechnen, Anzeigedauer und Wiederholung übernehmen
                out, durations = [], []
                for frame in ImageSequence.Iterator(img):
                    out.append(fit_frame(frame, center))
                    durations.append(frame.info.get("duration", img.info.get("duration", 100)))
                buf = io.BytesIO()
                out[0].save(buf, "GIF", save_all=True, append_images=out[1:], duration=durations,
                            loop=img.info.get("loop", 0), disposal=1)
                name, data = device_name(path, ".gif"), buf.getvalue()
            else:
                name, data = device_name(path, ".png"), to_png(fit_frame(img, center))
        except Exception as e:
            sys.exit(f"Cannot convert image {path}: {e}")

    if len(data) > MAX_UPLOAD:
        sys.exit(f"Image {path} is {len(data)} bytes after processing, the device accepts at most {MAX_UPLOAD} bytes. "
                 f"Use a smaller image or fewer frames.")
    return name, data

def text_image(text):
    img = Image.new("RGB", DISPLAY_SIZE, "black")
    ImageDraw.Draw(img).text((20, 120), text, fill="white", font=ImageFont.load_default(size=32))
    return "busytag-text.png", to_png(img)

def read_lines(c, wait=0.5):
    # Für Abfragen ohne verlässliches OK: alle Zeilen lesen, bis das Gerät schweigt
    ser.reset_input_buffer()
    ser.write((c + "\r\n").encode())
    old, ser.timeout = ser.timeout, wait
    try:
        lines = []
        while raw := ser.readline():
            lines.append(raw.decode(errors="ignore").strip())
        return lines
    finally:
        ser.timeout = old

# Vom Skript hochgeladene Dateien je Gerät, damit --clear nur diese löscht
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "busytag-uploads.json")

def load_manifest():
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        sys.exit(f"Cannot read {MANIFEST}: {e}")

def save_manifest(manifest):
    try:
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
    except OSError as e:
        warn(f"Cannot write {MANIFEST}: {e}")

def device_id():
    for line in read_lines("AT+GDN"):
        if line.startswith("+DN:"):
            return line[4:].strip()
    sys.exit("AT+GDN: device did not report its name")

def pictures():
    return [l[4:].rsplit(",", 1)[0] for l in read_lines("AT+GPL") if l.startswith("+PL:")]

def release(names):
    # Das gerade angezeigte Bild kann weder überschrieben noch gelöscht werden (ERROR:3),
    # daher vorher ein anderes Bild vom Gerät anzeigen
    shown = next((l[4:] for l in read_lines("AT+SP?") if l.startswith("+SP:")), None)
    if shown not in names:
        return
    others = [n for n in pictures() if n not in names]
    if not others:
        sys.exit(f"{shown} is currently displayed and no other picture is on the device to switch to.")
    cmd(f"AT+SP={others[0]}")

def upload(name, data, dev):
    release({name})
    c = f"AT+UF={name},{len(data)}"
    ser.write((c + "\r\n").encode())
    read_reply(c, until=(">",))   # Gerät wartet auf die Daten
    ser.write(data)
    read_reply(c)
    manifest = load_manifest()
    if name not in manifest.setdefault(dev, []):
        manifest[dev].append(name)
        save_manifest(manifest)

def clear(dev):
    manifest = load_manifest()
    names = manifest.get(dev, [])
    if not names:
        print("Nothing to clear: no uploads recorded for this device.")
        return
    release(set(names))
    kept = []
    for name in names:
        reply = read_lines(f"AT+DF={name}")
        if "OK" in reply:
            print(f"Deleted {name}")
        elif "ERROR:3" in reply:
            print(f"Already gone: {name}")
        else:
            warn(f"Could not delete {name}: {' '.join(reply) or 'no reply'}")
            kept.append(name)
    if kept:
        manifest[dev] = kept
    else:
        manifest.pop(dev, None)
    save_manifest(manifest)

def main():
    global ser
    ap = argparse.ArgumentParser(description="Set LED color and displayed image of a Busy Tag.")
    ap.add_argument("--led", type=parse_color, metavar="COLOR",
                    help=f"LED color: RRGGBB hex (e.g. FF0000) or preset ({', '.join(LED_PRESETS)})")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--image", metavar="PATH",
                     help=f"image to display; PNG/GIF at {DISPLAY_SIZE[0]}x{DISPLAY_SIZE[1]} are uploaded unchanged, others are fitted")
    src.add_argument("--text", help="render this text and display it (use \\n for line breaks)")
    ap.add_argument("--center", action="store_true",
                    help="center smaller images instead of enlarging them (larger ones are still shrunk)")
    ap.add_argument("--clear", action="store_true",
                    help="delete images this tool uploaded to the device (runs before --image/--text)")
    args = ap.parse_args()
    if not (args.led or args.image or args.text or args.clear):
        ap.error("nothing to do: give --led, --image, --text and/or --clear")

    # Bild vor dem Verbindungsaufbau prüfen, damit Fehler das Gerät nicht verändern
    if args.image:
        image = prepare_image(args.image, args.center)
    elif args.text:
        image = text_image(args.text.replace("\\n", "\n"))
    else:
        image = None

    ser = open_port(find_port())
    try:
        check_firmware()
        dev = device_id() if (image or args.clear) else None
        if args.led:
            cmd(f"AT+SC=127,{args.led}")   # 127 = alle LEDs
        if args.clear:
            clear(dev)
        if image:
            upload(*image, dev)
            cmd(f"AT+SP={image[0]}")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
