using Godot;
using MetaCampus.Core;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;

public partial class QuestManager : Node
{
    [Signal] public delegate void QuestAvailableEventHandler(string questId);
    [Signal] public delegate void QuestStartedEventHandler(string questId);
    [Signal] public delegate void QuestUpdatedEventHandler(string questId);
    [Signal] public delegate void QuestCompletedEventHandler(string questId);
    [Signal] public delegate void QuestFailedEventHandler(string questId);
    [Signal] public delegate void QuestExpiredEventHandler(string questId);
    [Signal] public delegate void DailyQuestsRefreshedEventHandler(Godot.Collections.Array<string> questIds);

    private readonly Dictionary<string, QuestDefinition> _allQuests = new();
    private readonly Dictionary<string, QuestState> _questStates = new();
    private readonly List<string> _activeQuests = new();
    private readonly List<string> _completedQuests = new();
    private readonly List<string> _failedQuests = new();
    private readonly List<string> _dailyQuestIds = new();

    private static readonly string[] QuestFiles =
    {
        "res://data/quests/main_quests.json",
        "res://data/quests/daily_quests.json",
        "res://data/quests/npc_quests.json",
        "res://data/quests/random_event_quests.json"
    };

    public override void _Ready()
    {
        LoadAllQuests();
        InitializeQuestStates();
        CheckAvailableQuests();
    }

    public void LoadAllQuests()
    {
        _allQuests.Clear();

        foreach (var path in QuestFiles)
        {
            var quests = LoadQuestFile(path);

            foreach (var quest in quests)
            {
                if (string.IsNullOrWhiteSpace(quest.Id))
                {
                    GD.PushWarning($"Quest with empty id ignored in {path}");
                    continue;
                }

                _allQuests[quest.Id] = quest;
            }
        }

        GD.Print($"QuestManager loaded {_allQuests.Count} quests.");
    }

