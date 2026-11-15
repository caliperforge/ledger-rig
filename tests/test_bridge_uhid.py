import re
import socket
import subprocess
import sys
import threading
import time

import pytest
from fake_apdu import FakeApdu

from ledger_rig import rig, uhid
from ledger_rig.__main__ import main
from ledger_rig.bridge import VENDOR, Bridge
from ledger_rig.framing import REPORT_SIZE, Decoder, FramingError, encode

APDU = bytes.fromhex("e001000000")
REPLY = bytes.fromhex("0102039000")
ISO = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}"


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
    pages = [
        d["usage_page"] for d in hid.enumerate(VENDOR) if d["serial_number"] == "0001"
    ]
    assert pages == [0xFF00]
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
def test_locked_bridge_answers_5515_until_unlocked_and_after_lock():
    import hid

    rig.LOGS.mkdir(exist_ok=True)
    (rig.LOGS / "bridge-0001.sock").touch()
    server = FakeApdu({APDU: REPLY})
    bridge = threading.Thread(
        target=Bridge("127.0.0.1", server.port, "0001", locked=True).run
    )
    bridge.start()
    _wait_for(_paths)
    device = hid.Device(path=_paths()[0])

    def exchange() -> bytes | None:
        device.write(encode(APDU)[0])
        return Decoder().feed(device.read(REPORT_SIZE, timeout=5000))

    assert exchange() == b"\x55\x15"
    assert server.received == []
    main(["unlock", "0001"])
    assert exchange() == REPLY
    main(["lock", "0001"])
    assert exchange() == b"\x55\x15"
    assert server.received == [APDU]
    device.close()

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


@pytest.mark.uhid
def test_command_line_logs_each_apdu_and_exits_on_close():
    import hid

    apdu = bytes(range(20))
    reply = bytes(range(100, 118)) + b"\x90\x00"
    server = FakeApdu({apdu: reply})
    process = subprocess.Popen(
        [sys.executable, "-m", "ledger_rig", "bridge"]
        + ["--apdu", f"127.0.0.1:{server.port}", "--serial", "0001"],
        stderr=subprocess.PIPE,
        text=True,
    )
    _wait_for(_paths)
    device = hid.Device(path=_paths()[0])
    device.write(encode(apdu)[0])
    report = device.read(REPORT_SIZE, timeout=5000)
    device.close()
    assert Decoder().feed(report) == reply

    server.close()
    _, stderr = process.communicate(timeout=5)
    assert process.returncode == 0
    sent, received = stderr.splitlines()
    assert re.fullmatch(rf"{ISO} -> 20 {apdu[:16].hex()}", sent)
    assert re.fullmatch(rf"{ISO} <- 20 9000 {reply[:16].hex()}", received)
    _wait_for(lambda: not _paths())


@pytest.mark.parametrize(
    "argv",
    [
        ["bridge", "--apdu", "127.0.0.1", "--serial", "0001"],
        ["bridge", "--apdu", "127.0.0.1:port", "--serial", "0001"],
        ["bridge", "--apdu", "127.0.0.1:9999"],
        ["unlock"],
        ["unlock", "9999"],
        [],
    ],
)
def test_command_line_refuses_bad_arguments(argv):
    with pytest.raises(SystemExit) as refused:
        main(argv)
    assert refused.value.code == 2
