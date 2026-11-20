# Changelog

## 0.2.0

- `up` and the Action's `count` take up to 8 devices.
- `up` prints `<hidraw> <serial> <apdu port> <api port>` for each device.
- `press` sends one button press; `approve` and `reject` walk a Solana sign review to that choice.
- `--locked` on `bridge` and `up` starts a bridge locked; `lock` and `unlock` toggle it.
- `--dashboard` on `bridge` and `up`, and the Action's `dashboard` input, start each device as the BOLOS dashboard.
- `hold` opens a device and sends get-app-version on a timer, as a stand-in for another app holding the Ledger.
- `.github/workflows/keychain-runbook.yml` and `examples/keychain/runbook.md` mark which phases of solana-keychain's hardware runbook run on the rig.
- The keychain docs move from `docs/` to `examples/keychain/`.
- The README leads with a quickstart.

## 0.1.0

- `bridge` connects a Speculos APDU socket to a uhid hidraw device and logs one line per APDU.
- `up` and `down` start and remove at most 2 devices; `up` prints `<hidraw> <serial> <apdu port>` for each.
- `scripts/build-solana-app.sh` builds the app-solana ELF.
- The Action `caliperforge/ledger-rig@v0` takes `count` (at most 2) and `app-tag`, outputs `hidraw`, and removes the devices after the job.
- The keychain-307 harness, `docs/keychain-307.md` and `.github/workflows/keychain-307.yml` run solana-keychain against two rig devices.
