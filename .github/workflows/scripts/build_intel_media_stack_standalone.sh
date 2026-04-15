#!/bin/bash
set -euo pipefail

# QSVEncC が依存する Intel Media Stack の構成ライブラリ (gmmlib / libva / media-driver / MediaSDK runtime / oneVPL GPU runtime) を
# Ubuntu 20.04 上でビルドし、thirdparty/Library/ 以下へそのままコピーできる形へ整える CI 環境向けスクリプト
## Intel Media Stack の構成ライブラリ (OpenCL ランタイムを除く) をすべて自己完結型でビルドすることで、
## サードパーティーライブラリ上の QSVEncC がシステム側の iHD_drv_video.so や libmfx に依存しないようにし、
## どのような OS 環境・CPU 世代でも QSVEncC を安定的に動作させ続けることが狙い

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PATCH_DIR="${REPO_ROOT}/.github/workflows/patches"
OUTPUT_ROOT="${1:-${REPO_ROOT}/intel-media-stack}"

: "${INTEL_GMMLIB_TAG:?INTEL_GMMLIB_TAG is required}"
: "${INTEL_LIBVA_TAG:?INTEL_LIBVA_TAG is required}"
: "${INTEL_MEDIA_DRIVER_TAG:?INTEL_MEDIA_DRIVER_TAG is required}"
: "${INTEL_MEDIASDK_TAG:?INTEL_MEDIASDK_TAG is required}"
: "${INTEL_ONEVPL_GPU_TAG:?INTEL_ONEVPL_GPU_TAG is required}"

SRC_ROOT="${OUTPUT_ROOT}/src"
BUILD_ROOT="${OUTPUT_ROOT}/build-root"
BUILD_DIR="${BUILD_ROOT}/work"
PREFIX_DIR="${BUILD_DIR}/prefix"
FREE_PREFIX_DIR="${BUILD_DIR}/prefix-free"
ARTIFACT_DIR="${OUTPUT_ROOT}/artifact"

HOST_UID_VALUE="${HOST_UID:-0}"
HOST_GID_VALUE="${HOST_GID:-0}"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl git patch perl pkg-config build-essential ninja-build cmake meson \
  libdrm-dev libx11-dev libxext-dev libxfixes-dev libxrandr-dev libxrender-dev libxinerama-dev libxcursor-dev libxi-dev \
  libx11-xcb-dev libxcb-dri3-dev libxcb-present-dev \
  wayland-protocols libwayland-dev libwayland-egl-backend-dev libffi-dev libglib2.0-dev libpciaccess-dev libudev-dev libtbb-dev \
  patchelf

mkdir -p "${SRC_ROOT}" "${BUILD_DIR}" "${PREFIX_DIR}" "${FREE_PREFIX_DIR}" \
         "${ARTIFACT_DIR}/Library/dri" "${ARTIFACT_DIR}/Library/libmfx-gen"

export PKG_CONFIG_PATH="${PREFIX_DIR}/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export CMAKE_PREFIX_PATH="${PREFIX_DIR}"
export CFLAGS='-O2'
export CXXFLAGS='-O2'

apply-git-patch() {
  local source_dir="$1"
  local patch_file="$2"

  if git -C "${source_dir}" apply --check "${patch_file}" >/dev/null 2>&1; then
    git -C "${source_dir}" apply "${patch_file}"
    return 0
  fi

  if git -C "${source_dir}" apply --reverse --check "${patch_file}" >/dev/null 2>&1; then
    echo "Patch already applied. patch: ${patch_file}"
    return 0
  fi

  echo "Failed to apply patch. source: ${source_dir}, patch: ${patch_file}" >&2
  return 1
}

if [ ! -d "${SRC_ROOT}/gmmlib" ]; then
  git clone --depth=1 --branch "${INTEL_GMMLIB_TAG}" https://github.com/intel/gmmlib.git "${SRC_ROOT}/gmmlib"
fi
if [ ! -d "${SRC_ROOT}/libva" ]; then
  git clone --depth=1 --branch "${INTEL_LIBVA_TAG}" https://github.com/intel/libva.git "${SRC_ROOT}/libva"
fi
if [ ! -d "${SRC_ROOT}/media-driver" ]; then
  git clone --depth=1 --branch "${INTEL_MEDIA_DRIVER_TAG}" https://github.com/intel/media-driver.git "${SRC_ROOT}/media-driver"
