import glob
import os
import time
from pathlib import Path

from ledger_rig import framing

APDU = bytes.fromhex("e001000000")


def node(serial: str) -> str | None:
    for uevent in glob.glob("/sys/class/hidraw/*/device/uevent"):
        if f"HID_UNIQ={serial}" in Path(uevent).read_text().splitlines():
            return f"/dev/{Path(uevent).parts[4]}"
    return None


def hold(fd: int, every: float) -> None:
    while True:
        os.write(fd, framing.encode(APDU)[0])
        if not os.read(fd, framing.REPORT_SIZE):
            return
        time.sleep(every)
