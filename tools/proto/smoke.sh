#!/usr/bin/env bash
# 链路冒烟：macOS 系统 TTS 合成音频 + tiny 模型，验证脚本能跑通
# 注意：TTS 语音识别质量极高，看不出热词差异，仅验证脚本本身
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$ROOT/tools/proto/.venv"
AUDIO="/tmp/meetrec-smoke.aiff"
REPORT="$ROOT/tools/proto/smoke-report.md"

[ -x "$VENV/bin/python" ] || { echo "先跑 bash tools/proto/setup.sh"; exit 1; }
command -v say >/dev/null || { echo "找不到 say 命令（仅 macOS 可用）"; exit 1; }

echo "== 合成演示音频 =="
say -v Eddy -o "$AUDIO" -r 165   '今天会议主要讨论 MeetRec Master 的整体方案。张一鸣他们负责 PySide6 的界面部分，雷军那边负责 faster-whisper 的集成。CTranslate2 的 int8 量化效果不错，VAD 模块用 Silero，打包用 PyInstaller，Windows 那边还要处理 Authenticode 签名和 SmartScreen 提示。纪要部分对接 OpenAI 兼容接口。'

echo "== 运行原型（tiny 模型，冒烟用）=="
"$VENV/bin/python" "$ROOT/tools/proto/keyword_probe.py"   --audio "$AUDIO"   --keywords-file "$ROOT/tools/proto/keywords.example.txt"   --aliases-file "$ROOT/tools/proto/aliases.example.txt"   --model tiny   --report "$REPORT"

echo
echo "== 冒烟完成，报告：$REPORT =="
