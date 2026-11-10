#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: scripts/build-solana-app.sh <tag>" >&2
  exit 2
fi
tag=$1

src=$(mktemp -d)
trap 'rm -rf "$src"' EXIT

git clone --depth 1 --branch "$tag" https://github.com/LedgerHQ/app-solana "$src"
docker run --rm --user "$(id -u):$(id -g)" -v "$src:/app" -w /app \
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-builder sh -c 'make BOLOS_SDK=$NANOSP_SDK'
mkdir -p apps
cp "$src/build/nanos2/bin/app.elf" "apps/solana-nanosp-$tag.elf"
