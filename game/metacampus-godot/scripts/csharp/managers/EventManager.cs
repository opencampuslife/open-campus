using Godot;
using System.Collections.Generic;

public partial class EventManager : Node
{
    [Signal] public delegate void EventTriggeredEventHandler(string eventId, Godot.Collections.Dictionary eventData);
    [Signal] public delegate void EventResolvedEventHandler(string eventId, int choiceIndex, Godot.Collections.Dictionary effects);
    [Signal] public delegate void PendingEventsChangedEventHandler(Godot.Collections.Array pending);

    private readonly List<string> _pendingEvents = new();
    private readonly Dictionary<string, Godot.Collections.Dictionary> _resolvedEvents = new();
    private readonly List<string> _eventHistory = new();

    public override void _Ready()
    {
        AddUserSignal("event_triggered");
        AddUserSignal("event_resolved");
        AddUserSignal("pending_events_changed");
        LoadEventData();
    }

    private void LoadEventData()
    {
        // Event data is loaded from data/random_events.json via JsonLoader
        // For now, we just initialize
    }

    public void RollNextDayEvents()
    {
        RollNextDayEventsAndCollect();
    }

    public Godot.Collections.Array<string> RollNextDayEventsAndCollect()
    {
        var result = new Godot.Collections.Array<string>();
        var rng = new RandomNumberGenerator();
        rng.Randomize();

        if (rng.Randf() < 0.3f)
        {
            result.Add("随机事件：明日可能有校园突发事件待处理");
        }

        EmitSignal("pending_events_changed", new Godot.Collections.Array());
        return result;
    }

    public void TriggerEvent(string eventId)
    {
        if (_pendingEvents.Contains(eventId) || _resolvedEvents.ContainsKey(eventId))
            return;

        _pendingEvents.Add(eventId);
        EmitSignal("pending_events_changed", GetPendingAsArray());

        // Load event data from JSON and emit
        EmitSignal("event_triggered", eventId, new Godot.Collections.Dictionary());
    }

    public void ResolveEvent(string eventId, int choiceIndex)
    {
        if (!_pendingEvents.Contains(eventId))
            return;

        _pendingEvents.Remove(eventId);

        if (!_resolvedEvents.ContainsKey(eventId))
            _resolvedEvents[eventId] = new Godot.Collections.Dictionary();

        _eventHistory.Add(eventId);

        EmitSignal("event_resolved", eventId, choiceIndex, new Godot.Collections.Dictionary());
        EmitSignal("pending_events_changed", GetPendingAsArray());
    }

    public Godot.Collections.Array GetPendingEvents()
    {
        return GetPendingAsArray();
    }

    public bool HasPendingEvents()
    {
        return _pendingEvents.Count > 0;
    }

    public int GetResolvedCount()
    {
        return _resolvedEvents.Count;
    }

    private Godot.Collections.Array GetPendingAsArray()
    {
        var result = new Godot.Collections.Array();
        foreach (var evt in _pendingEvents)
            result.Add(evt);
        return result;
    }

    public Godot.Collections.Dictionary GetSaveData()
    {
        var data = new Godot.Collections.Dictionary();
        
        var resolvedDict = new Godot.Collections.Dictionary();
        foreach (var pair in _resolvedEvents)
            resolvedDict[pair.Key] = pair.Value;
        data["resolved_events"] = resolvedDict;

        var pendingArray = new Godot.Collections.Array();
        foreach (var evt in _pendingEvents)
            pendingArray.Add(evt);
        data["pending_ids"] = pendingArray;

        return data;
    }

    public void LoadSaveData(Godot.Collections.Dictionary data)
    {
        _resolvedEvents.Clear();
        _pendingEvents.Clear();

        if (data.ContainsKey("resolved_events"))
        {
            var resolvedDict = (Godot.Collections.Dictionary)data["resolved_events"];
            foreach (var key in resolvedDict.Keys)
                _resolvedEvents[key.ToString()] = (Godot.Collections.Dictionary)resolvedDict[key];
        }

        if (data.ContainsKey("pending_ids"))
        {
            var pendingArray = (Godot.Collections.Array)data["pending_ids"];
            foreach (var evt in pendingArray)
                _pendingEvents.Add(evt.ToString());
        }
    }
}
