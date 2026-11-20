import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from ledger_rig import rig
from ledger_rig.__main__ import main
from ledger_rig.bridge import VENDOR
from ledger_rig.framing import REPORT_SIZE, Decoder, encode
from ledger_rig.seeds import SEEDS

GET_PUBKEY = bytes.fromhex("e0050000 09 02 8000002c 800001f5")
ISO = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}"


def _wait_for(predicate) -> None:
    deadline = time.monotonic() + 5
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(0.05)


def _rig_serials() -> list[str]:
    import hid

    serials = [d["serial_number"] for d in hid.enumerate(VENDOR)]
    return [s for s in serials if s in ("0000", "0001", "0002")]


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
            [sys.executable, "-m", "ledger_rig", "up", "--count", "3", "--app", app],
            stdout=subprocess.PIPE,
            text=True,
            timeout=600,
            check=True,
        )
        devices = [line.split() for line in up.stdout.splitlines()]
        assert [serial for _, serial, _, _ in devices] == ["0000", "0001", "0002"]
        replies = [_exchange(path) for path, _, _, _ in devices]
    finally:
        subprocess.run([sys.executable, "-m", "ledger_rig", "down"], check=True)
        _wait_for(lambda: not _rig_serials())
    assert len(set(replies)) == 3
    assert replies == [_solana_key(m) + b"\x90\x00" for m in SEEDS[:3]]
    for (_, serial, _, _), reply in zip(devices, replies, strict=True):
        log = (rig.LOGS / f"bridge-{serial}.log").read_text().splitlines()
        sent = rf"{ISO} -> {len(GET_PUBKEY)} {GET_PUBKEY[:16].hex()}"
        assert re.fullmatch(sent, log[-2])
        assert re.fullmatch(rf"{ISO} <- 34 9000 {reply[:16].hex()}", log[-1])


def test_seeds_are_distinct_valid_bip39_phrases():
    words = (Path(__file__).parent / "bip39_english.txt").read_text().split()
    assert len(words) == 2048
    for phrase in SEEDS:
        indices = [words.index(word) for word in phrase.split()]
        bits = len(indices) * 11
        assert bits % 33 == 0
        checksum = bits // 33
        value = int("".join(f"{i:011b}" for i in indices), 2)
        entropy = (value >> checksum).to_bytes((bits - checksum) // 8, "big")
        expected = hashlib.sha256(entropy).digest()[0] >> (8 - checksum)
        assert value & ((1 << checksum) - 1) == expected
    assert len(set(SEEDS)) == len(SEEDS) == 8


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (["up", "--count", "2", "--app", "a.elf", "--seeds", "A"], "needs 2 seeds"),
        (["up", "--count", "9", "--app", "a.elf"], "needs 9 seeds"),
        (["up", "--count", "2"], "--app"),
    ],
)
def test_up_refuses_bad_arguments_before_starting(argv, error, monkeypatch, capsys):
    monkeypatch.setattr(rig, "up", lambda *_: pytest.fail("up started"))
    with pytest.raises(SystemExit) as refused:
        main(argv)
    assert refused.value.code == 2
    assert error in capsys.readouterr().err


def test_up_locked_passes_locked_to_rig(monkeypatch):
    calls = []
    monkeypatch.setattr(rig, "up", lambda _, __, *flags: calls.append(flags) or [])
    main(["up", "--count", "1", "--app", "a.elf", "--locked"])
    main(["up", "--count", "1", "--app", "a.elf"])
    assert calls == [(True, False), (False, False)]
