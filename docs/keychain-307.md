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

## Limit

emulated Speculos devices on Linux hidraw, not physical Ledgers, and not macOS
