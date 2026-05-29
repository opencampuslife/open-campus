using Godot;
using System.Collections.Generic;

public partial class GameState : Node
{
    [Signal] public delegate void LocationUnlockedEventHandler(string locationId);

    private readonly HashSet<string> _unlockedLocations = new()
    {
        "ai_hub",
        "admission_office",
        "academic_affairs",
        "school_gate"
    };

    public override void _Ready()
    {
        AddUserSignal("location_unlocked");
    }

    public bool IsLocationUnlocked(string locationId)
    {
        return _unlockedLocations.Contains(locationId);
    }

    public void UnlockLocation(string locationId)
    {
        if (_unlockedLocations.Add(locationId))
        {
            EmitSignal("location_unlocked", locationId);
        }
    }

    public Godot.Collections.Array GetUnlockedLocations()
    {
        var result = new Godot.Collections.Array();
        foreach (var loc in _unlockedLocations)
            result.Add(loc);
        return result;
    }

    public Godot.Collections.Dictionary GetSaveData()
    {
        var data = new Godot.Collections.Dictionary();
        var locArray = new Godot.Collections.Array();
        foreach (var loc in _unlockedLocations)
            locArray.Add(loc);
        data["unlocked_locations"] = locArray;
        return data;
    }

    public void LoadSaveData(Godot.Collections.Dictionary data)
    {
        _unlockedLocations.Clear();
        if (data.ContainsKey("unlocked_locations"))
        {
            var locArray = (Godot.Collections.Array)data["unlocked_locations"];
            foreach (var loc in locArray)
                _unlockedLocations.Add(loc.ToString());
        }
    }
}
