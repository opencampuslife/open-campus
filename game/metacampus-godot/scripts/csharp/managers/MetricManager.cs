using Godot;
using System.Collections.Generic;

public partial class MetricManager : Node
{
    [Signal] public delegate void MetricChangedEventHandler(string metricId, int oldValue, int newValue);
    [Signal] public delegate void SubMetricChangedEventHandler(string metricId, string subId, int oldValue, int newValue);
    [Signal] public delegate void ThresholdTriggeredEventHandler(string metricId, string consequenceId);

    private readonly Dictionary<string, int> _metrics = new()
    {
        { "school_efficiency", 40 },
        { "parent_trust", 50 },
        { "compliance_safety", 70 },
        { "system_stability", 60 }
    };

    private readonly Dictionary<string, Dictionary<string, int>> _subMetrics = new()
    {
        { "school_efficiency", new Dictionary<string, int>
            {
                { "work_order_backlog", 0 },
                { "enrollment_conversion", 50 },
                { "response_time", 80 }
            }
        },
        { "parent_trust", new Dictionary<string, int>
            {
                { "complaint_rate", 10 },
                { "student_satisfaction", 60 },
                { "reputation", 40 }
            }
        },
        { "compliance_safety", new Dictionary<string, int>
            {
                { "ai_hallucination_rate", 5 },
                { "kb_freshness", 60 },
                { "kb_coverage", 40 }
            }
        },
        { "system_stability", new Dictionary<string, int>
            {
                { "api_latency", 80 },
                { "kb_accuracy", 70 },
                { "citation_completeness", 50 }
            }
        }
    };

    public override void _Ready()
    {
        AddUserSignal("metric_changed");
        AddUserSignal("sub_metric_changed");
        AddUserSignal("threshold_triggered");
    }

    public int GetMetric(string metricId)
    {
        return _metrics.GetValueOrDefault(metricId, 0);
    }

    public void AddMetric(string metricId, int amount)
    {
        if (!_metrics.ContainsKey(metricId))
            _metrics[metricId] = 0;

        var oldValue = _metrics[metricId];
        _metrics[metricId] = Mathf.Clamp(_metrics[metricId] + amount, 0, 100);

        if (oldValue != _metrics[metricId])
        {
            EmitSignal("metric_changed", metricId, oldValue, _metrics[metricId]);
        }
    }

    public int GetSubMetric(string metricId, string subId)
    {
        if (!_subMetrics.ContainsKey(metricId))
            return 0;
        return _subMetrics[metricId].GetValueOrDefault(subId, 0);
    }

    public void AddSubMetric(string metricId, string subId, int amount)
    {
        if (!_subMetrics.ContainsKey(metricId))
            _subMetrics[metricId] = new Dictionary<string, int>();

        if (!_subMetrics[metricId].ContainsKey(subId))
            _subMetrics[metricId][subId] = 0;

        var oldValue = _subMetrics[metricId][subId];
        _subMetrics[metricId][subId] += amount;

        if (oldValue != _subMetrics[metricId][subId])
        {
            EmitSignal("sub_metric_changed", metricId, subId, oldValue, _subMetrics[metricId][subId]);
        }
    }

    public Godot.Collections.Dictionary GetMetricSnapshot()
    {
        var snapshot = new Godot.Collections.Dictionary();
        foreach (var pair in _metrics)
            snapshot[pair.Key] = pair.Value;
        return snapshot;
    }

    public Godot.Collections.Array<string> CheckThresholdConsequencesAndCollect()
    {
        var triggered = new Godot.Collections.Array<string>();
        CheckThresholdAndCollect("compliance_safety", 40, "audit_warning", triggered);
        CheckThresholdAndCollect("compliance_safety", 20, "suspend_ai_auto_reply", triggered);
        CheckThresholdAndCollect("system_stability", 40, "ai_tools_intermittent", triggered);
        CheckThresholdAndCollect("system_stability", 20, "system_outage", triggered);
        CheckThresholdAndCollect("parent_trust", 35, "complaint_increase", triggered);
        CheckThresholdAndCollect("parent_trust", 15, "reputation_crisis", triggered);
        CheckThresholdAndCollect("school_efficiency", 35, "task_backlog_double", triggered);
        CheckThresholdAndCollect("school_efficiency", 15, "principal_accountability", triggered);
        return triggered;
    }

