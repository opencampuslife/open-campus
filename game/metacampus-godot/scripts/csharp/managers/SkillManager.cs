using Godot;
using System.Collections.Generic;

public partial class SkillManager : Node
{
    [Signal] public delegate void SkillXpChangedEventHandler(string skillId, int level, int xp, int maxXp);
    [Signal] public delegate void SkillLeveledUpEventHandler(string skillId, int newLevel, string unlock);

    private sealed class SkillState
    {
        public int Level = 1;
        public int Xp = 0;
    }

    private readonly Dictionary<string, SkillState> _skills = new()
    {
        { "admissions", new SkillState() },
        { "academic_affairs", new SkillState() },
        { "compliance", new SkillState() },
        { "operations", new SkillState() },
        { "data_intelligence", new SkillState() },
        { "communication", new SkillState() }
    };

    private static readonly Dictionary<string, string> SkillNames = new()
    {
        { "admissions", "招生咨询" },
        { "academic_affairs", "教务处理" },
        { "compliance", "合规治理" },
        { "operations", "系统运维" },
        { "data_intelligence", "数据智能" },
        { "communication", "沟通协调" }
    };

    public override void _Ready()
    {
        AddUserSignal("skill_xp_changed");
        AddUserSignal("skill_leveled_up");
    }

    public int GetSkillLevel(string skillId)
    {
        return _skills.TryGetValue(skillId, out var state) ? state.Level : 0;
    }

    public int GetSkillXp(string skillId)
    {
        return _skills.TryGetValue(skillId, out var state) ? state.Xp : 0;
    }

    public string GetSkillName(string skillId)
    {
        return SkillNames.GetValueOrDefault(skillId, skillId);
    }

    public void AddXp(string skillId, int amount)
    {
        if (!_skills.ContainsKey(skillId))
            _skills[skillId] = new SkillState();

        var state = _skills[skillId];
        state.Xp += amount;

        var leveledUp = false;
        while (state.Level < 10 && state.Xp >= RequiredXpForNextLevel(state.Level))
        {
            state.Xp -= RequiredXpForNextLevel(state.Level);
            state.Level++;
            leveledUp = true;

            var unlock = GetUnlockForLevel(skillId, state.Level);
            EmitSignal("skill_leveled_up", skillId, state.Level, unlock);
        }

        var maxXp = RequiredXpForNextLevel(state.Level);
        EmitSignal("skill_xp_changed", skillId, state.Level, state.Xp, maxXp);

        if (leveledUp)
            NotifyManagerUnlocks(skillId, state.Level);
    }

    public Godot.Collections.Dictionary GetSkillSnapshot()
    {
        var result = new Godot.Collections.Dictionary();
        foreach (var pair in _skills)
        {
            var entry = new Godot.Collections.Dictionary();
            entry["level"] = pair.Value.Level;
            entry["xp"] = pair.Value.Xp;
            entry["next_xp"] = RequiredXpForNextLevel(pair.Value.Level);
            result[pair.Key] = entry;
        }
        return result;
    }

    public Godot.Collections.Dictionary GetSkillProgress()
    {
        var result = new Godot.Collections.Dictionary();
        foreach (var pair in _skills)
        {
            var entry = new Godot.Collections.Dictionary();
            entry["level"] = pair.Value.Level;
            entry["xp"] = pair.Value.Xp;
            entry["name"] = GetSkillName(pair.Key);
            entry["max_xp"] = RequiredXpForNextLevel(pair.Value.Level);
            entry["progress"] = pair.Value.Level >= 10 ? 1.0f :
                (float)pair.Value.Xp / RequiredXpForNextLevel(pair.Value.Level);
            result[pair.Key] = entry;
        }
        return result;
    }

    private static int RequiredXpForNextLevel(int level)
    {
        // Level 1->2: 100, 2->3: 150, ... 9->10: 500
        return 100 + (level - 1) * 50;
    }

