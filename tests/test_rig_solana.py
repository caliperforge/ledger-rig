import hashlib
import os
import subprocess
import sys
import time

import pytest

from ledger_rig import rig
from ledger_rig.__main__ import main
from ledger_rig.bridge import VENDOR
from ledger_rig.framing import REPORT_SIZE, Decoder, encode
from ledger_rig.seeds import SEEDS

GET_PUBKEY = bytes.fromhex("e0050000 09 02 8000002c 800001f5")


def _wait_for(predicate) -> None:
    deadline = time.monotonic() + 5
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(0.05)


def _rig_serials() -> list[str]:
    import hid

    serials = [d["serial_number"] for d in hid.enumerate(VENDOR)]
    return [s for s in serials if s in ("0000", "0001")]


def _exchange(path: str) -> bytes:
    import hid

    device = hid.Device(path=path.encode())
    device.write(encode(GET_PUBKEY)[0])
    report = device.read(REPORT_SIZE, timeout=5000)
    device.close()
    reply = Decoder().feed(report)
    assert reply is not None
    return reply


def _solana_key(mnemonic: str) -> bytes:
    from solders.keypair import Keypair

    seed = hashlib.pbkdf2_hmac("sha512", mnemonic.encode(), b"mnemonic", 2048)
    return bytes(Keypair.from_seed_and_derivation_path(seed, "m/44'/501'").pubkey())


@pytest.mark.uhid
def test_up_serves_one_solana_key_per_seed_and_down_removes_them():
    app = f"apps/solana-nanosp-{os.environ['SOLANA_APP_TAG']}.elf"
    try:
        up = subprocess.run(
            [sys.executable, "-m", "ledger_rig", "up", "--count", "2", "--app", app],
            stdout=subprocess.PIPE,
            text=True,
            timeout=600,
            check=True,
        )
        devices = [line.split() for line in up.stdout.splitlines()]
        assert [serial for _, serial, _ in devices] == ["0000", "0001"]
        replies = [_exchange(path) for path, _, _ in devices]
    finally:
        subprocess.run([sys.executable, "-m", "ledger_rig", "down"], check=True)
        _wait_for(lambda: not _rig_serials())
    assert replies[0] != replies[1]
    assert replies == [_solana_key(m) + b"\x90\x00" for m in SEEDS]


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (["up", "--count", "2", "--app", "a.elf", "--seeds", "A"], "needs 2 seeds"),
        (["up", "--count", "3", "--app", "a.elf"], "needs 3 seeds"),
        (["up", "--count", "2"], "--app"),
    ],
)
def test_up_refuses_bad_arguments_before_starting(argv, error, monkeypatch, capsys):
    monkeypatch.setattr(rig, "up", lambda *_: pytest.fail("up started"))
    with pytest.raises(SystemExit) as refused:
        main(argv)
    assert refused.value.code == 2
    assert error in capsys.readouterr().err
