import argparse
import logging

from ledger_rig.bridge import Bridge


def _address(value: str) -> tuple[str, int]:
    host, port = value.rsplit(":", 1)
    return host, int(port)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ledger_rig")
    commands = parser.add_subparsers(dest="command", required=True)
    bridge = commands.add_parser("bridge")
    bridge.add_argument("--apdu", type=_address, required=True)
    bridge.add_argument("--serial", required=True)
    args = parser.parse_args(argv)
    host, port = args.apdu
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    Bridge(host, port, args.serial).run()


if __name__ == "__main__":
    main()