    private static string GetUnlockForLevel(string skillId, int level)
    {
        var unlocks = new Dictionary<string, Dictionary<int, string>>
        {
            { "compliance", new Dictionary<int, string>
                {
                    { 1, "高风险词提醒" }, { 2, "招生承诺检测" }, { 3, "隐私字段脱敏" },
                    { 4, "自动生成合规话术" }, { 5, "高风险任务预警" }, { 6, "政策冲突检测" },
                    { 7, "审计日志自动归档" }, { 8, "舆情风险预测" }, { 9, "多部门合规联动" },
                    { 10, "合规沙盒推演" }
                }
            },
            { "admissions", new Dictionary<int, string>
                {
                    { 1, "标准问答模板" }, { 2, "材料自动审核" }, { 3, "招生承诺检测" },
                    { 4, "政策知识库联动" }, { 5, "招生趋势预测" }, { 6, "多源数据核验" },
                    { 7, "智能咨询分流" }, { 8, "招生风险预警" }, { 9, "全链路自动化" },
                    { 10, "智慧招生中枢" }
                }
            },
            { "operations", new Dictionary<int, string>
                {
                    { 1, "基础监控面板" }, { 2, "自动告警通知" }, { 3, "快速回滚能力" },
                    { 4, "灰度发布优先" }, { 5, "故障预测模型" }, { 6, "自动扩容策略" },
                    { 7, "跨区容灾机制" }, { 8, "智能根因分析" }, { 9, "自愈系统框架" },
                    { 10, "零故障架构" }
                }
            },
            { "data_intelligence", new Dictionary<int, string>
                {
                    { 1, "基础RAG检索" }, { 2, "检索结果排序优化" }, { 3, "引文自动标注" },
                    { 4, "知识库新鲜度监控" }, { 5, "多模态数据融合" }, { 6, "预测性分析模型" },
                    { 7, "归因分析引擎" }, { 8, "自动化知识图谱" }, { 9, "跨源数据治理" },
                    { 10, "认知智能中枢" }
                }
            },
            { "communication", new Dictionary<int, string>
                {
                    { 1, "基础沟通技巧" }, { 2, "情绪识别能力" }, { 3, "冲突调解技巧" },
                    { 4, "信任快速建立" }, { 5, "危机公关话术" }, { 6, "跨部门协作机制" },
                    { 7, "组织影响力扩展" }, { 8, "文化变革引导" }, { 9, "战略沟通能力" },
                    { 10, "卓越领导力" }
                }
            }
        };

        return unlocks.GetValueOrDefault(skillId, new Dictionary<int, string>())
            .GetValueOrDefault(level, "");
    }

    private void NotifyManagerUnlocks(string skillId, int level)
    {
        var resourceMgr = GetNode<ResourceManager>("/root/ResourceManager");
        if (skillId == "operations" && level >= 3)
            resourceMgr.UnlockUpgrade("quick_rollback");
        else if (skillId == "data_intelligence" && level >= 3)
            resourceMgr.UnlockUpgrade("citation_auto");
        else if (skillId == "communication" && level >= 4)
            resourceMgr.UnlockUpgrade("trust_boost");
    }

    public void AddXpForAction(string action)
    {
        var xpMap = new Dictionary<string, Dictionary<string, int>>
        {
            { "admission_consultation", new Dictionary<string, int> { { "admissions", 5 }, { "communication", 3 } } },
            { "intercept_violation", new Dictionary<string, int> { { "compliance", 10 } } },
            { "process_leave", new Dictionary<string, int> { { "academic_affairs", 5 } } },
            { "canary_release", new Dictionary<string, int> { { "operations", 15 }, { "compliance", 5 } } },
            { "kb_optimization", new Dictionary<string, int> { { "data_intelligence", 12 }, { "compliance", 3 } } },
            { "complain_resolution", new Dictionary<string, int> { { "communication", 12 }, { "admissions", 3 } } },
            { "data_analysis", new Dictionary<string, int> { { "data_intelligence", 10 } } },
            { "system_recovery", new Dictionary<string, int> { { "operations", 10 } } }
        };

        if (xpMap.TryGetValue(action, out var skillsToAdd))
        {
            foreach (var pair in skillsToAdd)
                AddXp(pair.Key, pair.Value);
        }
    }

    public Godot.Collections.Dictionary GetSaveData()
    {
        var data = new Godot.Collections.Dictionary();
        foreach (var pair in _skills)
        {
            var entry = new Godot.Collections.Dictionary();
            entry["level"] = pair.Value.Level;
            entry["xp"] = pair.Value.Xp;
            data[pair.Key] = entry;
        }
        return data;
    }

    public void LoadSaveData(Godot.Collections.Dictionary data)
    {
        foreach (var key in data.Keys)
        {
            var strKey = key.ToString();
            if (!_skills.ContainsKey(strKey))
                _skills[strKey] = new SkillState();

            var entry = (Godot.Collections.Dictionary)data[key];
            _skills[strKey].Level = (int)entry["level"];
            _skills[strKey].Xp = (int)entry["xp"];
        }
    }
}
