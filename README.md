# ledger-rig

Runs Solana Ledger Nano S Plus devices on Linux for tests: each is a Speculos emulator bridged through uhid to a USB HID Ledger device, opened by clients as `/dev/hidraw*`. It is for hidapi and hidraw clients that need a Ledger in CI with no hardware, where the code cannot be pointed at Speculos over TCP, such as Rust `hidapi` wallets.

## In GitHub Actions

```yaml
- uses: caliperforge/ledger-rig@v0
  id: rig
  with:
    count: 2
- run: pytest
  env:
    LEDGER_HIDRAW: ${{ steps.rig.outputs.hidraw }}
```

`hidraw` holds the device paths, space-separated, readable and writable by the job user. `app-tag` sets the app-solana commit; its ELF is built once and cached. `dashboard: true` starts each device as the BOLOS dashboard, as `--dashboard` does; the node a device comes back at after opening Solana is root-only. The devices are removed after the job's main steps.

## On your machine

- Linux with `/dev/uhid` (`sudo modprobe uhid`)
- root
- Python 3.11+

```sh
pip install -e .
bash scripts/build-solana-app.sh <tag>
sudo python -m ledger_rig up --count 2 --app apps/solana-nanosp-<tag>.elf
python -m ledger_rig approve 0000
sudo python -m ledger_rig down
```

`up` starts one Speculos container and one bridge per device and prints `<hidraw> <serial> <apdu port> <api port>` for each. Each bridge appends its log to `/tmp/ledger-rig/bridge-<serial>.log`. `down` removes the containers; their bridges exit with them.

`press` sends one `left`, `right` or `both` button press to that device's Speculos API. `approve` and `reject` wait for a Solana sign review, press right through its screens to that choice, then press both.

## Commands

```sh
sudo python -m ledger_rig up --count 2 --app apps/solana-nanosp-<tag>.elf --dashboard
python -m ledger_rig press 0000 right
python -m ledger_rig reject 0000
```

```sh
sudo python -m ledger_rig bridge --apdu 127.0.0.1:9999 --serial 0001
sudo python -m ledger_rig bridge --apdu 127.0.0.1:9999 --serial 0001 --dashboard
sudo python -m ledger_rig unlock 0001
sudo python -m ledger_rig lock 0001
```

`9999` is the Speculos APDU port. Run one bridge per device, each with its own `--serial`.

## Locked

With `--locked` on `bridge` or `up`, a bridge starts locked: it answers every APDU with `5515` and forwards nothing. `unlock <serial>` makes it forward, `lock <serial>` locks it again; both reach the bridge through `/tmp/ledger-rig/bridge-<serial>.sock`.

## Dashboard

With `--dashboard` on `bridge` or `up`, the device starts as the BOLOS dashboard: it answers get-app-and-version with `BOLOS` and refuses other APDUs. Opening `Solana` answers `9000`, recreates the device at a new `/dev/hidraw*` path and forwards to Speculos from then on.

## Hold

```sh
sudo python -m ledger_rig hold 0001 --every 2
```

`hold` is a stand-in for another app holding the Ledger, such as Ledger Live. It opens the device's `/dev/hidraw*` node and sends get-app-version (`e001000000`) every `--every` seconds (default 2) until interrupted. This is not Ledger Live's real traffic, which was never checked.

## Logs

The bridge logs one line per APDU, command then response with its status word:

```
2026-11-10T12:00:00.000 -> 5 e001000000
2026-11-10T12:00:00.004 <- 5 9000 0102039000
```

A locked bridge logs its reply as `<- 2 5515 5515`.

It exits once the APDU socket closes.

## Limits

- Linux only, with root for uhid
- hidraw behaviour only, not USB descriptors or macOS IOKit
- At most 8 devices
- Nano S Plus only
- Dashboard mode emulates only the hidraw path change on app launch, not the USB PID change

## Tests

```sh
pytest
sudo "$(which python)" -m pytest -m uhid
```

## Examples

[examples/keychain/](examples/keychain/) runs solana-keychain against two rig devices.

[examples/keychain/runbook.md](examples/keychain/runbook.md) marks which phases of solana-keychain's hardware runbook run on the rig.

## Prior art

- [Speculos](https://github.com/LedgerHQ/speculos) is the emulator; this repo only bridges its APDU socket to the host.
- [Karrq/speculos-hid](https://github.com/Karrq/speculos-hid) (2023) bridged one Speculos to a uhid Ledger first. ledger-rig adds a second device, the GitHub Action, a cached app-solana build and the solana-keychain scenarios in `harness/`.

## License

MIT
