#!/bin/bash
#
# switch_to_headless_smoke.sh
# 切换到 Profile A：非 Mono headless smoke 环境
#
# 执行：cd game/metacampus-godot && ./tools/switch_to_headless_smoke.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Profile A: Headless Smoke ==="
echo "切换到非 Mono Godot 测试环境..."

# 1. 备份 C# UI 脚本，激活 GDScript stubs
echo "[1/5] 备份 C# UI 脚本 → .cs.bak"
for cs_file in \
    "scripts/csharp/ui/NpcScheduleVisualizer.cs" \
    "scripts/csharp/ui/DebugCommandPanel.cs" \
    "scripts/csharp/ui/QuestDetailPanel.cs" \
    "scripts/csharp/ui/SettlementReportPanel.cs" \
    "scripts/csharp/ui/HudController.cs" \
    "scripts/csharp/ui/QuestBoardController.cs" \
    "scripts/csharp/ui/DashboardController.cs" \
    "scripts/csharp/debug/LocationCalibrationPanel.cs" \
    "scripts/csharp/debug/CSharpSmokeTest.cs"; do

    if [ -f "$cs_file" ]; then
        mv "$cs_file" "$cs_file.bak" 2>/dev/null || true
        echo "  ✓ $cs_file → .bak"
    fi
done

# 2. 更新 .tscn 文件引用：.cs → .gd
echo "[2/5] 更新 scene 引用：.cs → .gd"
find scenes -name "*.tscn" -exec sed -i '' \
    's|path="res://scripts/csharp/\(.*\)\.cs"|path="res://scripts/csharp/\1.gd"|g' {} \;

# 3. project.godot: features 移除 "C#"
echo "[3/5] project.godot: 移除 C# feature"
sed -i '' 's|PackedStringArray("4.6", "C#", "GL Compatibility")|PackedStringArray("4.6", "GL Compatibility")|g' project.godot

# 4. 注释 C# autoloads（保留 AudioManager GDScript stub）
echo "[4/5] project.godot: 注释 C# autoloads"
# 注释所有以 ";TimeManager=" 开头的行（这些是 C# autoloads）
# AudioManager 行没有 ; 开头，保持活跃
sed -i '' '/^;TimeManager=/s/^;/\;/' project.godot  # 确保已注释
sed -i '' '/^;ResourceManager=/s/^;/\;/' project.godot
sed -i '' '/^;SkillManager=/s/^;/\;/' project.godot
sed -i '' '/^;EventManager=/s/^;/\;/' project.godot
sed -i '' '/^;SaveManager=/s/^;/\;/' project.godot
sed -i '' '/^;MetricManager=/s/^;/\;/' project.godot
sed -i '' '/^;NpcRegistry=/s/^;/\;/' project.godot
sed -i '' '/^;GameState=/s/^;/\;/' project.godot
sed -i '' '/^;QuestManager=/s/^;/\;/' project.godot
# 确保 AudioManager（GDScript）保持激活
sed -i '' '/^AudioManager=/s/^;.*AudioManager/AudioManager/' project.godot 2>/dev/null || true

# 5. 确认切换完成
echo "[5/5] 验证切换状态"
CS_COUNT=$(find scripts/csharp -name '*.cs' ! -name '*.cs.bak' 2>/dev/null | wc -l | tr -d ' ')
CS_BAK_COUNT=$(find scripts/csharp -name '*.cs.bak' 2>/dev/null | wc -l | tr -d ' ')
GD_COUNT=$(find scripts/csharp -name '*.gd' 2>/dev/null | wc -l | tr -d ' ')
FEATURES=$(grep '^config/features' project.godot)
C_AUTOLOADS=$(grep -c '^;' project.godot 2>/dev/null || echo 0)

echo ""
echo "  GDScript stubs: $GD_COUNT"
echo "  C# scripts (active): $CS_COUNT"
echo "  C# scripts (backed up): $CS_BAK_COUNT"
echo "  Features: $FEATURES"
echo "  Commented autoloads: $C_AUTOLOADS"
echo ""
echo "=== Profile A ready ==="
echo "运行：/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --quit"