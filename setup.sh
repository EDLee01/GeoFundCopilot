#!/bin/bash
# GeoFund Copilot — nanobot 一键部署脚本
#
# 用法:
#   chmod +x setup.sh && ./setup.sh
#
# 前提:
#   1. 已安装 Python ≥3.11
#   2. 已安装 nanobot: pip install nanobot-ai
#   3. 已运行 nanobot onboard

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NANOBOT_DIR="$HOME/.nanobot"
WORKSPACE="$NANOBOT_DIR/workspace"

echo "🔬 GeoFund Copilot — nanobot 部署"
echo "=================================="

# 检查 nanobot
if ! command -v nanobot &>/dev/null; then
    echo "❌ 未找到 nanobot，请先安装: pip install nanobot-ai"
    exit 1
fi

if [ ! -d "$NANOBOT_DIR" ]; then
    echo "❌ 未找到 ~/.nanobot，请先运行: nanobot onboard"
    exit 1
fi

# 安装 SDK 依赖
echo ""
echo "📦 安装依赖..."
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet

# 部署到 workspace
echo ""
echo "📂 部署到 nanobot workspace..."

# SDK
mkdir -p "$WORKSPACE/geofund"
cp -r "$SCRIPT_DIR/geomind_sdk" "$WORKSPACE/geofund/"
cp -r "$SCRIPT_DIR/scripts" "$WORKSPACE/geofund/"

# Skills
mkdir -p "$WORKSPACE/skills"
cp -r "$SCRIPT_DIR/workspace/skills/geofund" "$WORKSPACE/skills/"

# Agent 配置
cp "$SCRIPT_DIR/workspace/AGENTS.md" "$WORKSPACE/AGENTS.md"
cp "$SCRIPT_DIR/workspace/SOUL.md" "$WORKSPACE/SOUL.md"

echo "  ✅ SDK → $WORKSPACE/geofund/"
echo "  ✅ SKILL.md → $WORKSPACE/skills/geofund/"
echo "  ✅ AGENTS.md + SOUL.md → $WORKSPACE/"

# 检查 config
echo ""
CONFIG="$NANOBOT_DIR/config.json"
if [ -f "$CONFIG" ]; then
    echo "⚙️  config.json 已存在: $CONFIG"
    echo "   请确保已配置:"
    echo "   - providers.deepseek.apiKey"
    echo "   - channels.mochat.claw_token (微信接入)"
else
    echo "⚙️  创建配置模板..."
    cp "$SCRIPT_DIR/config/nanobot.config.example.json" "$CONFIG"
    echo "   请编辑 $CONFIG 填入 API Key"
fi

# 检查 DeepSeek Key
echo ""
if [ -n "$DEEPSEEK_API_KEY" ]; then
    echo "✅ DEEPSEEK_API_KEY 已设置"
else
    echo "⚠️  DEEPSEEK_API_KEY 未设置"
    echo "   设置方式: export DEEPSEEK_API_KEY=sk-xxx"
    echo "   或在 $CONFIG 中配置 providers.deepseek.apiKey"
fi

echo ""
echo "=================================="
echo "🎉 部署完成！"
echo ""
echo "测试命令:"
echo "  nanobot agent -m '帮我查一下用图神经网络预测水质的文献'"
echo ""
echo "启动微信:"
echo "  nanobot gateway"
echo ""