fi
if [ ! -d "${SRC_ROOT}/MediaSDK" ]; then
  git clone --depth=1 --branch "${INTEL_MEDIASDK_TAG}" https://github.com/Intel-Media-SDK/MediaSDK.git "${SRC_ROOT}/MediaSDK"
fi
if [ ! -d "${SRC_ROOT}/vpl-gpu-rt" ]; then
  git clone --depth=1 --branch "${INTEL_ONEVPL_GPU_TAG}" https://github.com/intel/vpl-gpu-rt.git "${SRC_ROOT}/vpl-gpu-rt"
fi

apply-git-patch "${SRC_ROOT}/libva" "${PATCH_DIR}/intel-libva-standalone.patch"
apply-git-patch "${SRC_ROOT}/media-driver" "${PATCH_DIR}/intel-media-driver-vpp-deinterlace-crash-fix.patch"

# gmmlib
cmake -S "${SRC_ROOT}/gmmlib" -B "${BUILD_DIR}/gmmlib" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${PREFIX_DIR}" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DMAJOR_VERSION=22 \
  -DMINOR_VERSION=7 \
  -DPATCH_VERSION=2 \
  -DGMMLIB_API_PATCH_VERSION=1094 \
  -DRUN_TEST_SUITE=OFF
ninja -C "${BUILD_DIR}/gmmlib" -j"$(nproc)"
ninja -C "${BUILD_DIR}/gmmlib" install

# libva
meson setup "${BUILD_DIR}/libva" "${SRC_ROOT}/libva" \
  --buildtype=release \
  --prefix="${PREFIX_DIR}" \
  --sysconfdir='.' \
  --libdir=lib \
  -Ddriverdir=dri \
  -Dwith_x11=yes \
  -Dwith_wayland=yes \
  -Dwith_glx=auto \
  -Ddisable_drm=false \
  -Denable_docs=false
ninja -C "${BUILD_DIR}/libva" -j"$(nproc)"
ninja -C "${BUILD_DIR}/libva" install

# media-driver (iHD 向けの独自カーネルを含む版)
cmake -S "${SRC_ROOT}/media-driver" -B "${BUILD_DIR}/media-driver-non-free" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${PREFIX_DIR}" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DINSTALL_DRIVER_SYSCONF=OFF \
  -DENABLE_KERNELS=ON \
  -DENABLE_NONFREE_KERNELS=ON \
  -DENABLE_PRODUCTION_KMD=ON \
  -DBUILD_CMRTLIB=OFF \
  -DARCH=64 \
  -DLIBVA_DRIVERS_PATH="${PREFIX_DIR}/lib/dri" \
  -DCMAKE_PREFIX_PATH="${PREFIX_DIR}" \
  -DBS_DIR_GMMLIB="${SRC_ROOT}/gmmlib"
ninja -C "${BUILD_DIR}/media-driver-non-free" -j"$(nproc)"
ninja -C "${BUILD_DIR}/media-driver-non-free" install

# media-driver (CMRT 用のフリーカーネル版)
cmake -S "${SRC_ROOT}/media-driver" -B "${BUILD_DIR}/media-driver-free" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${FREE_PREFIX_DIR}" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DINSTALL_DRIVER_SYSCONF=OFF \
  -DENABLE_KERNELS=ON \
  -DENABLE_NONFREE_KERNELS=OFF \
  -DENABLE_PRODUCTION_KMD=ON \
  -DBUILD_CMRTLIB=ON \
  -DARCH=64 \
  -DLIBVA_DRIVERS_PATH="${FREE_PREFIX_DIR}/lib/dri" \
  -DCMAKE_PREFIX_PATH="${PREFIX_DIR}" \
  -DBS_DIR_GMMLIB="${SRC_ROOT}/gmmlib"
ninja -C "${BUILD_DIR}/media-driver-free" -j"$(nproc)"
ninja -C "${BUILD_DIR}/media-driver-free" install

# 旧世代 GPU 向けの後方互換性を維持するため、MediaSDK 系の実ランタイムのみをビルドする
# QSVEncC は libvpl のディスパッチャー相当を静的リンクしているため、libmfx.so.1 は同梱しない
cmake -S "${SRC_ROOT}/MediaSDK" -B "${BUILD_DIR}/MediaSDK" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${PREFIX_DIR}" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DENABLE_OPENCL=OFF \
  -DENABLE_X11_DRI3=ON \
  -DENABLE_WAYLAND=ON \
  -DENABLE_TEXTLOG=ON \
  -DENABLE_STAT=ON \
  -DBUILD_RUNTIME=ON \
  -DBUILD_DISPATCHER=OFF \
  -DBUILD_SAMPLES=OFF \
  -DBUILD_TUTORIALS=OFF \
  -DBUILD_TOOLS=OFF \
  -DBUILD_TESTS=OFF
