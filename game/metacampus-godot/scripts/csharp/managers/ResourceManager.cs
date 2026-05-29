using Godot;
using System.Collections.Generic;

public partial class ResourceManager : Node
{
    [Signal] public delegate void ResourceChangedEventHandler(string resourceId, int value, int maxValue = 0);

    private readonly Dictionary<string, int> _resources = new()
    {
        { "ap", 10 },
        { "compute", 80 },
        { "budget", 10000 }
    };

    private readonly Dictionary<string, int> _maxResources = new()
    {
        { "ap", 10 },
        { "compute", 100 },
        { "budget", 50000 }
    };

    private readonly HashSet<string> _unlockedUpgrades = new();

    public override void _Ready()
    {
        AddUserSignal("ap_changed");
        AddUserSignal("compute_changed");
        AddUserSignal("budget_changed");
    }

    public int GetResource(string resourceId)
    {
        return _resources.GetValueOrDefault(resourceId, 0);
    }

    public int GetMaxResource(string resourceId)
    {
        return _maxResources.GetValueOrDefault(resourceId, 100);
    }

    public void SetResource(string resourceId, int value)
    {
        if (!_resources.ContainsKey(resourceId))
            _resources[resourceId] = 0;

        var max = _maxResources.GetValueOrDefault(resourceId, 100);
        var old = _resources[resourceId];
        _resources[resourceId] = Mathf.Clamp(value, 0, max);

        if (old != _resources[resourceId])
        {
            EmitSignal("resource_changed", resourceId, _resources[resourceId], max);
        }
    }

    public void AddResource(string resourceId, int amount)
    {
        SetResource(resourceId, _resources.GetValueOrDefault(resourceId, 0) + amount);
    }

    public bool UseAp(int amount)
    {
        var current = _resources.GetValueOrDefault("ap", 10);
        if (current < amount)
            return false;

        SetResource("ap", current - amount);
        return true;
    }

    public bool UseCompute(int amount)
    {
        var current = _resources.GetValueOrDefault("compute", 80);
        if (current < amount)
            return false;

        SetResource("compute", current - amount);
        return true;
    }

    public bool UseBudget(int amount)
    {
        var current = _resources.GetValueOrDefault("budget", 10000);
        if (current < amount)
            return false;

        SetResource("budget", current - amount);
        return true;
    }

    public bool CanAfford(string resourceId, int amount)
    {
        return _resources.GetValueOrDefault(resourceId, 0) >= amount;
    }

    public void ProcessDailySettlement(int reputation = 50, int efficiency = 40)
    {
        // Restore AP
        SetResource("ap", _maxResources["ap"]);

        // Compute recovers over time (handled by tick)
        // Budget: base + efficiency bonus + reputation bonus - costs
        var income = 2000 + efficiency * 10 + reputation * 5;
        var expenses = 100 + 200; // Tool upkeep + NPC support
        AddResource("budget", income - expenses);

        EmitSignal("ap_changed", _resources["ap"], _maxResources["ap"]);
        EmitSignal("compute_changed", _resources["compute"], _maxResources["compute"]);
        EmitSignal("budget_changed", _resources["budget"], _maxResources["budget"]);
    }

    public void UnlockUpgrade(string upgradeId)
    {
        _unlockedUpgrades.Add(upgradeId);
    }

    public bool IsUpgradeUnlocked(string upgradeId)
    {
        return _unlockedUpgrades.Contains(upgradeId);
    }

    public Godot.Collections.Dictionary GetResourceSnapshot()
    {
        var snapshot = new Godot.Collections.Dictionary();
        foreach (var pair in _resources)
            snapshot[pair.Key] = pair.Value;
        return snapshot;
    }

    private static readonly string[] DefaultUpgradeIds =
    {
        "rag_knowledge_base",
        "compliance_filter",
        "ticket_router",
        "parent_notification_bot",
        "academic_summarizer",
        "canary_console",
        "public_opinion_radar",
        "ops_dashboard",
        "privacy_masker",
        "sla_monitor",
        "policy_diff_checker",
        "multi_agent_orchestrator"
    };

    public Godot.Collections.Dictionary GetUpgradeUnlockSnapshot()
    {
        var result = new Godot.Collections.Dictionary();
        foreach (var upgradeId in DefaultUpgradeIds)
            result[upgradeId] = _unlockedUpgrades.Contains(upgradeId);
        return result;
    }

    public Godot.Collections.Dictionary GetSaveData()
    {
        var data = new Godot.Collections.Dictionary();
        foreach (var pair in _resources)
            data[pair.Key] = pair.Value;
        return data;
    }

    public void LoadSaveData(Godot.Collections.Dictionary data)
    {
        foreach (var key in data.Keys)
        {
            var strKey = key.ToString();
            if (_resources.ContainsKey(strKey))
                _resources[strKey] = (int)data[key];
        }
    }
}
