# Two-device test for solana-keychain #358

Scenarios from dev-jodee's review of #358, run by `.github/workflows/keychain-307.yml` against
`004999a`, `0b7bf83` (the #358 head) and `4db0db2` (caliperforge/solana-keychain #7):

- A: signers held on `0000` and `0001`, then 50 reads alternating `0000`, `0001`; every read returns its own key.
- B: as A, with bridge `0001` killed and respawned before read 26; no read returns the other device's key.
- C: bridge `0001` killed, an unnamed signer connects (key `0000`), bridge respawned, a signer held on `0001`, then 50 reads alternating the unnamed signer's `is_available` and a `0001` read.
- D: a signer held on `0000` reads its key, a second signer connects on `0001`, then `0000` is read again at once; that read returns key `0000` with no error.

## Commands

```sh
git -C keychain checkout --detach <commit>
cp keychain/rust/Cargo.lock harness/keychain/
cargo build --release --manifest-path harness/keychain/Cargo.toml
sudo strace -f -qq -e trace=openat -o trace-<scenario> \
  harness/keychain/target/release/keychain-harness <scenario> <commit> <hidraw0000> <hidraw0001> <key0000> <key0001>
grep -c '"/dev/hidraw' trace-<scenario>
```

## Results

Run https://github.com/caliperforge/ledger-rig/actions/runs/42945997769 (commit `127d762`):

| commit | scenario | result | error | detail | wall ms | HID opens |
|---|---|---|---|---|---|---|
| 004999a | A | pass |  |  | 77445 | 104 |
| 004999a | B | pass |  |  | 77274 | 104 |
| 004999a | C | fail | unnamed signer unavailable at read 1 | is_available() returned false; no error value | 2943 | 5 |
| 004999a | D | pass |  |  | 4160 | 6 |
| 0b7bf83 | A | fail | read 1: signer unavailable | is_available() returned false; no error value | 2368 | 4 |
| 0b7bf83 | B | fail | Signer not available | SignerError::NotAvailable([REDACTED]): no Ledger device at host path `/dev/hidraw0` | 700 | 2 |
| 0b7bf83 | C | fail | unnamed signer unavailable at read 1 | is_available() returned false; no error value | 3001 | 5 |
| 0b7bf83 | D | fail | read 2: signer unavailable | is_available() returned false; no error value | 2692 | 4 |
| 4db0db2 | A | pass |  |  | 18448 | 2 |
| 4db0db2 | B | pass |  |  | 18994 | 3 |
| 4db0db2 | C | pass |  |  | 18915 | 2 |
| 4db0db2 | D | pass |  |  | 2127 | 2 |

## What failed and why

From run https://github.com/caliperforge/ledger-rig/actions/runs/42945997769, artifacts `bridge-logs-0b7bf83` and `bridge-logs-004999a`.

### `0b7bf83 D`

Detail: `is_available() returned false; no error value`.

Read 2 sent `bridge-0000-0b7bf83-D.log:13` `2026-11-11T02:29:09.505 -> 18 e00500000d038000002c800001f58000`, the last line on bridge `0000`; no `<-` line follows it. The line before it is `bridge-0000-0b7bf83-D.log:12` `2026-11-11T02:29:08.796 <- 34 9000 5eb9862fe23e544a2a0969cc157cb31f`.

Bridge `0000` logged no line while bridge `0001` logged lines 5–10, so no reply to `0001`'s enumeration shows on `0000`:

- `bridge-0001-0b7bf83-D.log:5` `2026-11-11T02:29:08.797 -> 5 e004000000`
- `bridge-0001-0b7bf83-D.log:6` `2026-11-11T02:29:08.798 <- 7 9000 00000110019000`
- `bridge-0001-0b7bf83-D.log:7` `2026-11-11T02:29:08.798 -> 14 e005000009028000002c800001f5`
- `bridge-0001-0b7bf83-D.log:8` `2026-11-11T02:29:09.127 <- 34 9000 b2a722dc18dd5c49c3f48e9b0726f11b`
- `bridge-0001-0b7bf83-D.log:9` `2026-11-11T02:29:09.164 -> 18 e00500000d038000002c800001f58000`
- `bridge-0001-0b7bf83-D.log:10` `2026-11-11T02:29:09.504 <- 34 9000 e9b6062841bb977ad21de71ec9619006`

The logs show bridge `0000` logged no reply to read 2's APDU; they do not show why `is_available()` returned false.

### `004999a C`

Detail: `is_available() returned false; no error value`.

`bridge-0000-004999a-C.log` lines 1–6 run from `02:31:27.711` to `bridge-0000-004999a-C.log:6` `2026-11-11T02:31:28.374 <- 34 9000 1572e52f2c5e7e66bc19ac6cd30b6d69`, before `bridge-0001-004999a-C.log:1` `2026-11-11T02:31:28.967 -> 5 e004000000`.

The last lines on each bridge:

- `bridge-0000-004999a-C.log:11` `2026-11-11T02:31:29.790 -> 5 e004000000`
- `bridge-0000-004999a-C.log:12` `2026-11-11T02:31:29.791 <- 7 9000 00000110019000`
- `bridge-0000-004999a-C.log:13` `2026-11-11T02:31:29.791 -> 14 e005000009028000002c800001f5`
- `bridge-0000-004999a-C.log:14` `2026-11-11T02:31:30.113 <- 34 9000 5eb9862fe23e544a2a0969cc157cb31f`
- `bridge-0001-004999a-C.log:7` `2026-11-11T02:31:30.114 -> 5 e004000000`
- `bridge-0001-004999a-C.log:8` `2026-11-11T02:31:30.115 <- 7 9000 00000110019000`
- `bridge-0001-004999a-C.log:9` `2026-11-11T02:31:30.115 -> 14 e005000009028000002c800001f5`
- `bridge-0001-004999a-C.log:10` `2026-11-11T02:31:30.429 <- 34 9000 b2a722dc18dd5c49c3f48e9b0726f11b`

Every `<-` line on both bridges (`0000` lines 2, 4, 6, 8, 10, 12, 14; `0001` lines 2, 4, 6, 8, 10) has status `9000`.

The logs show no cause for the unnamed signer being unavailable.

## Busy failures

Run https://github.com/caliperforge/ledger-rig/actions/runs/43130238317 (workflow_dispatch, `repeat: 20`, commit `620718f1ecaf41a679e03e205a95c142ab137746`):

| commit | runs | busy A | busy B | busy C | busy D | other failures | job |
|---|---|---|---|---|---|---|---|
| 4db0db2 | 20 | 6 | 3 | 0 | 0 | 0 | https://github.com/caliperforge/ledger-rig/actions/runs/43130238317/job/130892297672 |
| 4db0db2+claim | 20 | 0 | 0 | 0 | 0 | 0 | https://github.com/caliperforge/ledger-rig/actions/runs/43130238317/job/130892297595 |

Verdict: race confirmed.

## Busy failures (11-12)

Run https://github.com/caliperforge/ledger-rig/actions/runs/43281042252 (workflow_dispatch, `repeat: 20`, commit `a2bd6f3c045b8a1effe9f707b9aebb8430b705b6`):

| commit | runs | busy A | busy B | busy C | busy D | other failures | job |
|---|---|---|---|---|---|---|---|
| cd5982c | 20 | 4 | 4 | 0 | 0 | 20 | https://github.com/caliperforge/ledger-rig/actions/runs/43281042252/job/131402063315 |
| cd5982c+claim | 20 | 0 | 0 | 0 | 0 | 20 | https://github.com/caliperforge/ledger-rig/actions/runs/43281042252/job/131402063459 |
| aa66be2 | 20 | 2 | 4 | 0 | 0 | 0 | https://github.com/caliperforge/ledger-rig/actions/runs/43281042252/job/131402063297 |
| aa66be2+claim | 20 | 0 | 0 | 0 | 0 | 0 | https://github.com/caliperforge/ledger-rig/actions/runs/43281042252/job/131402063118 |

## Limit

emulated Speculos devices on Linux hidraw, not physical Ledgers, and not macOS
