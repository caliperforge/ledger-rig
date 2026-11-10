import struct

UHID_DESTROY = 1
UHID_OUTPUT = 6
UHID_CREATE2 = 11
UHID_INPUT2 = 12
EVENT_SIZE = 4376

# vendor usage page 0xFFA0, 64-byte input and output reports
REPORT_DESCRIPTOR = bytes.fromhex(
    "06a0ff 0901 a101"
    " 0903 1500 26ff00 7508 9540 8108"
    " 0904 1500 26ff00 7508 9540 9108"
    " c0"
)


def create2(name: str, serial: str, vendor: int, product: int) -> bytes:
    return (
        struct.pack("<I", UHID_CREATE2)
        + name.encode().ljust(128, b"\0")
        + b"".ljust(64, b"\0")
        + serial.encode().ljust(64, b"\0")
        + struct.pack("<HHIIII", len(REPORT_DESCRIPTOR), 0x03, vendor, product, 0, 0)
        + REPORT_DESCRIPTOR.ljust(4096, b"\0")
    )


def input2(report: bytes) -> bytes:
    return struct.pack("<IH", UHID_INPUT2, len(report)) + report


def destroy() -> bytes:
    return struct.pack("<I", UHID_DESTROY)


def output(event: bytes) -> bytes | None:
    (kind,) = struct.unpack_from("<I", event)
    if kind != UHID_OUTPUT:
        return None
    (size,) = struct.unpack_from("<H", event, 4100)
    return event[4 : 4 + size]