    private void CheckThresholdAndCollect(string metricId, int threshold, string consequenceId, Godot.Collections.Array<string> collector)
    {
        if (_metrics.GetValueOrDefault(metricId, 0) < threshold)
        {
            EmitSignal("threshold_triggered", metricId, consequenceId);
            collector.Add(consequenceId);
        }
    }

    public Godot.Collections.Dictionary GetSubMetricSnapshot()
    {
        var result = new Godot.Collections.Dictionary();
        foreach (var pair in _subMetrics)
        {
            var subDict = new Godot.Collections.Dictionary();
            foreach (var subPair in pair.Value)
                subDict[subPair.Key] = subPair.Value;
            result[pair.Key] = subDict;
        }
        return result;
    }

    public Godot.Collections.Dictionary GetAllWithSubMetrics()
    {
        var result = new Godot.Collections.Dictionary();
        foreach (var pair in _metrics)
            result[pair.Key] = pair.Value;

        var subDict = new Godot.Collections.Dictionary();
        foreach (var metricPair in _subMetrics)
        {
            var subResult = new Godot.Collections.Dictionary();
            foreach (var subPair in metricPair.Value)
                subResult[subPair.Key] = subPair.Value;
            subDict[metricPair.Key] = subResult;
        }
        result["sub_metrics"] = subDict;
        return result;
    }

    public void CheckThresholdConsequences()
    {
        CheckThreshold("compliance_safety", 40, "audit_warning");
        CheckThreshold("compliance_safety", 20, "suspend_ai_auto_reply");
        CheckThreshold("system_stability", 40, "ai_tools_intermittent");
        CheckThreshold("system_stability", 20, "system_outage");
        CheckThreshold("parent_trust", 35, "complaint_increase");
        CheckThreshold("parent_trust", 15, "reputation_crisis");
        CheckThreshold("school_efficiency", 35, "task_backlog_double");
        CheckThreshold("school_efficiency", 15, "principal_accountability");
    }

    private void CheckThreshold(string metricId, int threshold, string consequenceId)
    {
        if (_metrics.GetValueOrDefault(metricId, 0) < threshold)
        {
            EmitSignal("threshold_triggered", metricId, consequenceId);
        }
    }

    public Godot.Collections.Dictionary GetSaveData()
    {
        var data = new Godot.Collections.Dictionary();
        foreach (var pair in _metrics)
            data[pair.Key] = pair.Value;

        var subData = new Godot.Collections.Dictionary();
        foreach (var metricPair in _subMetrics)
        {
            var subDict = new Godot.Collections.Dictionary();
            foreach (var subPair in metricPair.Value)
                subDict[subPair.Key] = subPair.Value;
            subData[metricPair.Key] = subDict;
        }
        data["sub_metrics"] = subData;
        return data;
    }

    public void LoadSaveData(Godot.Collections.Dictionary data)
    {
        foreach (var key in data.Keys)
        {
            var strKey = key.ToString();
            if (_metrics.ContainsKey(strKey))
                _metrics[strKey] = (int)data[key];
        }

        if (data.ContainsKey("sub_metrics"))
        {
            var subData = (Godot.Collections.Dictionary)data["sub_metrics"];
            foreach (var metricKey in subData.Keys)
            {
                var metricStr = metricKey.ToString();
                if (!_subMetrics.ContainsKey(metricStr))
                    _subMetrics[metricStr] = new Dictionary<string, int>();

                var subDict = (Godot.Collections.Dictionary)subData[metricKey];
                foreach (var subKey in subDict.Keys)
                {
                    _subMetrics[metricStr][subKey.ToString()] = (int)subDict[subKey];
                }
            }
        }
    }
}
