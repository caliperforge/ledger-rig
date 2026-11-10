import socket
import threading
import time

import pytest
from fake_apdu import FakeApdu

from ledger_rig import uhid
from ledger_rig.bridge import VENDOR, Bridge
from ledger_rig.framing import REPORT_SIZE, Decoder, FramingError, encode

APDU = bytes.fromhex("e001000000")
REPLY = bytes.fromhex("0102039000")


def _wait_for(predicate) -> None:
    deadline = time.monotonic() + 5
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(0.05)


def _paths() -> list[bytes]:
    import hid

    devices = hid.enumerate(VENDOR)
    return [d["path"] for d in devices if d["serial_number"] == "0001"]


def test_create2_is_one_event():
    assert len(uhid.create2("x", "0001", VENDOR, 0x5011)) == uhid.EVENT_SIZE


@pytest.mark.uhid
def test_apdu_round_trips_through_hidraw():
    import hid

    server = FakeApdu({APDU: REPLY})
    bridge = threading.Thread(target=Bridge("127.0.0.1", server.port, "0001").run)
    bridge.start()
    _wait_for(_paths)
    device = hid.Device(path=_paths()[0])
    device.write(encode(APDU)[0])
    report = device.read(REPORT_SIZE, timeout=5000)
    device.close()
    assert len(report) == REPORT_SIZE
    assert Decoder().feed(report) == REPLY

    server.close()
    bridge.join(timeout=5)
    assert not bridge.is_alive()
    _wait_for(lambda: not _paths())


@pytest.mark.uhid
def test_bad_report_raises_and_destroys_device():
    import hid

    server = FakeApdu({})
    raised = []

    def run() -> None:
        try:
            Bridge("127.0.0.1", server.port, "0001").run()
        except FramingError as error:
            raised.append(error)

    bridge = threading.Thread(target=run)
    bridge.start()
    _wait_for(_paths)
    device = hid.Device(path=_paths()[0])
    device.write(b"\x01\x01\x00" + encode(APDU)[0][3:])
    bridge.join(timeout=5)
    device.close()
    server.close()
    assert not bridge.is_alive()
    assert raised
    _wait_for(lambda: not _paths())


def test_refused_socket_raises_before_device():
    listener = socket.create_server(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()
    with pytest.raises(ConnectionRefusedError):
        Bridge("127.0.0.1", port, "0001").run()
