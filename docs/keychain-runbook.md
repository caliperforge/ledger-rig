# keychain runbook on the rig

The phases of solana-keychain's `scripts/ledger-hardware-runbook.sh` at `cd5982c`, and which of them `.github/workflows/keychain-runbook.yml` runs.

Green workflow_dispatch run on main: https://github.com/caliperforge/ledger-rig/actions/runs/44526766290 (commit `d7ee77fa`).

| phase | runbook expects | rig | job or reason |
|---|---|---|---|
| 1 | pass | runs on the rig | phase 1 |
| 2 | fail | runs on the rig | phase 2 |
| 3 | fail | runs on the rig | phase 3 |
| 4a | pass | runs on the rig | phase 4a |
| 4b | pass | runs on the rig | phase 4b |
| 5 | fail | runs on the rig | phase 5: the rig checks the runbook's "must not crash the process" half, so any exit at or under 128 passes. The `NotAvailable` exit stays timing-dependent on the rig, because keychain's hardware tests skip, and so pass, when the device is already gone at the moment they start. |
| 6 | pass, 20 of 20 | runs on the rig | phase 6: the rig checks the signal-termination half the keychain justfile gives this loop, so any exit at or under 128 passes. At `cd5982c` a connect releases its device claim only after replying, so the next connect can fail with "Ledger is busy" ([Busy failures](keychain-307.md#busy-failures)); one of 20 runs exited 101 on a push run. |
| 7 | pass | runs on the rig | phase 7 |
| 8 | pass | stays manual | push run: exit 101, `test_ledger_signer_survives_unplug_replug` FAILED in 47.43s |
| 9 | pass | runs on the rig | phase 9 |
| 10a | fail | runs on the rig | phase 10a |
| 11a | pass | runs on the rig | phase 11a |
| 11b | pass | stays manual | the rig cannot turn on blind signing |

The hand-run explicit-path checklist of phase 10a stays manual.

The rig's limits are in the README's [Limits](../README.md#limits).
