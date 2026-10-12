# busytag-python

**English** | [Deutsch](README.de.md)

Small Python script that controls a [Busy Tag](https://www.busy-tag.com/) USB status display over its serial port. `busytag.py` sets the LED color and shows an image or a text on the display, controlled by command-line options, so it can be called from external automation.

## Requirements

- Python 3.8 or newer
- Busy Tag connected via USB
- Libraries: `pyserial`, `pillow>=10.1` (installed by the setup scripts)

## Windows

1. Install Python 3 from [python.org](https://www.python.org/downloads/) or the Microsoft Store.
2. Create the virtual environment (`.venv-win`) and install the libraries:
   ```bat
   setup-venv.bat
   ```
3. Run the script (options see [Usage](#usage)):
   ```bat
   .venv-win\Scripts\python busytag.py --led red --text "Hello"
   ```

Close the Busy Tag / Luxafor app first: while it runs, it holds the COM port.

## Linux

1. Make sure Python 3 and the venv module are installed (Debian/Ubuntu: `sudo apt install python3 python3-venv`).
2. Create the virtual environment (`.venv`) and install the libraries:
   ```bash
   ./setup-venv.sh
   ```
3. Allow your user to access serial ports, then log out and in again:
   ```bash
   sudo usermod -aG dialout $USER
   ```
4. Run the script (options see [Usage](#usage)):
   ```bash
   .venv/bin/python busytag.py --led red --text "Hello"
   ```

## WSL

WSL cannot open Windows COM ports directly. The simplest option is to run the script from Windows (see above). To run it inside WSL, pass the USB device through with [usbipd-win](https://github.com/dorssel/usbipd-win):

1. Install usbipd-win on Windows, then open a new terminal:
   ```powershell
   winget install --interactive --exact dorssel.usbipd-win
   ```
2. Find the Busy Tag's bus ID (e.g. `2-3`):
   ```powershell
   usbipd list
   ```
3. Share the device. This needs an administrator terminal and is only needed once:
   ```powershell
   usbipd bind --busid 2-3
   ```
4. Close the Busy Tag / Luxafor app. With a WSL window open, attach the device to WSL:
   ```powershell
   usbipd attach --wsl --busid 2-3
   ```
5. Continue with the Linux steps above.

If attach fails with `Device busy (exported)`, a Windows program still uses the device: close the Busy Tag / Luxafor app and eject the Busy Tag drive in Explorer. While attached, Windows cannot use the device. Give it back with `usbipd detach --busid 2-3`. The attachment is lost when the device is unplugged or WSL restarts, so repeat step 4 after either.

## Serial port

`busytag.py` finds the Busy Tag automatically by its USB vendor ID (`303a`, Espressif), e.g. `COM4` on Windows or `/dev/ttyACM0` on Linux. To use a specific port instead, set `BUSYTAG_PORT`:

```bash
BUSYTAG_PORT=/dev/ttyACM0 .venv/bin/python busytag.py
```
```bat
set BUSYTAG_PORT=COM4
.venv-win\Scripts\python busytag.py
```

## Firmware check

On start, `busytag.py` reads the firmware version (`AT+GFV`) and exits if it is older than `MIN_FIRMWARE` (2.0), because image upload fails on old firmware. The device reports its own version numbers: Busy Tag app firmware 1.7.4.0 reports `2.0`, 1.1.0.0 reports `1.0`. Update the firmware with the Busy Tag app on Windows. To skip the check, set `BUSYTAG_SKIP_FW_CHECK=1`.

## Usage

```bash
.venv/bin/python busytag.py --led red --image images/meeting.png
.venv/bin/python busytag.py --led FF8800
.venv/bin/python busytag.py --image images/away.gif
.venv/bin/python busytag.py --text "Meeting\nbis 15:00"
.venv/bin/python busytag.py --clear
```

On Windows use `.venv-win\Scripts\python busytag.py` with the same options.

- `--led COLOR`: hex `RRGGBB` (optional `#`) or a preset: `off`, `red`, `green`, `blue`, `yellow`, `cyan`, `magenta`, `white`.
- `--image PATH`: image to show. The display is 240x280.
  - PNG or GIF at exactly 240x280 is uploaded unchanged (fastest).
  - Any other image, still or animated, is scaled to fit 240x280 with black borders that keep the aspect ratio, with a warning on stderr. Animations stay animated and keep their frame timing.
  - The program exits with an error if the file is missing, unreadable, or larger than 1 MB after processing.
- `--center`: with `--image`, place smaller images in the middle at their original size instead of enlarging them. Larger images are still shrunk.
- `--clear`: delete the images this tool uploaded to the device. Uploads are recorded per device in `busytag-uploads.json` next to the script; files from the factory or the Busy Tag app are never deleted. Runs before `--image`/`--text`, so `--clear --image x.png` leaves only the new image.
- `--text TEXT`: render white text on black and show it (`\n` for line breaks). Cannot be combined with `--image`.

The image is uploaded under its file name (unsafe characters replaced by `_`; converted images get `.png`, animations `.gif`), so an existing device file with the same name is overwritten. `images/logo.jpg` and `images/logo.png` both become `logo.png` on the device. Device storage is small (about 3 MB).

Exit codes: `0` success, `1` error (device, image or firmware), `2` invalid arguments. Errors and warnings go to stderr.
