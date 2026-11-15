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

`up` starts one Speculos container and one bridge per device and prints `<hidraw> <serial> <apdu port> <api port>` for each. Each bridge appends its log to `/tmp/ledger-rig/bridge-<serial>.log`. `down` removes the containers; their bridges exit with them.

```sh
python -m ledger_rig press 0000 right
python -m ledger_rig approve 0000
python -m ledger_rig reject 0000
```

`press` sends one `left`, `right` or `both` button press to that device's Speculos API. `approve` and `reject` wait for a Solana sign review, press right through its screens to that choice, then press both.

```sh
sudo python -m ledger_rig bridge --apdu 127.0.0.1:9999 --serial 0001
sudo python -m ledger_rig unlock 0001
sudo python -m ledger_rig lock 0001
```

`9999` is the Speculos APDU port. Run one bridge per device, each with its own `--serial`.

With `--locked` on `bridge` or `up`, a bridge starts locked: it answers every APDU with `5515` and forwards nothing. `unlock <serial>` makes it forward, `lock <serial>` locks it again; both reach the bridge through `/tmp/ledger-rig/bridge-<serial>.sock`.

The bridge logs one line per APDU, command then response with its status word:

```
2026-11-10T12:00:00.000 -> 5 e001000000
2026-11-10T12:00:00.004 <- 5 9000 0102039000
```

A locked bridge logs its reply as `<- 2 5515 5515`.

It exits once the APDU socket closes.

```sh
sudo python -m ledger_rig hold 0001 --every 2
```

`hold` is a stand-in for another app holding the Ledger, such as Ledger Live. It opens the device's `/dev/hidraw*` node and sends get-app-version (`e001000000`) every `--every` seconds (default 2) until interrupted. This is not Ledger Live's real traffic, which was never checked.

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
