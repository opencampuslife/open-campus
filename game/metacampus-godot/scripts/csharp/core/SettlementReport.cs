using Godot;
using System.Collections.Generic;

public partial class SettlementReport : GodotObject
{
    public int Semester { get; set; }
    public int Day { get; set; }

    public Godot.Collections.Dictionary ResourceBefore { get; set; } = new();
    public Godot.Collections.Dictionary ResourceAfter { get; set; } = new();
    public Godot.Collections.Dictionary MetricBefore { get; set; } = new();
    public Godot.Collections.Dictionary MetricAfter { get; set; } = new();

    public Godot.Collections.Array<string> CompletedQuests { get; set; } = new();
    public Godot.Collections.Array<string> FailedOrExpiredQuests { get; set; } = new();
    public Godot.Collections.Array<string> TriggeredConsequences { get; set; } = new();
    public Godot.Collections.Array<string> NextDayEvents { get; set; } = new();
}
