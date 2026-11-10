REPORT_SIZE = 64
CHANNEL = b"\x01\x01"
TAG = 0x05
HEADER_SIZE = 5
CHUNK_SIZE = REPORT_SIZE - HEADER_SIZE


class FramingError(ValueError):
    pass


def encode(message: bytes) -> list[bytes]:
    data = len(message).to_bytes(2, "big") + message
    reports = []
    for seq, start in enumerate(range(0, len(data), CHUNK_SIZE)):
        chunk = data[start : start + CHUNK_SIZE]
        header = CHANNEL + bytes([TAG]) + seq.to_bytes(2, "big")
        reports.append((header + chunk).ljust(REPORT_SIZE, b"\x00"))
    return reports


class Decoder:
    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._seq = 0
        self._length = 0
        self._buffer = bytearray()

    def feed(self, report: bytes) -> bytes | None:
        try:
            return self._feed(report)
        except FramingError:
            self._reset()
            raise

    def _feed(self, report: bytes) -> bytes | None:
        if report[:2] != CHANNEL:
            raise FramingError(f"channel {report[:2].hex()}")
        if report[2] != TAG:
            raise FramingError(f"tag {report[2]:#04x}")
        seq = int.from_bytes(report[3:5], "big")
        if seq != self._seq:
            raise FramingError(f"sequence {seq}, expected {self._seq}")
        if seq == 0:
            self._length = int.from_bytes(report[5:7], "big")
            self._buffer += report[7:]
        else:
            self._buffer += report[HEADER_SIZE:]
        self._seq += 1
        if len(self._buffer) < self._length:
            return None
        message = bytes(self._buffer[: self._length])
        self._reset()
        return message
