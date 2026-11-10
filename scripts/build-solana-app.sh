#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: scripts/build-solana-app.sh <tag>" >&2
  exit 2
fi
tag=$1

src=$(mktemp -d)
trap 'rm -rf "$src"' EXIT

git -C "$src" init -q
git -C "$src" fetch -q --depth 1 https://github.com/LedgerHQ/app-solana "$tag"
git -C "$src" checkout -q FETCH_HEAD
docker run --rm --user "$(id -u):$(id -g)" -v "$src:/app" -w /app \
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-builder sh -c 'make BOLOS_SDK=$NANOSP_SDK'
mkdir -p apps
cp "$src/build/nanos2/bin/app.elf" "apps/solana-nanosp-$tag.elf"
