import signal
import socket
import subprocess
import sys
import threading
import time

import pytest
from fake_apdu import FakeApdu
from test_bridge_uhid import REPLY, _paths, _wait_for

from ledger_rig.__main__ import main
from ledger_rig.bridge import Bridge
from ledger_rig.framing import REPORT_SIZE, Decoder, FramingError, encode
from ledger_rig.hold import APDU, hold


def test_hold_sends_get_app_version_every_interval():
    ours, theirs = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    holder = threading.Thread(target=hold, args=(theirs.fileno(), 0.1), daemon=True)
    holder.start()
    times = []
    for _ in range(3):
        assert ours.recv(REPORT_SIZE) == encode(APDU)[0]
        times.append(time.monotonic())
        ours.send(encode(REPLY)[0] if len(times) < 3 else b"")
    holder.join(timeout=5)
    ours.close()
    theirs.close()
    assert not holder.is_alive()
    assert min(times[1] - times[0], times[2] - times[1]) >= 0.1


@pytest.mark.parametrize(
    "argv", [["hold", "nope"], ["hold"], ["hold", "0001", "--every", "x"]]
)
def test_hold_refuses_bad_arguments(argv):
    with pytest.raises(SystemExit) as refused:
        main(argv)
    assert refused.value.code == 2


def _connect() -> bytes | None:
    import hid

    device = hid.Device(path=_paths()[0])
    device.write(encode(APDU)[0])
    report = device.read(REPORT_SIZE, timeout=5000)
    device.close()
    return Decoder().feed(report)


@pytest.mark.uhid
def test_connect_while_hold_runs_and_after_it_stops(capsys):
    import hid

    server = FakeApdu({APDU: REPLY})
    bridge = threading.Thread(target=Bridge("127.0.0.1", server.port, "0001").run)
    bridge.start()
    _wait_for(_paths)
    watcher = hid.Device(path=_paths()[0])
    process = subprocess.Popen(
        [sys.executable, "-m", "ledger_rig", "hold", "0001", "--every", "0.2"]
    )
    # hidraw copies each reply to every open handle, so this is hold's first one
    assert watcher.read(REPORT_SIZE, timeout=5000)
    watcher.close()
    try:
        result = _connect().hex()
    except (hid.HIDException, FramingError) as error:
        result = repr(error)
    with capsys.disabled():
        print(f"connect while hold runs: {result}")
    process.send_signal(signal.SIGINT)
    assert process.wait(timeout=5) == 0
    assert _connect().endswith(b"\x90\x00")

    server.close()
    bridge.join(timeout=5)
    assert not bridge.is_alive()
    _wait_for(lambda: not _paths())
