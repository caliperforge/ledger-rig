import argparse
import logging

from ledger_rig import buttons, rig
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
    bridge.add_argument("--dashboard", action="store_true")
    up = commands.add_parser("up")
    up.add_argument("--count", type=int, required=True)
    up.add_argument("--app", required=True)
    up.add_argument("--seeds", nargs="+")
    up.add_argument("--locked", action="store_true")
    up.add_argument("--dashboard", action="store_true")
    commands.add_parser("down")
    for command in ("lock", "unlock"):
        commands.add_parser(command).add_argument("serial")
    press = commands.add_parser("press")
    press.add_argument("serial")
    press.add_argument("button", choices=["left", "right", "both"])
    commands.add_parser("approve").add_argument("serial")
    commands.add_parser("reject").add_argument("serial")
    args = parser.parse_args(argv)
    if args.command == "up":
        seeds = args.seeds or SEEDS[: args.count]
        if len(seeds) != args.count:
            parser.error(f"--count {args.count} needs {args.count} seeds")
        devices = rig.up(args.app, seeds, args.locked, args.dashboard)
        for path, serial, port, api in devices:
            print(f"{path} {serial} {port} {api}")
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
    if args.command in ("press", "approve", "reject"):
        try:
            api = buttons.port(args.serial)
        except LookupError:
            parser.error(f"no device {args.serial}: run up first")
        if args.command == "press":
            buttons.press(api, args.button)
        elif args.command == "approve":
            buttons.walk(api, buttons.APPROVE)
        else:
            buttons.walk(api, buttons.REJECT)
        return
    host, port = args.apdu
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    Bridge(host, port, args.serial, locked=args.locked, dashboard=args.dashboard).run()


if __name__ == "__main__":
    main()
