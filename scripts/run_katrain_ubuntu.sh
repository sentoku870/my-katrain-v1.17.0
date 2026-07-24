#!/usr/bin/env bash
# Ubuntu/WSL から katrain を起動するスクリプト
# 用途: WSL Ubuntu 環境で katrain を起動する
#
# 事前準備:
#   sudo apt install -y xvfb xclip xsel \
#     libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
#     libmtdev1t64
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
# .venv のみ使用（.venv-linux は廃止: KivyMD 1.2.0 と乖離した古い環境を
# 優先してしまう問題があった）。CUDA 版 KataGo を使う場合は .venv に
# NVIDIA パッケージを追加インストールすること。
VENV_DIR="$REPO_ROOT/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "[ERROR] .venv not found. Run: uv sync"
  exit 1
fi

export VIRTUAL_ENV="$VENV_DIR"
export UV_PROJECT_ENVIRONMENT="$VENV_DIR"
echo "[INFO] Using venv: $VENV_DIR"

# === 環境変数 ===
# libGL_ALWAYS_SOFTWARE=1 は WSLg の GPU パスと相性が悪いので外す
# export LIBGL_ALWAYS_SOFTWARE=1
export SDL_AUDIODRIVER=${SDL_AUDIODRIVER:-dummy}

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
  exec xvfb-run -a uv run --frozen python /tmp/_katrain_pygame_wrapper.py "$@"
else
  echo "[INFO] Starting with DISPLAY=$DISPLAY (WSLg)"
  exec uv run --frozen python /tmp/_katrain_pygame_wrapper.py "$@"
fi