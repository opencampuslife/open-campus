#!/bin/bash
#
# switch_to_csharp_runtime.sh
# 切换到 Profile B：C# 运行时环境
#
# 执行：cd game/metacampus-godot && ./tools/switch_to_csharp_runtime.sh
# 注意：当前 Godot Mono headless 有 bug，建议在 Godot Mono GUI 模式下验证

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Profile B: C# Runtime ==="
echo "切换到 C# 运行时环境（需要 Godot Mono GUI 验证）..."

# 1. 恢复 C# UI 脚本
echo "[1/5] 恢复 C# UI 脚本：.cs.bak → .cs"
for cs_bak_file in \
    "scripts/csharp/ui/NpcScheduleVisualizer.cs.bak" \
    "scripts/csharp/ui/DebugCommandPanel.cs.bak" \
    "scripts/csharp/ui/QuestDetailPanel.cs.bak" \
    "scripts/csharp/ui/SettlementReportPanel.cs.bak" \
    "scripts/csharp/ui/HudController.cs.bak" \
    "scripts/csharp/ui/QuestBoardController.cs.bak" \
    "scripts/csharp/ui/DashboardController.cs.bak" \
    "scripts/csharp/debug/LocationCalibrationPanel.cs.bak" \
    "scripts/csharp/debug/CSharpSmokeTest.cs.bak"; do

    if [ -f "$cs_bak_file" ]; then
        mv "$cs_bak_file" "${cs_bak_file%.bak}" 2>/dev/null || true
        echo "  ✓ $cs_bak_file → ${cs_bak_file%.bak}"
    fi
done

# 2. 更新 .tscn 文件引用：如果 .cs 存在，指向 .cs；否则保持 .gd
echo "[2/5] 更新 scene 引用"
# 对于每个有 .cs 的文件，更新 .tscn 引用
for gd_file in scripts/csharp/ui/*.gd scripts/csharp/debug/*.gd; do
    if [ -f "${gd_file%.gd}.cs" ]; then
        # .cs 存在，切换回来
        cs_path=$(echo "$gd_file" | sed 's|scripts/|scripts/|;s|\.gd|.cs|')
        tsn_file=$(grep -rl "path=\"res://${gd_file}\"" scenes/ 2>/dev/null || true)
        if [ -n "$tsn_file" ]; then
            sed -i '' "s|path=\"res://${gd_file}\"|path=\"res://${cs_path}\"|g" $tsn_file
        fi
    fi
done

# 3. project.godot: features 添加 "C#"
echo "[3/5] project.godot: 添加 C# feature"
sed -i '' 's|PackedStringArray("4.6", "GL Compatibility")|PackedStringArray("4.6", "C#", "GL Compatibility")|g' project.godot

# 4. 取消注释 C# autoloads
echo "[4/5] project.godot: 取消注释 C# autoloads"
sed -i '' 's|^;TimeManager=|TimeManager=|' project.godot
sed -i '' 's|^;ResourceManager=|ResourceManager=|' project.godot
sed -i '' 's|^;SkillManager=|SkillManager=|' project.godot
sed -i '' 's|^;EventManager=|EventManager=|' project.godot
sed -i '' 's|^;SaveManager=|SaveManager=|' project.godot
sed -i '' 's|^;MetricManager=|MetricManager=|' project.godot
sed -i '' 's|^;NpcRegistry=|NpcRegistry=|' project.godot
sed -i '' 's|^;GameState=|GameState=|' project.godot
sed -i '' 's|^;QuestManager=|QuestManager=|' project.godot

# 5. 确认切换完成
echo "[5/5] 验证切换状态"
CS_COUNT=$(find scripts/csharp -name '*.cs' ! -name '*.cs.bak' 2>/dev/null | wc -l | tr -d ' ')
CS_BAK_COUNT=$(find scripts/csharp -name '*.cs.bak' 2>/dev/null | wc -l | tr -d ' ')
GD_COUNT=$(find scripts/csharp -name '*.gd' 2>/dev/null | wc -l | tr -d ' ')
FEATURES=$(grep '^config/features' project.godot)
C_AUTOLOADS=$(grep -c '^;' project.godot 2>/dev/null || echo 0)

echo ""
echo "  C# scripts (active): $CS_COUNT"
echo "  C# scripts (backed up): $CS_BAK_COUNT"
echo "  GDScript stubs: $GD_COUNT"
echo "  Features: $FEATURES"
echo "  Commented autoloads: $C_AUTOLOADS"
echo ""
echo "=== Profile B ready ==="
echo "建议在 Godot Mono GUI 中打开项目验证 C# 运行"
echo "或运行：$HOME/Applications/Godot_mono.app/Contents/MacOS/Godot --editor"