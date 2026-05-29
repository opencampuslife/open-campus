using Godot;
using System.Collections.Generic;
using System.Text.Json;

public partial class NpcRegistry : Node
{
    [Signal] public delegate void NpcTrustChangedEventHandler(string npcId, int oldLevel, int newLevel);

    private sealed class NpcData
    {
        public int TrustLevel = 1;
        public readonly List<string> CompletedEvents = new();
    }

    private readonly Dictionary<string, NpcData> _npcs = new();

    private static readonly Dictionary<string, int> DefaultTrust = new()
    {
        { "principal", 3 },
        { "admissions_director", 2 },
        { "homeroom_teacher", 3 },
        { "it_operator", 4 },
        { "logistics_manager", 2 },
        { "compliance_officer", 3 },
        { "parent_representative", 3 },
        { "student_representative", 3 }
    };

    public override void _Ready()
    {
        AddUserSignal("trust_changed");
        InitializeTrust();
    }

    private void InitializeTrust()
    {
        foreach (var pair in DefaultTrust)
        {
            if (!_npcs.ContainsKey(pair.Key))
                _npcs[pair.Key] = new NpcData();
            _npcs[pair.Key].TrustLevel = pair.Value;
        }
    }

    public int GetTrustLevel(string npcId)
    {
        return _npcs.TryGetValue(npcId, out var data) ? data.TrustLevel : 0;
    }

    public void SetTrustLevel(string npcId, int level)
    {
        if (!_npcs.ContainsKey(npcId))
            _npcs[npcId] = new NpcData();

        var oldLevel = _npcs[npcId].TrustLevel;
        var newLevel = Mathf.Clamp(level, 0, 10);

        if (oldLevel != newLevel)
        {
            _npcs[npcId].TrustLevel = newLevel;
            EmitSignal("trust_changed", npcId, oldLevel, newLevel);
        }
    }

    public void AddTrust(string npcId, int delta)
    {
        SetTrustLevel(npcId, GetTrustLevel(npcId) + delta);
    }

    public Godot.Collections.Dictionary GetTrustSnapshot()
    {
        var result = new Godot.Collections.Dictionary();
        foreach (var pair in _npcs)
            result[pair.Key] = pair.Value.TrustLevel;
        return result;
    }

    public Godot.Collections.Dictionary GetRelationshipEventSnapshot()
    {
        var result = new Godot.Collections.Dictionary();
        foreach (var pair in _npcs)
        {
            if (pair.Value.CompletedEvents.Count == 0)
                continue;
            var eventsArray = new Godot.Collections.Array();
            foreach (var evt in pair.Value.CompletedEvents)
                eventsArray.Add(evt);
            result[pair.Key] = eventsArray;
        }
        return result;
    }

    public Godot.Collections.Array GetAvailableTrustEvents(string npcId)
    {
        var result = new Godot.Collections.Array();
        var currentTrust = GetTrustLevel(npcId);

        // Load NPC JSON to get relationship_events
        var path = $"res://data/npcs/npc_{npcId}.json";
        if (!FileAccess.FileExists(path))
            return result;

        using var file = FileAccess.Open(path, FileAccess.ModeFlags.Read);
        var json = file.GetAsText();

        try
        {
            var wrapper = JsonSerializer.Deserialize<JsonElement>(json);
            if (wrapper.TryGetProperty("relationship_events", out var eventsArray))
            {
                foreach (var evt in eventsArray.EnumerateArray())
                {
                    if (evt.TryGetProperty("trust_required", out var trustProp) &&
                        trustProp.GetInt32() <= currentTrust)
                    {
                        result.Add(evt.GetProperty("title").GetString());
                    }
                }
            }
        }
        catch { }

        return result;
    }

    public bool IsTrustEventCompleted(string npcId, string eventTitle)
    {
        return _npcs.TryGetValue(npcId, out var data) &&
               data.CompletedEvents.Contains(eventTitle);
    }

    public void MarkTrustEventCompleted(string npcId, string eventTitle)
    {
        if (!_npcs.ContainsKey(npcId))
            _npcs[npcId] = new NpcData();
        _npcs[npcId].CompletedEvents.Add(eventTitle);
    }

    public string GetPortraitPath(string npcId, string expression = "neutral")
    {
        var path = $"res://assets/npcs/{npcId}/portrait_{expression}.png";

        if (ResourceLoader.Exists(path))
            return path;

        // Fallback to neutral
        var neutralPath = $"res://assets/npcs/{npcId}/portrait_neutral.png";
        if (ResourceLoader.Exists(neutralPath))
            return neutralPath;

        return "";
    }

    public string GetSpritePath(string npcId)
    {
        var path = $"res://assets/npcs/{npcId}/sprite_idle.png";
        return ResourceLoader.Exists(path) ? path : "";
    }

    public Godot.Collections.Dictionary GetSaveData()
    {
        var data = new Godot.Collections.Dictionary();
        foreach (var pair in _npcs)
        {
            var entry = new Godot.Collections.Dictionary();
            entry["trust_level"] = pair.Value.TrustLevel;

            var eventsArray = new Godot.Collections.Array();
            foreach (var evt in pair.Value.CompletedEvents)
                eventsArray.Add(evt);
            entry["completed_events"] = eventsArray;

            data[pair.Key] = entry;
        }
        return data;
    }

    public void LoadSaveData(Godot.Collections.Dictionary data)
    {
        _npcs.Clear();
        foreach (var key in data.Keys)
        {
            var strKey = key.ToString();
            var entry = (Godot.Collections.Dictionary)data[key];

            var npcData = new NpcData();
            npcData.TrustLevel = (int)entry["trust_level"];

            var eventsArray = (Godot.Collections.Array)entry["completed_events"];
            foreach (var evt in eventsArray)
                npcData.CompletedEvents.Add(evt.ToString());

            _npcs[strKey] = npcData;
        }
    }
}
