from __future__ import annotations

import io
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from serial.tools import list_ports

if TYPE_CHECKING:
    from satsentinel_flash.ui import ClackUI

_KEY_PATTERNS = (
    "Connecting", "Chip is", "Uploading stub", "Running stub",
    "Configuring flash", "Erasing flash", "Compressed",
    "Wrote", "Hash of data verified", "Hard resetting",
    "error", "Error", "WARNING",
)


class FlashError(Exception):
    pass


def list_serial_ports() -> list:
    return list(list_ports.comports())


def flash_device_threaded(
    ui: ClackUI,
    port: str,
    bootloader: Path,
    partition_table: Path,
    nvs_bin: Path,
    firmware: Path,
    ota_data: Path,
    baud: int = 460800,
) -> list[str]:
    import esptool

    args = [
        "--port", port,
        "--baud", str(baud),
        "--chip", "esp32s3",
        "write-flash", "-z",
        "0x0",      str(bootloader),
        "0x8000",   str(partition_table),
        "0x9000",   str(nvs_bin),
        "0x3F0000", str(ota_data),
        "0x10000",  str(firmware),
    ]

    buf = io.StringIO()
    exc_holder: list[BaseException] = []

    def _run() -> None:
        _out, _err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = buf
        try:
            esptool.main(args)
        except SystemExit as e:
            if e.code not in (None, 0):
                exc_holder.append(FlashError(f"esptool exited with code {e.code}"))
        except Exception as e:
            exc_holder.append(FlashError(str(e)))
        finally:
            sys.stdout, sys.stderr = _out, _err

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    printed = 0
    while thread.is_alive():
        lines = [l.strip() for l in buf.getvalue().splitlines()
                 if any(p in l for p in _KEY_PATTERNS)]
        for line in lines[printed:]:
            ui.note(line)
        printed = len(lines)
        time.sleep(0.2)
    thread.join()

    # flush any lines that arrived after last poll
    lines = [l.strip() for l in buf.getvalue().splitlines()
             if any(p in l for p in _KEY_PATTERNS)]
    for line in lines[printed:]:
        ui.note(line)

    if exc_holder:
        raise exc_holder[0]

    return lines[-4:]
