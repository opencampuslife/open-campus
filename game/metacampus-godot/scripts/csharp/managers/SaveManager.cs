using Godot;

public partial class SaveManager : Node
{
    private const string SAVE_DIR = "user://saves/";
    private const string SAVE_EXT = ".json";
    private const int MAX_SLOTS = 6;

    private int _currentSlot = 0;
    private readonly Godot.Collections.Dictionary _saveMetadata = new();
    private static readonly System.Collections.Generic.Dictionary<string, Godot.Collections.Dictionary> _emptyDict = new();

    public override void _Ready()
    {
        AddUserSignal("save_completed");
        AddUserSignal("load_completed");
        AddUserSignal("save_deleted");
        EnsureSaveDir();
    }

    private void EnsureSaveDir()
    {
        var dir = DirAccess.Open("user://");
        if (dir != null && !dir.DirExists(SAVE_DIR))
        {
            dir.MakeDirRecursive(SAVE_DIR);
        }
    }

    private string GetSavePath(int slot)
    {
        return SAVE_DIR + "save_" + slot + SAVE_EXT;
    }

    public bool SaveGame(int slot = -1)
    {
        if (slot < 0) slot = _currentSlot;
        if (slot < 0 || slot >= MAX_SLOTS) return false;

        var data = CollectAllData();

        var file = FileAccess.Open(GetSavePath(slot), FileAccess.ModeFlags.Write);
        if (file == null) return false;

        file.StoreString(Json.Stringify(data, "\t"));
        file.Close();

        _currentSlot = slot;
        EmitSignal("save_completed", GetSavePath(slot));
        return true;
    }

    public bool LoadGame(int slot = -1)
    {
        if (slot < 0) slot = _currentSlot;
        if (slot < 0 || slot >= MAX_SLOTS) return false;

        var path = GetSavePath(slot);
        if (!FileAccess.FileExists(path)) return false;

        var file = FileAccess.Open(path, FileAccess.ModeFlags.Read);
        if (file == null) return false;

        var jsonText = file.GetAsText();
        file.Close();

        var data = Json.ParseString(jsonText).AsGodotDictionary();
        if (data == null) return false;

        ApplyAllData(data);
        _currentSlot = slot;

        EmitSignal("load_completed", path);
        return true;
    }

    public bool DeleteSave(int slot)
    {
        var path = GetSavePath(slot);
        if (!FileAccess.FileExists(path)) return false;

        var dir = DirAccess.Open("user://saves/");
        if (dir != null)
        {
            dir.Remove(path);
            EmitSignal("save_deleted", path);
            return true;
        }
        return false;
    }

    public bool HasSave(int slot)
    {
        return FileAccess.FileExists(GetSavePath(slot));
    }

    public Godot.Collections.Dictionary GetAllSaves()
    {
        var result = new Godot.Collections.Dictionary();
        for (int i = 0; i < MAX_SLOTS; i++)
        {
            if (HasSave(i))
            {
                if (_saveMetadata.TryGetValue(i.ToString(), out var existing))
                    result[i] = existing;
                else
                    result[i] = new Godot.Collections.Dictionary();
            }
        }
        return result;
    }

    private Godot.Collections.Dictionary CollectAllData()
    {
        var data = new Godot.Collections.Dictionary();

        // TimeManager
        var timeMgr = GetNode<TimeManager>("/root/TimeManager");
        if (timeMgr != null) data["time"] = timeMgr.GetSaveData();

        // ResourceManager
        var resMgr = GetNode<ResourceManager>("/root/ResourceManager");
        if (resMgr != null) data["resources"] = resMgr.GetSaveData();

        // SkillManager
        var skillMgr = GetNode<SkillManager>("/root/SkillManager");
        if (skillMgr != null) data["skills"] = skillMgr.GetSaveData();

        // MetricManager
        var metricMgr = GetNode<MetricManager>("/root/MetricManager");
        if (metricMgr != null) data["metrics"] = metricMgr.GetSaveData();

        // NpcRegistry
        var npcReg = GetNode<NpcRegistry>("/root/NpcRegistry");
        if (npcReg != null) data["npcs"] = npcReg.GetSaveData();

        // GameState
        var gameState = GetNode<GameState>("/root/GameState");
        if (gameState != null) data["game_state"] = gameState.GetSaveData();

        // SaveManager metadata
        data["version"] = "1.0.0";
        data["timestamp"] = Time.GetUnixTimeFromSystem();

        return data;
    }

    private void ApplyAllData(Godot.Collections.Dictionary data)
    {
        var timeMgr = GetNode<TimeManager>("/root/TimeManager");
        if (timeMgr != null && data.ContainsKey("time"))
            timeMgr.LoadSaveData((Godot.Collections.Dictionary)data["time"]);

        var resMgr = GetNode<ResourceManager>("/root/ResourceManager");
        if (resMgr != null && data.ContainsKey("resources"))
            resMgr.LoadSaveData((Godot.Collections.Dictionary)data["resources"]);

        var skillMgr = GetNode<SkillManager>("/root/SkillManager");
        if (skillMgr != null && data.ContainsKey("skills"))
            skillMgr.LoadSaveData((Godot.Collections.Dictionary)data["skills"]);

        var metricMgr = GetNode<MetricManager>("/root/MetricManager");
        if (metricMgr != null && data.ContainsKey("metrics"))
            metricMgr.LoadSaveData((Godot.Collections.Dictionary)data["metrics"]);

        var npcReg = GetNode<NpcRegistry>("/root/NpcRegistry");
        if (npcReg != null && data.ContainsKey("npcs"))
            npcReg.LoadSaveData((Godot.Collections.Dictionary)data["npcs"]);

        var gameState = GetNode<GameState>("/root/GameState");
        if (gameState != null && data.ContainsKey("game_state"))
            gameState.LoadSaveData((Godot.Collections.Dictionary)data["game_state"]);
    }

    public void AutoSave()
    {
        GD.Print("AutoSave triggered.");
        SaveGame(_currentSlot);
    }

    public void NewGame()
    {
        // Reset all systems
        var timeMgr = GetNode<TimeManager>("/root/TimeManager");
        if (timeMgr != null) timeMgr.LoadSaveData(new Godot.Collections.Dictionary());

        var resMgr = GetNode<ResourceManager>("/root/ResourceManager");
        if (resMgr != null) resMgr.LoadSaveData(new Godot.Collections.Dictionary());

        var skillMgr = GetNode<SkillManager>("/root/SkillManager");
        if (skillMgr != null) skillMgr.LoadSaveData(new Godot.Collections.Dictionary());

        var metricMgr = GetNode<MetricManager>("/root/MetricManager");
        if (metricMgr != null) metricMgr.LoadSaveData(new Godot.Collections.Dictionary());

        var npcReg = GetNode<NpcRegistry>("/root/NpcRegistry");
        if (npcReg != null) npcReg.LoadSaveData(new Godot.Collections.Dictionary());

        var gameState = GetNode<GameState>("/root/GameState");
        if (gameState != null) gameState.LoadSaveData(new Godot.Collections.Dictionary());
    }
}
