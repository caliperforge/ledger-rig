import logging
import os
import select
import socket
from datetime import datetime
from pathlib import Path

from ledger_rig import framing, rig, uhid

VENDOR = 0x2C97

log = logging.getLogger(__name__)


class Bridge:
    def __init__(
        self,
        apdu_host: str,
        apdu_port: int,
        serial: str,
        pid: int = 0x5011,
        name: str = "Ledger Nano S Plus",
        locked: bool = False,
    ) -> None:
        self.address = (apdu_host, apdu_port)
        self.serial = serial
        self.pid = pid
        self.name = name
        self.locked = locked

    def run(self) -> None:
        path = _control_path(self.serial)
        with (
            socket.create_connection(self.address) as sock,
            socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as control,
        ):
            rig.LOGS.mkdir(exist_ok=True)
            path.unlink(missing_ok=True)
            control.bind(str(path))
            fd = os.open("/dev/uhid", os.O_RDWR)
            try:
                os.write(fd, uhid.create2(self.name, self.serial, VENDOR, self.pid))
                _serve(fd, sock, control, self.locked)
            finally:
                os.write(fd, uhid.destroy())
                os.close(fd)
                path.unlink()


def control(serial: str, command: str) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
        client.sendto(command.encode(), str(_control_path(serial)))


def _control_path(serial: str) -> Path:
    return rig.LOGS / f"bridge-{serial}.sock"


def _serve(fd: int, sock: socket.socket, control: socket.socket, locked: bool) -> None:
    decoder = framing.Decoder()
    while sock not in (ready := select.select([fd, sock, control], [], [])[0]):
        if control in ready:
            locked = control.recv(16) == b"lock"
        if fd not in ready:
            continue
        report = uhid.output(os.read(fd, uhid.EVENT_SIZE))
        if report is None:
            continue
        if len(report) == framing.REPORT_SIZE + 1:
            report = report[1:]
        apdu = decoder.feed(report)
        if apdu is None:
            continue
        log.info("%s -> %d %s", _now(), len(apdu), apdu[:16].hex())
        reply = b"\x55\x15" if locked else _exchange(sock, apdu)
        if reply is None:
            return
        log.info(
            "%s <- %d %s %s", _now(), len(reply), reply[-2:].hex(), reply[:16].hex()
        )
        for chunk in framing.encode(reply):
            os.write(fd, uhid.input2(chunk))


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _exchange(sock: socket.socket, apdu: bytes) -> bytes | None:
    sock.sendall(len(apdu).to_bytes(4, "big") + apdu)
    header = sock.recv(4, socket.MSG_WAITALL)
    if len(header) < 4:
        return None
    size = int.from_bytes(header, "big") + 2
    reply = sock.recv(size, socket.MSG_WAITALL)
    return reply if len(reply) == size else None
