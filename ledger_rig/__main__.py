import argparse
import logging

from ledger_rig import rig
from ledger_rig.bridge import Bridge, control
from ledger_rig.seeds import SEEDS


def _address(value: str) -> tuple[str, int]:
    host, port = value.rsplit(":", 1)
    return host, int(port)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ledger_rig")
    commands = parser.add_subparsers(dest="command", required=True)
    bridge = commands.add_parser("bridge")
    bridge.add_argument("--apdu", type=_address, required=True)
    bridge.add_argument("--serial", required=True)
    bridge.add_argument("--locked", action="store_true")
    up = commands.add_parser("up")
    up.add_argument("--count", type=int, required=True)
    up.add_argument("--app", required=True)
    up.add_argument("--seeds", nargs="+")
    up.add_argument("--locked", action="store_true")
    commands.add_parser("down")
    for command in ("lock", "unlock"):
        commands.add_parser(command).add_argument("serial")
    args = parser.parse_args(argv)
    if args.command == "up":
        seeds = args.seeds or SEEDS[: args.count]
        if len(seeds) != args.count:
            parser.error(f"--count {args.count} needs {args.count} seeds")
        for path, serial, port in rig.up(args.app, seeds, args.locked):
            print(f"{path} {serial} {port}")
        return
    if args.command == "down":
        rig.down()
        return
    if args.command in ("lock", "unlock"):
        try:
            control(args.serial, args.command)
        except OSError:
            parser.error(f"no bridge {args.serial}")
        return
    host, port = args.apdu
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    Bridge(host, port, args.serial, locked=args.locked).run()


if __name__ == "__main__":
    main()
