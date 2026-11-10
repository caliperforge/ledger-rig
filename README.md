# ledger-rig

Bridges a Speculos APDU socket to a USB HID Ledger device on Linux.

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
sudo python -m ledger_rig bridge --apdu 127.0.0.1:9999 --serial 0001
```

`9999` is the Speculos APDU port. Run one bridge per device, each with its own `--serial`.

The bridge logs one line per APDU, command then response with its status word:

```
-> 5
<- 5 9000
```

It exits once the APDU socket closes.

## Tests

```sh
pytest
sudo "$(which python)" -m pytest -m uhid
```