ninja -C "${BUILD_DIR}/MediaSDK" -j"$(nproc)"
ninja -C "${BUILD_DIR}/MediaSDK" install

# oneVPL GPU ランタイム
cmake -S "${SRC_ROOT}/vpl-gpu-rt" -B "${BUILD_DIR}/vpl-gpu-rt" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${PREFIX_DIR}" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DCMAKE_PREFIX_PATH="${PREFIX_DIR}" \
  -DBUILD_RUNTIME=ON \
  -DMFX_ENABLE_ENCTOOLS=ON \
  -DMFX_ENABLE_AENC=ON \
  -DBUILD_TESTS=OFF \
  -DBUILD_TOOLS=OFF
ninja -C "${BUILD_DIR}/vpl-gpu-rt" -j"$(nproc)"
ninja -C "${BUILD_DIR}/vpl-gpu-rt" install

# 成果物を同梱用ディレクトリへ集約する
cp -df "${PREFIX_DIR}/lib/libigdgmm.so"* "${ARTIFACT_DIR}/Library/"
cp -df "${PREFIX_DIR}/lib/libva.so"* "${ARTIFACT_DIR}/Library/"
cp -df "${PREFIX_DIR}/lib/libva-drm.so"* "${ARTIFACT_DIR}/Library/"
cp -df "${PREFIX_DIR}/lib/libva-x11.so"* "${ARTIFACT_DIR}/Library/"
cp -df "${PREFIX_DIR}/lib/libva-wayland.so"* "${ARTIFACT_DIR}/Library/"
cp -df "${PREFIX_DIR}/lib/libmfx-gen.so"* "${ARTIFACT_DIR}/Library/"
cp -df "${PREFIX_DIR}/lib/libmfxhw64.so"* "${ARTIFACT_DIR}/Library/"
cp -df "${FREE_PREFIX_DIR}/lib/libigfxcmrt.so"* "${ARTIFACT_DIR}/Library/"
cp -f "${PREFIX_DIR}/lib/dri/iHD_drv_video.so" "${ARTIFACT_DIR}/Library/dri/"
if [ -d "${PREFIX_DIR}/lib/libmfx-gen" ]; then
  cp -af "${PREFIX_DIR}/lib/libmfx-gen/." "${ARTIFACT_DIR}/Library/libmfx-gen/"
fi

# ファイルサイズ削減のため、Intel 系ライブラリのデバッグシンボルを削除する
strip --strip-debug "${ARTIFACT_DIR}/Library/libigdgmm.so"* || true
strip --strip-debug "${ARTIFACT_DIR}/Library/dri/iHD_drv_video.so" || true
strip --strip-debug "${ARTIFACT_DIR}/Library/libva.so"* "${ARTIFACT_DIR}/Library/libva-drm.so"* \
                     "${ARTIFACT_DIR}/Library/libva-x11.so"* "${ARTIFACT_DIR}/Library/libva-wayland.so"* || true
strip --strip-debug "${ARTIFACT_DIR}/Library/libmfxhw64.so"* \
                     "${ARTIFACT_DIR}/Library/libmfx-gen.so"* "${ARTIFACT_DIR}/Library/libigfxcmrt.so"* || true
find "${ARTIFACT_DIR}/Library/libmfx-gen" -type f -name '*.so*' -exec strip --strip-debug {} + || true

# 実行時ライブラリ探索パスはビルド時の絶対パスを残さず、サードパーティーライブラリの配置先を基準とした相対パスだけにそろえる
find "${ARTIFACT_DIR}/Library" -maxdepth 1 -type f -name '*.so*' | while read -r file; do
  patchelf --set-rpath '$ORIGIN' "${file}"
  chmod +x "${file}"
done
find "${ARTIFACT_DIR}/Library/libmfx-gen" -type f -name '*.so*' | while read -r file; do
  patchelf --set-rpath '$ORIGIN:$ORIGIN/..' "${file}"
  chmod +x "${file}"
done
patchelf --set-rpath '$ORIGIN:$ORIGIN/..' "${ARTIFACT_DIR}/Library/dri/iHD_drv_video.so"
chmod +x "${ARTIFACT_DIR}/Library/dri/iHD_drv_video.so"

chown -R "${HOST_UID_VALUE}:${HOST_GID_VALUE}" "${OUTPUT_ROOT}" || true
