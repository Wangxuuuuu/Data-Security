#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPS_DIR="$ROOT_DIR/deps"
LIBSNARK_DIR="$DEPS_DIR/libsnark"
INSTALL_PREFIX="$DEPS_DIR/install"
JOBS="${JOBS:-$(nproc)}"

sudo apt-get update
sudo apt-get install -y \
  build-essential cmake git libgmp3-dev libprocps-dev python3-markdown \
  libboost-program-options-dev libssl-dev python3 pkg-config libtool automake

mkdir -p "$DEPS_DIR"

git config --global http.version HTTP/1.1
git config --global http.postBuffer 524288000

if [[ ! -f "$LIBSNARK_DIR/CMakeLists.txt" ]]; then
  rm -rf "$LIBSNARK_DIR"
  for i in 1 2 3; do
    if git clone --depth 1 https://github.com/scipr-lab/libsnark.git "$LIBSNARK_DIR"; then
      break
    fi
    if [[ "$i" -eq 3 ]]; then
      echo "libsnark 仓库克隆失败，请检查网络后重试。"
      exit 1
    fi
    rm -rf "$LIBSNARK_DIR"
    echo "克隆失败，准备重试 ($i/3)..."
  done
fi

cd "$LIBSNARK_DIR"

# 兼容手动拷贝源码包的场景：如果目录不是 git 仓库，则跳过 submodule 命令。
if [[ -d .git ]]; then
  for i in 1 2 3; do
    if git submodule update --init --recursive; then
      break
    fi
    if [[ "$i" -eq 3 ]]; then
      echo "子模块拉取失败，请检查网络后重试。"
      exit 1
    fi
    echo "子模块拉取失败，准备重试 ($i/3)..."
  done
else
  echo "检测到手动拷贝的源码目录（非 git 仓库），跳过 submodule 拉取。"
fi

if [[ ! -d "$LIBSNARK_DIR/libsnark" ]]; then
  echo "目录结构异常：未找到 libsnark 源码子目录。"
  echo "请确认你拷贝的是完整源码目录，并且包含 CMakeLists.txt 与 libsnark 子目录。"
  exit 1
fi

required_submodules=(
  "depends/gtest/CMakeLists.txt"
  "depends/libff/CMakeLists.txt"
  "depends/libfqfft/CMakeLists.txt"
)

missing=0
for rel in "${required_submodules[@]}"; do
  if [[ ! -f "$LIBSNARK_DIR/$rel" ]]; then
    echo "缺少依赖文件: $LIBSNARK_DIR/$rel"
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  cat <<'EOF'

当前 libsnark 目录不是完整可编译版本（子模块内容缺失）。
如果你使用的是 GitHub 的 Source Code(zip)，请继续手动补齐子模块源码：
1) gtest
2) libff
3) libfqfft

补齐后请保证以下文件存在：
- depends/gtest/CMakeLists.txt
- depends/libff/CMakeLists.txt
- depends/libfqfft/CMakeLists.txt

然后重新运行：
./scripts/install_libsnark.sh
EOF
  exit 1
fi

mkdir -p build
cd build

cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX"

make -j"$JOBS"
make install

echo "libsnark installed to: $INSTALL_PREFIX"
