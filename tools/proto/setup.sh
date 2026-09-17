#!/usr/bin/env bash
# MeetRec Master 热词原型验证工具 · 环境准备
# 用法：bash tools/proto/setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$ROOT/tools/proto/.venv"
PY="${PYTHON:-python3.11}"

echo "== 检查 Python =="
"$PY" --version || { echo "需要 Python 3.11（当前：$PY）"; exit 1; }

if [ ! -d "$VENV" ]; then
  echo "== 创建虚拟环境 $VENV =="
  "$PY" -m venv "$VENV"
fi

echo "== 升级 pip =="
"$VENV/bin/pip" install --upgrade pip wheel -q

echo "== 安装依赖（首次约 3-5 分钟）=="
"$VENV/bin/pip" install faster-whisper pypinyin rapidfuzz av numpy

echo
echo "== 完成 =="
echo "激活环境："
echo "  source $VENV/bin/activate"
echo
echo "快速冒烟（系统 TTS + tiny 模型，只验证链路）："
echo "  bash tools/proto/smoke.sh"
echo
echo "正式验证（用自己的会议录音）："
echo "  $VENV/bin/python tools/proto/keyword_probe.py"
echo "      --audio /path/to/meeting.mp3"
echo "      --keywords-file tools/proto/keywords.example.txt"
echo "      --aliases-file  tools/proto/aliases.example.txt"
echo "      --model large-v3-turbo"
