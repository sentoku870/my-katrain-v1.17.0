#!/usr/bin/env bash
# Ubuntu/WSL から katrain を起動するスクリプト
# 用途: WSL Ubuntu 環境で katrain を起動する
#
# 事前準備:
#   sudo apt install -y xvfb xclip xsel \
#     libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
#     libmtdev1t64
#   uv pip install pygame (in .venv-linux)
#
# このスクリプトは Kivy の pygame backend を使って katrain を起動します。
# まず WSLg (DISPLAY=:0) での起動を試み、失敗時のみ Xvfb にフォールバックします。
#
# 使い方:
#   ./scripts/run_katrain_ubuntu.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# === venv 選択 ===
VENV_LINUX="$REPO_ROOT/.venv-linux"
VENV_DEFAULT="$REPO_ROOT/.venv"

if [ -d "$VENV_LINUX" ]; then
  VENV_DIR="$VENV_LINUX"
elif [ -d "$VENV_DEFAULT" ]; then
  VENV_DIR="$VENV_DEFAULT"
else
  echo "[ERROR] No virtual environment found. Run: uv sync"
  exit 1
fi

export VIRTUAL_ENV="$VENV_DIR"
export UV_PROJECT_ENVIRONMENT="$VENV_DIR"
echo "[INFO] Using venv: $VENV_DIR"

# === 環境変数 ===
# libGL_ALWAYS_SOFTWARE=1 は WSLg の GPU パスと相性が悪いので外す
# export LIBGL_ALWAYS_SOFTWARE=1
export SDL_AUDIODRIVER=${SDL_AUDIODRIVER:-dummy}

# CUDA 版 KataGo 用: venv の NVIDIA ライブラリを LD_LIBRARY_PATH に追加
NVIDIA_LIB_DIR="$VENV_DIR/lib/python3.13/site-packages/nvidia"
if [ -d "$NVIDIA_LIB_DIR/cublas/lib" ]; then
  export LD_LIBRARY_PATH="$NVIDIA_LIB_DIR/cublas/lib:$NVIDIA_LIB_DIR/cudnn/lib:$NVIDIA_LIB_DIR/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}"
  echo "[INFO] NVIDIA CUDA libraries: $NVIDIA_LIB_DIR"
fi

# === 起動モード選択 ===
# DISPLAY=:0 (WSLg) が利用可能なら優先 → Windows 側にウィンドウ表示
# そうでなければ Xvfb で仮想ディスプレイ（ウィンドウは見えないが動作確認可）
USE_XVFB=${USE_XVFB:-auto}

if [ "$USE_XVFB" = "auto" ]; then
  # WSLg の DISPLAY=:0 が使えるか確認
  if [ -n "${DISPLAY:-}" ] && [ -S "/tmp/.X11-unix/X${DISPLAY#:}" ] 2>/dev/null; then
    USE_XVFB=no
  elif [ -S "/tmp/.X11-unix/X0" ] && command -v xclip >/dev/null && command -v xsel >/dev/null; then
    USE_XVFB=no
    export DISPLAY=:0
  elif command -v xvfb-run >/dev/null 2>&1; then
    USE_XVFB=yes
  else
    echo "[ERROR] Neither WSLg DISPLAY nor xvfb-run available"
    echo "        Install: sudo apt install -y xvfb xclip xsel"
    exit 1
  fi
fi

echo "[INFO] Display mode: $([ "$USE_XVFB" = "yes" ] && echo "Xvfb (virtual, invisible)" || echo "WSLg (Windows desktop visible)")"
echo ""

# KIVY_WINDOW=pygame 環境変数は反映されないため、Config.set を使うラッパー
cat > /tmp/_katrain_pygame_wrapper.py <<'PYEOF'
import os
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

from kivy.config import Config
Config.set('graphics', 'window', 'pygame')
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

from katrain.__main__ import run_app
run_app()
PYEOF

if [ "$USE_XVFB" = "yes" ]; then
  if ! command -v xvfb-run >/dev/null 2>&1; then
    echo "[ERROR] xvfb-run not found. Install: sudo apt install -y xvfb"
    exit 1
  fi
  echo "[INFO] Starting with Xvfb virtual display"
  unset DISPLAY
  unset WAYLAND_DISPLAY
  exec xvfb-run -a uv run --no-sync python /tmp/_katrain_pygame_wrapper.py "$@"
else
  echo "[INFO] Starting with DISPLAY=$DISPLAY (WSLg)"
  exec uv run --no-sync python /tmp/_katrain_pygame_wrapper.py "$@"
fi