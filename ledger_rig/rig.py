import glob
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from typing import TypeVar

IMAGE = "ghcr.io/ledgerhq/speculos"
LABEL = "ledger-rig"
TIMEOUT = 60
LOGS = Path("/tmp/ledger-rig")

T = TypeVar("T")


def up(
    app: str, seeds: Sequence[str], locked: bool = False
) -> list[tuple[str, str, int, int]]:
    elf = Path(app).resolve()
    LOGS.mkdir(exist_ok=True)
    devices = []
    for i, seed in enumerate(seeds):
        apdu, api = _free_ports()
        subprocess.run(
            ["docker", "run", "-d", "--rm", "--network", "host", "--label", LABEL]
            + ["-v", f"{elf}:/app.elf:ro", IMAGE, "/app.elf", "--model", "nanosp"]
            + ["--seed", seed, "--display", "headless"]
            + ["--apdu-port", str(apdu), "--api-port", str(api)],
            stdout=subprocess.DEVNULL,
            check=True,
        )
        _poll(partial(_answers, api))
        serial = f"{i:04d}"
        (LOGS / f"api-{serial}").write_text(str(api))
        with (LOGS / f"bridge-{serial}.log").open("ab") as stderr:
            bridge = subprocess.Popen(
                [sys.executable, "-m", "ledger_rig", "bridge"]
                + ["--apdu", f"127.0.0.1:{apdu}", "--serial", serial]
                + (["--locked"] if locked else []),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                start_new_session=True,
            )
        devices.append((_poll(partial(_hidraw, serial, bridge)), serial, apdu, api))
    return devices


def down() -> None:
    ps = subprocess.run(
        ["docker", "ps", "-q", "--filter", f"label={LABEL}"],
        capture_output=True,
        text=True,
        check=True,
    )
    ids = ps.stdout.split()
    if ids:
        subprocess.run(
            ["docker", "rm", "-f", *ids], stdout=subprocess.DEVNULL, check=True
        )


def _free_ports() -> tuple[int, int]:
    with socket.socket() as apdu, socket.socket() as api:
        apdu.bind(("127.0.0.1", 0))
        api.bind(("127.0.0.1", 0))
        return apdu.getsockname()[1], api.getsockname()[1]


def _poll(check: Callable[[], T]) -> T:
    deadline = time.monotonic() + TIMEOUT
    while not (result := check()):
        if time.monotonic() > deadline:
            raise TimeoutError
        time.sleep(0.1)
    return result


def _answers(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1).close()
    except OSError:
        return False
    return True


def _hidraw(serial: str, bridge: subprocess.Popen) -> str | None:
    for uevent in glob.glob("/sys/class/hidraw/*/device/uevent"):
        if f"HID_UNIQ={serial}" in Path(uevent).read_text().splitlines():
            return f"/dev/{Path(uevent).parts[4]}"
    if bridge.poll() is not None:
        raise RuntimeError(f"bridge {serial} exited with {bridge.returncode}")
    return None
