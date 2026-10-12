# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Single-script tool (`busytag.py`) that drives a Busy Tag USB status display over a serial connection. No package structure, build system, tests, or linter. Comments are in German.

## Running

```bash
./setup-venv.sh              # creates .venv with pyserial and pillow>=10.1
.venv/bin/python busytag.py
```

On Windows: `setup-venv.bat` creates `.venv-win`, then `.venv-win\Scripts\python busytag.py`.

CLI via argparse in `main()`: `--led COLOR`, `--image PATH` or `--text TEXT` (mutually exclusive), `--center`, `--clear` (runs before `--image`/`--text`); see README for usage. README.md and README.de.md are parallel English/German versions; keep both in sync. The image is validated/converted (`prepare_image`) before the port is opened, so bad input never changes the device. Errors use `sys.exit(msg)` (exit 1), warnings go to stderr; this is meant for external automation. `find_port()` picks the port by USB vendor ID `0x303A` (Espressif) via `serial.tools.list_ports`, overridable with env var `BUSYTAG_PORT`. On Windows the device is `COM4`; under WSL it is `/dev/ttyACM0` only after `usbipd attach --wsl --busid <id>` (see README), and the user needs the `dialout` group.

## Device protocol

Communication is AT commands at 460800 baud, terminated by `\r\n`; the device answers `OK\r\n`.

- `AT+SC=127,FF0000` sets LEDs (127 = bitmask for all LEDs, then hex RGB color).
- `AT+UF=<name>,<size>` starts a file upload; wait for `>`, send raw bytes, wait for `OK\r\n`.
- `AT+SP=<name>` shows a stored file on the display.

Display is 240x280 (`DISPLAY_SIZE`). PNG/GIF at that size are uploaded unchanged; everything else goes through `fit_frame()` (scale to fit, black borders; `--center` never enlarges). Animations are rebuilt frame by frame as GIF keeping durations and loop. Max upload 1 MB. Uploads are recorded per device name (`AT+GDN`) in `busytag-uploads.json`; `--clear` deletes only those, after switching the display away (`release()`), because the shown file can be neither overwritten nor deleted.

## Firmware

`check_firmware()` reads `AT+GFV` (reply `+FV:<version>`, sometimes without a trailing `OK`) and exits below `MIN_FIRMWARE` (2.0); `BUSYTAG_SKIP_FW_CHECK=1` skips the check. `+FV` numbers differ from the Busy Tag app's: app 1.1.0.0 reports `1.0`, app 1.7.4.0 reports `2.0`. On FW `1.0` every `AT+UF` upload fails with `ERROR:3`, and a failed upload to an existing name can delete that file. On FW `2.0`, `AT+UF` to the file currently shown fails with `ERROR:3`, so `release()` switches the display to another picture first. `AT+GFL`/`AT+GPL` output is truncated by the device after ~540 bytes.

## Gotcha

Keep the upload name's extension matching the data format; the device likely picks the decoder by extension (converted images are uploaded as `<stem>.png`, `--text` as `busytag-text.png`). `images/imbusy-busylife.gif` is a 200x200 animated GIF that displays fine.
