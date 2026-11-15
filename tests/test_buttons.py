import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from test_rig_solana import _solana_key

from ledger_rig import rig
from ledger_rig.__main__ import main
from ledger_rig.framing import REPORT_SIZE, Decoder, encode
from ledger_rig.seeds import SEEDS

BODY = b'{"action": "press-and-release"}'
EVENTS = "/events?currentscreenonly=true"
SCREENS = [
    ["Review transaction", "to send SOL"],
    [],
    ["Amount", "SOL 0.000000001"],
    ["Sign transaction"],
    ["Reject transaction"],
]


@pytest.fixture
def speculos(tmp_path, monkeypatch):
    monkeypatch.setattr(rig, "LOGS", tmp_path)
    servers = []

    def start(screens: list[list[str]]) -> list[tuple[str, str, bytes]]:
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                requests.append(("GET", self.path, b""))
                texts = screens[0]
                if not texts:
                    screens.pop(0)
                self._reply({"events": [{"text": text} for text in texts]})

            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                requests.append(("POST", self.path, body))
                if self.path == "/button/right":
                    screens.pop(0)
                self._reply({})

            def _reply(self, payload: dict) -> None:
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: object) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        (tmp_path / "api-0000").write_text(str(server.server_address[1]))
        return requests

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_press_posts_one_press_and_release(speculos):
    requests = speculos([["Review transaction"]])
    main(["press", "0000", "right"])
    assert requests == [("POST", "/button/right", BODY)]


@pytest.mark.parametrize(
    ("choice", "steps"),
    [
        ("approve", "read read right read read right read both"),
        ("reject", "read read right read read right read right read both"),
    ],
)
def test_walk_presses_right_to_the_choice_then_both(choice, steps, speculos):
    requests = speculos([list(texts) for texts in SCREENS])
    main([choice, "0000"])
    assert requests == [
        ("GET", EVENTS, b"") if step == "read" else ("POST", f"/button/{step}", BODY)
        for step in steps.split()
    ]


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (["press", "0001", "right"], "no device 0001: run up first"),
        (["approve", "0001"], "no device 0001: run up first"),
        (["press", "0000", "up"], "invalid choice"),
    ],
)
def test_buttons_refuse_bad_arguments_before_sending(argv, error, speculos, capsys):
    requests = speculos([["Review transaction"]])
    with pytest.raises(SystemExit) as refused:
        main(argv)
    assert refused.value.code == 2
    assert error in capsys.readouterr().err
    assert requests == []


def _sign(path: str, apdu: bytes, choice: str) -> bytes:
    import hid

    device = hid.Device(path=path.encode())
    for report in encode(apdu):
        device.write(report)
    main([choice, "0000"])
    decoder = Decoder()
    while (reply := decoder.feed(device.read(REPORT_SIZE, timeout=5000))) is None:
        pass
    device.close()
    return reply


@pytest.mark.uhid
def test_reject_refuses_and_approve_signs_on_the_device():
    app = f"apps/solana-nanosp-{os.environ['SOLANA_APP_TAG']}.elf"
    message = (
        bytes.fromhex("010001 03")
        + _solana_key(SEEDS[0])
        + bytes([1] * 32 + [0] * 32 + [0] * 32)
        + bytes.fromhex("01 02 020001 0c")
        + (2).to_bytes(4, "little")
        + (1).to_bytes(8, "little")
    )
    data = bytes.fromhex("01 02 8000002c 800001f5") + message
    apdu = bytes.fromhex("e0060100") + bytes([len(data)]) + data
    try:
        up = subprocess.run(
            [sys.executable, "-m", "ledger_rig", "up", "--count", "1", "--app", app],
            stdout=subprocess.PIPE,
            text=True,
            timeout=600,
            check=True,
        )
        path = up.stdout.split()[0]
        refused = _sign(path, apdu, "reject")
        signed = _sign(path, apdu, "approve")
    finally:
        subprocess.run([sys.executable, "-m", "ledger_rig", "down"], check=True)
    assert refused == bytes.fromhex("6985")
    assert len(signed) == 66
    assert signed[64:] == bytes.fromhex("9000")
