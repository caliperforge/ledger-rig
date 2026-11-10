import os
import select
import socket

from ledger_rig import framing, uhid

VENDOR = 0x2C97


class Bridge:
    def __init__(
        self,
        apdu_host: str,
        apdu_port: int,
        serial: str,
        pid: int = 0x5011,
        name: str = "Ledger Nano S Plus",
    ) -> None:
        self.address = (apdu_host, apdu_port)
        self.serial = serial
        self.pid = pid
        self.name = name

    def run(self) -> None:
        with socket.create_connection(self.address) as sock:
            fd = os.open("/dev/uhid", os.O_RDWR)
            try:
                os.write(fd, uhid.create2(self.name, self.serial, VENDOR, self.pid))
                _serve(fd, sock)
            finally:
                os.write(fd, uhid.destroy())
                os.close(fd)


def _serve(fd: int, sock: socket.socket) -> None:
    decoder = framing.Decoder()
    while sock not in select.select([fd, sock], [], [])[0]:
        report = uhid.output(os.read(fd, uhid.EVENT_SIZE))
        if report is None:
            continue
        if len(report) == framing.REPORT_SIZE + 1:
            report = report[1:]
        apdu = decoder.feed(report)
        if apdu is None:
            continue
        reply = _exchange(sock, apdu)
        if reply is None:
            return
        for chunk in framing.encode(reply):
            os.write(fd, uhid.input2(chunk))


def _exchange(sock: socket.socket, apdu: bytes) -> bytes | None:
    sock.sendall(len(apdu).to_bytes(4, "big") + apdu)
    header = sock.recv(4, socket.MSG_WAITALL)
    if len(header) < 4:
        return None
    size = int.from_bytes(header, "big") + 2
    reply = sock.recv(size, socket.MSG_WAITALL)
    return reply if len(reply) == size else None
