using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace MetaCampus.Core;

public enum QuestStatus
{
    Locked = 0,
    Available = 1,
    Active = 2,
    Completed = 3,
    Failed = 4,
    Expired = 5
}

public enum QuestType
{
    Main,
    Daily,
    Npc,
    RandomEvent
}

// ========== Quest Definition (from JSON) ==========

public sealed class QuestDefinition
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = "";

    [JsonPropertyName("title")]
    public string Title { get; set; } = "";

    [JsonPropertyName("description")]
    public string Description { get; set; } = "";

    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("category")]
    public string Category { get; set; } = "";

    [JsonPropertyName("chapter")]
    public int Chapter { get; set; } = 0;

    [JsonPropertyName("npc_id")]
    public string NpcId { get; set; } = "";

    [JsonPropertyName("location_id")]
    public string LocationId { get; set; } = "";

    [JsonPropertyName("priority")]
    public int Priority { get; set; } = 1;

    [JsonPropertyName("duration_minutes")]
    public int DurationMinutes { get; set; } = 0;

    [JsonPropertyName("deadline")]
    public QuestDeadline? Deadline { get; set; }

    [JsonPropertyName("requirements")]
    public QuestRequirements Requirements { get; set; } = new();

    [JsonPropertyName("objectives")]
    public List<QuestObjective> Objectives { get; set; } = new();

    [JsonPropertyName("choices")]
    public List<QuestChoice> Choices { get; set; } = new();

    [JsonPropertyName("rewards")]
    public QuestEffects Rewards { get; set; } = new();

    [JsonPropertyName("failure_effects")]
    public QuestEffects FailureEffects { get; set; } = new();

    [JsonPropertyName("unlock_on_complete")]
    public QuestUnlocks UnlockOnComplete { get; set; } = new();
}

public sealed class QuestDeadline
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("hour")]
    public int Hour { get; set; } = 22;

    [JsonPropertyName("minute")]
    public int Minute { get; set; } = 0;
}

public sealed class QuestRequirements
{
    [JsonPropertyName("day_min")]
    public int DayMin { get; set; } = 0;

    [JsonPropertyName("trust_min")]
    public Dictionary<string, int> TrustMin { get; set; } = new();

    [JsonPropertyName("skills_min")]
    public Dictionary<string, int> SkillsMin { get; set; } = new();

    [JsonPropertyName("metrics_min")]
    public Dictionary<string, int> MetricsMin { get; set; } = new();

    [JsonPropertyName("unlocked_locations")]
    public List<string> UnlockedLocations { get; set; } = new();
}

public sealed class QuestObjective
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = "";

    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("target")]
    public string Target { get; set; } = "";

    [JsonPropertyName("required")]
    public int Required { get; set; } = 1;
}

public sealed class QuestChoice
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = "";

    [JsonPropertyName("text")]
    public string Text { get; set; } = "";

    [JsonPropertyName("risk")]
    public string Risk { get; set; } = "low";

    [JsonPropertyName("effects")]
    public QuestEffects Effects { get; set; } = new();

    [JsonPropertyName("complete_quest")]
    public bool CompleteQuest { get; set; } = false;

    [JsonPropertyName("fail_quest")]
    public bool FailQuest { get; set; } = false;
}

public sealed class QuestEffects
{
    [JsonPropertyName("metrics")]
    public Dictionary<string, int> Metrics { get; set; } = new();

    [JsonPropertyName("sub_metrics")]
    public Dictionary<string, int> SubMetrics { get; set; } = new();

    [JsonPropertyName("resources")]
    public Dictionary<string, int> Resources { get; set; } = new();

    [JsonPropertyName("skills_xp")]
    public Dictionary<string, int> SkillsXp { get; set; } = new();

    [JsonPropertyName("npc_trust")]
    public Dictionary<string, int> NpcTrust { get; set; } = new();
}

public sealed class QuestUnlocks
{
    [JsonPropertyName("quests")]
    public List<string> Quests { get; set; } = new();

    [JsonPropertyName("locations")]
    public List<string> Locations { get; set; } = new();

    [JsonPropertyName("upgrades")]
    public List<string> Upgrades { get; set; } = new();
}

// ========== Quest State (runtime) ==========

public sealed class QuestState
{
    public QuestStatus Status { get; set; } = QuestStatus.Locked;
    public Dictionary<string, int> ObjectiveProgress { get; set; } = new();
    public int StartedDay { get; set; } = -1;
    public int CompletedDay { get; set; } = -1;
}

// ========== Quest File Wrapper ==========

public sealed class QuestFileWrapper
{
    [JsonPropertyName("quests")]
    public List<QuestDefinition> Quests { get; set; } = new();
}
