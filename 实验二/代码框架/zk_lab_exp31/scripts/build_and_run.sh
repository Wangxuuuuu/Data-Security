#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
PREFIX_DIR="$ROOT_DIR/deps/install"

cmake -S "$ROOT_DIR" -B "$BUILD_DIR" -DLIBSNARK_PREFIX="$PREFIX_DIR"
cmake --build "$BUILD_DIR" -j"$(nproc)"

cd "$BUILD_DIR"
./mysetup

echo "========== 正例：x=3（期望 验证结果: 1） =========="
printf "3\n" | ./myprove
./myverify

echo "========== 反例：x=2（期望 验证结果: 0） =========="
printf "2\n" | ./myprove
./myverify
