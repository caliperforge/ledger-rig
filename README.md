# ledger-rig

Runs Solana Ledger Nano S Plus devices on Linux for tests: each is a Speculos emulator bridged through uhid to a USB HID Ledger device, opened by clients as `/dev/hidraw*`.

## Requirements

- Linux with `/dev/uhid` (`sudo modprobe uhid`)
- root
- Python 3.11+

## Install

```sh
pip install -e .
```

## Usage

```sh
bash scripts/build-solana-app.sh <tag>
sudo python -m ledger_rig up --count 2 --app apps/solana-nanosp-<tag>.elf
sudo python -m ledger_rig down
```

`up` starts one Speculos container and one bridge per device and prints `<hidraw> <serial> <apdu port>` for each. Each bridge appends its log to `/tmp/ledger-rig/bridge-<serial>.log`. `down` removes the containers; their bridges exit with them.

```sh
sudo python -m ledger_rig bridge --apdu 127.0.0.1:9999 --serial 0001
```

`9999` is the Speculos APDU port. Run one bridge per device, each with its own `--serial`.

The bridge logs one line per APDU, command then response with its status word:

```
2026-11-10T12:00:00.000 -> 5 e001000000
2026-11-10T12:00:00.004 <- 5 9000 0102039000
```

It exits once the APDU socket closes.

## GitHub Action

```yaml
- uses: caliperforge/ledger-rig@v0
  id: rig
  with:
    count: 2
- run: pytest
  env:
    LEDGER_HIDRAW: ${{ steps.rig.outputs.hidraw }}
```

`hidraw` holds the device paths, space-separated, readable and writable by the job user. `app-tag` sets the app-solana commit; its ELF is built once and cached. The devices are removed after the job's main steps.

## Limits

- Linux only, with root for uhid
- hidraw behaviour only, not USB descriptors or macOS IOKit
- At most 2 devices
- Nano S Plus only

## Tests

```sh
pytest
sudo "$(which python)" -m pytest -m uhid
```

## Prior art

- [Speculos](https://github.com/LedgerHQ/speculos) is the emulator; this repo only bridges its APDU socket to the host.
- [Karrq/speculos-hid](https://github.com/Karrq/speculos-hid) (2023) bridged one Speculos to a uhid Ledger first. ledger-rig adds a second device, the GitHub Action, a cached app-solana build and the solana-keychain scenarios in `harness/`.

## License

MIT