    private static List<QuestDefinition> LoadQuestFile(string path)
    {
        if (!FileAccess.FileExists(path))
        {
            GD.PushWarning($"Quest file not found: {path}");
            return new List<QuestDefinition>();
        }

        using var file = FileAccess.Open(path, FileAccess.ModeFlags.Read);
        var json = file.GetAsText();

        try
        {
            var options = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                ReadCommentHandling = JsonCommentHandling.Skip,
                AllowTrailingCommas = true
            };

            var wrapper = JsonSerializer.Deserialize<QuestFileWrapper>(json, options);
            if (wrapper?.Quests != null)
                return wrapper.Quests;

            var rawList = JsonSerializer.Deserialize<List<QuestDefinition>>(json, options);
            return rawList ?? new List<QuestDefinition>();
        }
        catch (Exception ex)
        {
            GD.PushError($"Invalid quest JSON: {path}. Error: {ex.Message}");
            return new List<QuestDefinition>();
        }
    }

    public void InitializeQuestStates()
    {
        foreach (var pair in _allQuests)
        {
            var questId = pair.Key;
            var quest = pair.Value;

            if (_questStates.ContainsKey(questId))
                continue;

            var state = new QuestState();

            foreach (var objective in quest.Objectives)
                state.ObjectiveProgress[objective.Id] = 0;

            _questStates[questId] = state;
        }
    }

    public void CheckAvailableQuests()
    {
        foreach (var pair in _allQuests)
        {
            var questId = pair.Key;
            var quest = pair.Value;
            var state = _questStates[questId];

            if (state.Status != QuestStatus.Locked)
                continue;

            if (!RequirementsMet(quest))
                continue;

            state.Status = QuestStatus.Available;
            EmitSignal(SignalName.QuestAvailable, questId);
        }
    }

    public bool StartQuest(string questId)
    {
        if (!_allQuests.ContainsKey(questId))
            return false;

        var state = _questStates[questId];

        if (state.Status != QuestStatus.Available)
            return false;

        state.Status = QuestStatus.Active;
        state.StartedDay = GetTimeManager().GetCurrentDay();

        if (!_activeQuests.Contains(questId))
            _activeQuests.Add(questId);

        EmitSignal(SignalName.QuestStarted, questId);
        return true;
    }

    public void UpdateObjective(string questId, string objectiveId, int amount = 1)
    {
        if (!_questStates.TryGetValue(questId, out var state))
            return;

        if (state.Status != QuestStatus.Active)
            return;

        if (!state.ObjectiveProgress.ContainsKey(objectiveId))
            return;

        state.ObjectiveProgress[objectiveId] += amount;

        EmitSignal(SignalName.QuestUpdated, questId);

        if (ObjectivesCompleted(questId))
            CompleteQuest(questId);
    }

    public void CompleteQuest(string questId)
    {
        if (!_allQuests.TryGetValue(questId, out var quest))
            return;

        var state = _questStates[questId];

        if (state.Status == QuestStatus.Completed)
            return;

        state.Status = QuestStatus.Completed;
        state.CompletedDay = GetTimeManager().GetCurrentDay();

        _activeQuests.Remove(questId);

        if (!_completedQuests.Contains(questId))
            _completedQuests.Add(questId);

        ApplyEffects(quest.Rewards);
        ApplyUnlocks(quest.UnlockOnComplete);

        EmitSignal(SignalName.QuestCompleted, questId);
        CheckAvailableQuests();
    }

    public void FailQuest(string questId)
    {
        if (!_allQuests.TryGetValue(questId, out var quest))
            return;

        var state = _questStates[questId];

        if (state.Status == QuestStatus.Failed)
            return;

        state.Status = QuestStatus.Failed;
        _activeQuests.Remove(questId);

        if (!_failedQuests.Contains(questId))
            _failedQuests.Add(questId);

        ApplyEffects(quest.FailureEffects);

        EmitSignal(SignalName.QuestFailed, questId);
    }

    public void ExpireQuest(string questId)
    {
        if (!_allQuests.TryGetValue(questId, out var quest))
            return;

        var state = _questStates[questId];

        if (state.Status != QuestStatus.Active && state.Status != QuestStatus.Available)
            return;

        state.Status = QuestStatus.Expired;
        _activeQuests.Remove(questId);

        ApplyEffects(quest.FailureEffects);

        EmitSignal(SignalName.QuestExpired, questId);
    }

    public void RefreshDailyQuests(int maxDaily = 4)
    {
        _dailyQuestIds.Clear();

        var candidates = _allQuests
            .Where(pair => pair.Value.Type == "daily")
            .Where(pair => RequirementsMet(pair.Value))
            .Where(pair => !_completedQuests.Contains(pair.Key))
            .Select(pair => pair.Key)
            .ToList();

        Shuffle(candidates);

        foreach (var questId in candidates.Take(maxDaily))
        {
            _dailyQuestIds.Add(questId);
            _questStates[questId].Status = QuestStatus.Available;
        }

        var godotArray = new Godot.Collections.Array<string>();
        foreach (var id in _dailyQuestIds)
            godotArray.Add(id);

        EmitSignal(SignalName.DailyQuestsRefreshed, godotArray);
    }

    public void ProcessChoice(string questId, string choiceId)
    {
        if (!_allQuests.TryGetValue(questId, out var quest))
            return;

        var choice = quest.Choices.FirstOrDefault(c => c.Id == choiceId);
        if (choice == null)
            return;

        ApplyEffects(choice.Effects);

        if (choice.CompleteQuest)
            CompleteQuest(questId);
        else if (choice.FailQuest)
            FailQuest(questId);
    }

    public void CheckDeadlines()
    {
        foreach (var questId in _activeQuests.ToArray())
        {
            var quest = _allQuests[questId];

            if (IsDeadlineMissed(quest))
                ExpireQuest(questId);
        }
    }

    public Godot.Collections.Array<string> GetActiveQuests()
    {
        var result = new Godot.Collections.Array<string>();
        foreach (var id in _activeQuests)
            result.Add(id);
        return result;
    }

    public Godot.Collections.Array<string> GetDailyQuests()
    {
        var result = new Godot.Collections.Array<string>();
        foreach (var id in _dailyQuestIds)
            result.Add(id);
        return result;
    }

    public string GetQuestTitle(string questId)
    {
        return _allQuests.TryGetValue(questId, out var quest) ? quest.Title : "";
    }

    public Godot.Collections.Array<string> GetAvailableQuestsByType(string type)
    {
        var result = new Godot.Collections.Array<string>();
        foreach (var pair in _allQuests)
        {
            var questId = pair.Key;
            var quest = pair.Value;
            var state = _questStates[questId];

            if (state.Status != QuestStatus.Available)
                continue;

            if (quest.Type != type)
                continue;

            result.Add(questId);
        }
        return result;
    }

    public string GetQuestType(string questId)
    {
        return _allQuests.TryGetValue(questId, out var quest) ? quest.Type : "";
    }

    public string GetQuestCategory(string questId)
    {
        return _allQuests.TryGetValue(questId, out var quest) ? quest.Category : "";
    }

    public int GetQuestPriority(string questId)
    {
        return _allQuests.TryGetValue(questId, out var quest) ? quest.Priority : 0;
    }

    public Godot.Collections.Array<string> GetQuestObjectiveTexts(string questId)
    {
        var result = new Godot.Collections.Array<string>();

        if (!_allQuests.TryGetValue(questId, out var quest))
            return result;

        if (!_questStates.TryGetValue(questId, out var state))
            return result;

        foreach (var objective in quest.Objectives)
        {
            var current = state.ObjectiveProgress.GetValueOrDefault(objective.Id, 0);
            var text = GetObjectiveDisplayName(objective.Type, objective.Target);
            result.Add($"{text} {current}/{objective.Required}");
        }

        return result;
    }

    public Godot.Collections.Dictionary GetQuestRewardSummary(string questId)
    {
        var result = new Godot.Collections.Dictionary();

        if (!_allQuests.TryGetValue(questId, out var quest))
            return result;

        if (quest.Rewards?.Resources != null)
            foreach (var pair in quest.Rewards.Resources)
                result[$"resource:{pair.Key}"] = pair.Value;

        if (quest.Rewards?.Metrics != null)
            foreach (var pair in quest.Rewards.Metrics)
                result[$"metric:{pair.Key}"] = pair.Value;

        if (quest.Rewards?.SkillsXp != null)
            foreach (var pair in quest.Rewards.SkillsXp)
                result[$"xp:{pair.Key}"] = pair.Value;

        if (quest.Rewards?.NpcTrust != null)
            foreach (var pair in quest.Rewards.NpcTrust)
                result[$"trust:{pair.Key}"] = pair.Value;

        return result;
    }

    public bool IsQuestAvailable(string questId)
    {
        return _questStates.TryGetValue(questId, out var state)
               && state.Status == QuestStatus.Available;
    }

    public bool IsQuestActive(string questId)
    {
        return _questStates.TryGetValue(questId, out var state)
               && state.Status == QuestStatus.Active;
    }

    public Godot.Collections.Array<string> GetAvailableNpcQuests(string npcId)
    {
        var result = new Godot.Collections.Array<string>();

        foreach (var pair in _allQuests)
        {
            var questId = pair.Key;
            var quest = pair.Value;
            var state = _questStates[questId];

            if (state.Status != QuestStatus.Available)
                continue;

            if (quest.Type != "npc")
                continue;

            if (quest.NpcId != npcId)
                continue;

            result.Add(questId);
        }

        return result;
    }

    private static string GetObjectiveDisplayName(string type, string target)
    {
        return type switch
        {
            "talk_to_npc" => $"与 {target} 对话",
            "use_ai_tool" => $"使用 AI 工具：{target}",
            "visit_location" => $"前往地点：{target}",
            "resolve_event" => $"处理事件：{target}",
            "review_ai_answer" => $"审核 AI 回答：{target}",
            _ => $"{type}:{target}"
        };
    }

    public string GetQuestDeadline(string questId)
    {
        if (!_allQuests.TryGetValue(questId, out var quest))
            return "";
        if (quest.Deadline == null)
            return "";
        return $"{quest.Deadline.Hour:00}:{quest.Deadline.Minute:00}";
    }

    public string GetQuestDescription(string questId)
    {
        return _allQuests.TryGetValue(questId, out var quest) ? quest.Description : "";
    }

    public Godot.Collections.Array<string> GetCompletedQuestIds()
    {
        var result = new Godot.Collections.Array<string>();
        foreach (var id in _completedQuests)
            result.Add(id);
        return result;
    }

    public Godot.Collections.Array<string> GetFailedOrExpiredQuestIds()
    {
        var result = new Godot.Collections.Array<string>();
        foreach (var id in _failedQuests)
            result.Add(id);
        var expired = _questStates
            .Where(pair => pair.Value.Status == QuestStatus.Expired)
            .Select(pair => pair.Key);
        foreach (var id in expired)
        {
            if (!result.Contains(id))
                result.Add(id);
        }
        return result;
    }

    public int GetQuestStatusInt(string questId)
    {
        return _questStates.TryGetValue(questId, out var state)
            ? (int)state.Status
            : (int)QuestStatus.Locked;
    }

    private bool ObjectivesCompleted(string questId)
    {
        var quest = _allQuests[questId];
        var state = _questStates[questId];

        if (quest.Objectives.Count == 0)
            return true;

        foreach (var objective in quest.Objectives)
        {
            var current = state.ObjectiveProgress.GetValueOrDefault(objective.Id, 0);
            if (current < objective.Required)
                return false;
        }

        return true;
    }

    private bool RequirementsMet(QuestDefinition quest)
    {
        var req = quest.Requirements;

        if (req.DayMin > 0 && GetTimeManager().GetCurrentDay() < req.DayMin)
            return false;

        foreach (var pair in req.SkillsMin)
        {
            if (GetSkillManager().GetSkillLevel(pair.Key) < pair.Value)
                return false;
        }

        foreach (var pair in req.MetricsMin)
        {
            if (GetMetricManager().GetMetric(pair.Key) < pair.Value)
                return false;
        }

        foreach (var pair in req.TrustMin)
        {
            if (GetNpcRegistry().GetTrustLevel(pair.Key) < pair.Value)
                return false;
        }

        foreach (var locationId in req.UnlockedLocations)
        {
            if (!GetGameState().IsLocationUnlocked(locationId))
                return false;
        }

        return true;
    }

    private void ApplyEffects(QuestEffects effects)
    {
        if (effects?.Metrics != null)
            foreach (var pair in effects.Metrics)
                GetMetricManager().AddMetric(pair.Key, pair.Value);

        if (effects?.SubMetrics != null)
            foreach (var pair in effects.SubMetrics)
                GetMetricManager().AddSubMetric(pair.Key, pair.Key, pair.Value);

        if (effects?.Resources != null)
            foreach (var pair in effects.Resources)
                GetResourceManager().AddResource(pair.Key, pair.Value);

        if (effects?.SkillsXp != null)
            foreach (var pair in effects.SkillsXp)
                GetSkillManager().AddXp(pair.Key, pair.Value);

        if (effects?.NpcTrust != null)
            foreach (var pair in effects.NpcTrust)
                GetNpcRegistry().AddTrust(pair.Key, pair.Value);
    }

    private void ApplyUnlocks(QuestUnlocks unlocks)
    {
        if (unlocks?.Locations != null)
            foreach (var locationId in unlocks.Locations)
                GetGameState().UnlockLocation(locationId);

        if (unlocks?.Quests != null)
            foreach (var questId in unlocks.Quests)
            {
                if (!_questStates.ContainsKey(questId))
                    continue;

                _questStates[questId].Status = QuestStatus.Available;
                EmitSignal(SignalName.QuestAvailable, questId);
            }

        if (unlocks?.Upgrades != null)
            foreach (var upgradeId in unlocks.Upgrades)
                GetResourceManager().UnlockUpgrade(upgradeId);
    }

    private bool IsDeadlineMissed(QuestDefinition quest)
    {
        if (quest.Deadline == null)
            return false;

        if (quest.Deadline.Type != "same_day")
            return false;

        var time = GetTimeManager();

        if (time.GetCurrentHour() > quest.Deadline.Hour)
            return true;

        return time.GetCurrentHour() == quest.Deadline.Hour
               && time.GetCurrentMinute() > quest.Deadline.Minute;
    }

    private static void Shuffle<T>(IList<T> list)
    {
        var rng = new Random();

        for (var i = list.Count - 1; i > 0; i--)
        {
            var j = rng.Next(i + 1);
            (list[i], list[j]) = (list[j], list[i]);
        }
    }

    private TimeManager GetTimeManager() =>
        GetNode<TimeManager>("/root/TimeManager");

    private ResourceManager GetResourceManager() =>
        GetNode<ResourceManager>("/root/ResourceManager");

    private SkillManager GetSkillManager() =>
        GetNode<SkillManager>("/root/SkillManager");

    private MetricManager GetMetricManager() =>
        GetNode<MetricManager>("/root/MetricManager");

    private NpcRegistry GetNpcRegistry() =>
        GetNode<NpcRegistry>("/root/NpcRegistry");

    private GameState GetGameState() =>
        GetNode<GameState>("/root/GameState");
}
