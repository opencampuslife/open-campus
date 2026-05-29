using Godot;
using System;
using System.Linq;

public partial class TimeManager : Node
{
    [Signal] public delegate void DayEndedEventHandler(int day);
    [Signal] public delegate void TimeChangedEventHandler(int hour, int minute);
    [Signal] public delegate void PhaseChangedEventHandler(string phase);
    [Signal] public delegate void SettlementGeneratedEventHandler(SettlementReport report);

    private int _currentDay = 1;
    private int _currentHour = 7;
    private int _currentMinute = 0;
    private int _semester = 0; // 0=Spring, 1=Summer, 2=Autumn, 3=Winter

    private enum DayPhase
    {
        Morning,    // 07:00-09:59
        Forenoon,   // 10:00-11:59
        Noon,       // 12:00-13:59
        Afternoon, // 14:00-17:59
        Evening,    // 18:00-19:59
        Night       // 20:00-22:00
    }

    private DayPhase _currentPhase = DayPhase.Morning;

    public int GetCurrentDay() => _currentDay;
    public int GetCurrentHour() => _currentHour;
    public int GetCurrentMinute() => _currentMinute;
    public int GetCurrentSemester() => _semester;
    public string GetSemesterName() => new[] { "春季学期", "夏季学期", "秋季学期", "冬季学期" }[_semester];
    public int GetDayOfSemester() => _currentDay;
    public int GetDaysRemaining() => 28 - _currentDay + 1;

    public void SetTime(int hour, int minute)
    {
        _currentHour = Math.Clamp(hour, 7, 22);
        _currentMinute = Math.Clamp(minute, 0, 59);
        UpdatePhase();
        EmitSignal(SignalName.TimeChanged, _currentHour, _currentMinute);
    }

    private void UpdatePhase()
    {
        if (_currentHour < 10) _currentPhase = DayPhase.Morning;
        else if (_currentHour < 12) _currentPhase = DayPhase.Forenoon;
        else if (_currentHour < 14) _currentPhase = DayPhase.Noon;
        else if (_currentHour < 18) _currentPhase = DayPhase.Afternoon;
        else if (_currentHour < 20) _currentPhase = DayPhase.Evening;
        else _currentPhase = DayPhase.Night;

        EmitSignal(SignalName.PhaseChanged, _currentPhase.ToString().ToLower());
    }

    public override void _Ready()
    {
        AddUserSignal("day_started");
        AddUserSignal("day_ended");
        AddUserSignal("phase_changed");
    }

    public void StartDay()
    {
        _currentHour = 7;
        _currentMinute = 0;
        _currentPhase = DayPhase.Morning;
        EmitSignal("day_started", _currentDay, GetSemesterName());
    }

    public void EndDay()
    {
        var resourceManager = GetNode<ResourceManager>("/root/ResourceManager");
        var metricManager = GetNode<MetricManager>("/root/MetricManager");
        var questManager = GetNode<QuestManager>("/root/QuestManager");
        var eventManager = GetNode<EventManager>("/root/EventManager");

        var report = new SettlementReport
        {
            Semester = _semester,
            Day = _currentDay,
            ResourceBefore = resourceManager.GetResourceSnapshot(),
            MetricBefore = metricManager.GetMetricSnapshot()
        };

        questManager.CheckDeadlines();
        report.CompletedQuests = questManager.GetCompletedQuestIds();
        report.FailedOrExpiredQuests = questManager.GetFailedOrExpiredQuestIds();

        resourceManager.ProcessDailySettlement();
        report.TriggeredConsequences = metricManager.CheckThresholdConsequencesAndCollect();

        report.NextDayEvents = eventManager.RollNextDayEventsAndCollect();

        questManager.RefreshDailyQuests();

        report.ResourceAfter = resourceManager.GetResourceSnapshot();
        report.MetricAfter = metricManager.GetMetricSnapshot();

        GetNode<SaveManager>("/root/SaveManager").AutoSave();

        EmitSignal(SignalName.SettlementGenerated, report);

        AdvanceDay();

        EmitSignal(SignalName.DayEnded, _currentDay);
    }

    private void AdvanceDay()
    {
        _currentDay++;

        if (_currentDay > 28)
        {
            _currentDay = 1;
            _semester = (_semester + 1) % 4;
            EmitSignal("semester_ended", GetSemesterName());
        }

        _currentHour = 7;
        _currentMinute = 0;
        _currentPhase = DayPhase.Morning;

        EmitSignal("time_changed", _currentHour, _currentMinute);
        EmitSignal("phase_changed", "早晨");
    }

    public void ProcessTick()
    {
        _currentMinute += 10;

        while (_currentMinute >= 60)
        {
            _currentMinute -= 60;
            _currentHour++;
        }

        var newPhase = GetPhaseForHour(_currentHour);
        if (newPhase != _currentPhase)
        {
            _currentPhase = newPhase;
            var phaseNames = new[] { "早晨", "上午", "中午", "下午", "傍晚", "夜间" };
            EmitSignal("phase_changed", phaseNames[(int)_currentPhase]);
        }

        if (_currentHour >= 22)
        {
            EndDay();
        }
        else
        {
            EmitSignal("time_changed", _currentHour, _currentMinute);
        }
    }

    private static DayPhase GetPhaseForHour(int hour)
    {
        if (hour < 10) return DayPhase.Morning;
        if (hour < 12) return DayPhase.Forenoon;
        if (hour < 14) return DayPhase.Noon;
        if (hour < 18) return DayPhase.Afternoon;
        if (hour < 20) return DayPhase.Evening;
        return DayPhase.Night;
    }

    public float GetTimeProgress()
    {
        var totalTicks = 90; // (22-7)*60/10 = 90
        var currentTicks = (_currentHour - 7) * 6 + _currentMinute / 10;
        return (float)currentTicks / totalTicks;
    }

    public float GetSemesterProgress()
    {
        return (float)(_currentDay - 1) / 28f;
    }

    public Godot.Collections.Dictionary GetSaveData()
    {
        var data = new Godot.Collections.Dictionary();
        data["day"] = _currentDay;
        data["semester"] = new[] { "spring", "summer", "autumn", "winter" }[_semester];
        data["hour"] = _currentHour;
        data["minute"] = _currentMinute;
        return data;
    }

    public void LoadSaveData(Godot.Collections.Dictionary data)
    {
        _currentDay = (int)data["day"];
        var semStr = (string)data["semester"];
        var semIdx = new[] { "spring", "summer", "autumn", "winter" }.ToList().IndexOf(semStr);
        _semester = semIdx >= 0 ? semIdx : 0;
        _currentHour = (int)data["hour"];
        _currentMinute = (int)data["minute"];
        _currentPhase = GetPhaseForHour(_currentHour);
    }
}
