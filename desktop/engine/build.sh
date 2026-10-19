#!/usr/bin/env bash
# Builds clipnera-engine with swiftc. SwiftPM isn't used because it crashes in some
# Command Line Tools installs, and an SDK newer than the compiler won't build, so this
# picks the newest installed macOS SDK that was made with the same Swift version.
set -euo pipefail
cd "$(dirname "$0")"

config="${1:-release}"
out=".build/$config"
mkdir -p "$out"

pick_sdk() {
  local compiler sdks sdk
  compiler="$(swiftc --version 2>&1 | sed -n 's/.*Apple Swift version \([0-9]*\.[0-9]*\).*/\1/p' | head -1)"
  sdks="$(dirname "$(xcrun --show-sdk-path)")"
  for sdk in $(ls -1dr "$sdks"/MacOSX*.sdk); do
    if grep -qs "swift-compiler-version: Apple Swift version $compiler" "$sdk"/usr/lib/swift/Swift.swiftmodule/arm64e-apple-macos.swiftinterface; then
      echo "$sdk"
      return
    fi
  done
  xcrun --show-sdk-path
}

binary="$out/clipnera-engine"
if [ -x "$binary" ] && [ -z "$(find Sources build.sh -newer "$binary")" ]; then
  echo "clipnera-engine is up to date"
  exit 0
fi

sdk="${SDKROOT:-$(pick_sdk)}"
flags=(-O)
[ "$config" = debug ] && flags=(-Onone -g)

swiftc "${flags[@]}" -swift-version 5 -sdk "$sdk" -target arm64-apple-macos15 \
  -o "$binary" Sources/*.swift
echo "Built $binary"
