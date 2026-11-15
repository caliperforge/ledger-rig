import json
import re
import urllib.request
from functools import partial

from ledger_rig import rig

# ragger@6e106094 src/ragger/navigator/navigation_scenario.py, nano TX_REVIEW on NBGL
APPROVE = (
    r"^((Accept risk and (sign (transaction|message|operation))?)"
    r"|(Sign (transaction|message|operation)))$"
)
REJECT = r"^(Reject( (transaction|message|operation))?)$"


def port(serial: str) -> int:
    try:
        return int((rig.LOGS / f"api-{serial}").read_text())
    except FileNotFoundError:
        raise LookupError(serial) from None


def press(port: int, button: str) -> None:
    body = json.dumps({"action": "press-and-release"}).encode()
    url = f"http://127.0.0.1:{port}/button/{button}"
    urllib.request.urlopen(url, body, timeout=rig.TIMEOUT).close()


def screen(port: int) -> list[str]:
    url = f"http://127.0.0.1:{port}/events?currentscreenonly=true"
    with urllib.request.urlopen(url, timeout=rig.TIMEOUT) as reply:
        return [event["text"] for event in json.load(reply)["events"]]


def walk(port: int, pattern: str) -> None:
    rig._poll(lambda: any(text.startswith("Review") for text in screen(port)))
    rig._poll(partial(_step, port, pattern))


def _step(port: int, pattern: str) -> bool:
    texts = screen(port)
    if any(re.fullmatch(pattern, text) for text in texts):
        press(port, "both")
        return True
    if texts:
        press(port, "right")
    return False
