extends MainLoop

## G2 冒烟验证脚本
## 运行: godot --headless --path . --script smoke_g2_verify.gd

var pass_count := 0
var fail_count := 0
var results := []
var _done := false
var _st: SceneTree = null

func _initialize() -> void:
	print("══════════════════════════════════════════════════")
	print("  G2 Smoke Verification")
	print("══════════════════════════════════════════════════")
	print()
	
	_st = Engine.get_main_loop() as SceneTree
	if _st == null:
		print("ERROR: no SceneTree main loop")
		_done = true
		return
	
	var root := _st.root
	if root == null:
		print("ERROR: no scene tree root")
		_done = true
		return

	_check("TestHarness Autoload", func():
		var t = root.get_node_or_null("/root/TestHarness")
		return [t != null, "TestHarness registered"])

	_check("JsonLoader Autoload", func():
		var jl = root.get_node_or_null("/root/JsonLoader")
		return [jl != null, "JsonLoader registered"])

	_check("QuestManager Autoload", func():
		var qm = root.get_node_or_null("/root/QuestManager")
		return [qm != null, "QuestManager registered"])

	_check("MetricManager Autoload", func():
		var mm = root.get_node_or_null("/root/MetricManager")
		return [mm != null, "MetricManager registered"])

	_check("ApiClient Autoload", func():
		var ac = root.get_node_or_null("/root/ApiClient")
		return [ac != null, "ApiClient registered"])

	_check("NpcRegistry Autoload", func():
		var nr = root.get_node_or_null("/root/NpcRegistry")
		return [nr != null, "NpcRegistry registered"])

	# ── NpcRegistry ──
	var nr = root.get_node_or_null("/root/NpcRegistry")
	if nr:
		var all_npcs = nr.get_all_npcs()
		_check("NpcRegistry count >= 5", func():
			return [all_npcs.size() >= 5, "Loaded %d NPCs" % all_npcs.size()])

	# ── QuestManager ──
	var qm = root.get_node_or_null("/root/QuestManager")
	if qm:
		var quests = qm.get_all_quests()
		_check("QuestManager 8 quests", func():
			return [quests.size() == 8, "Loaded %d quests" % quests.size()])
		
		var t1_status = qm.get_quest_status("q_admission_001")
		_check("T1 initially available", func():
			return [t1_status == "available", "T1 status = '%s'" % t1_status])
		
		var activated = qm.activate_quest("q_admission_001")
		_check("Quest activate", func():
			return [activated == true, "q_admission_001 activated"])
		
		var completed = qm.complete_quest("q_admission_001")
		_check("Quest complete", func():
			return [completed == true, "q_admission_001 completed"])
		
		var t1_status2 = qm.get_quest_status("q_admission_001")
		_check("T1 status after complete", func():
			return [t1_status2 == "completed", "T1 status = '%s'" % t1_status2])
		
		var completed2 = qm.complete_quest("q_admission_001")
		_check("Quest double-complete blocked", func():
			return [completed2 == false, "Double complete returned %s" % str(completed2)])

	# ── MetricManager ──
	var mm = root.get_node_or_null("/root/MetricManager")
	if mm:
		_check("Metric school_efficiency=40", func():
			return [mm.get_value("school_efficiency") == 40, "Got %d" % mm.get_value("school_efficiency")])
		_check("Metric parent_trust=50", func():
			return [mm.get_value("parent_trust") == 50, "Got %d" % mm.get_value("parent_trust")])
		_check("Metric compliance_safety=70", func():
			return [mm.get_value("compliance_safety") == 70, "Got %d" % mm.get_value("compliance_safety")])
		_check("Metric system_stability=60", func():
			return [mm.get_value("system_stability") == 60, "Got %d" % mm.get_value("system_stability")])
		
		mm.apply_effects({"parent_trust": 8, "compliance_safety": 5})
		_check("Metric apply_effects parent_trust 50+8", func():
			return [mm.get_value("parent_trust") == 58, "Got %d" % mm.get_value("parent_trust")])
		_check("Metric apply_effects compliance_safety 70+5", func():
			return [mm.get_value("compliance_safety") == 75, "Got %d" % mm.get_value("compliance_safety")])
		
		mm.apply_effects({"compliance_safety": -200})
		_check("Metric clamp 0 min", func():
			return [mm.get_value("compliance_safety") == 0, "Min clamped to %d" % mm.get_value("compliance_safety")])
		
		mm.apply_effects({"compliance_safety": 500})
		_check("Metric clamp 100 max", func():
			return [mm.get_value("compliance_safety") == 100, "Max clamped to %d" % mm.get_value("compliance_safety")])
		
		mm.reset_all()
		_check("Metric reset_all parent_trust=50", func():
			return [mm.get_value("parent_trust") == 50, "Reset parent_trust=%d" % mm.get_value("parent_trust")])

	# ── Dialogue Data ──
	var jl = root.get_node_or_null("/root/JsonLoader")
	if jl:
		var dialogues = jl.load_dialogues()
		var dlg_list = dialogues.get("dialogues", [])
		_check("Dialogues loaded", func():
			return [dlg_list.size() > 0, "Loaded %d dialogues" % dlg_list.size()])
		
		var parent_dlg = null
		for d in dlg_list:
			if d.get("npc_id") == "parent_001":
				parent_dlg = d
				break
		_check("parent_001 dialogue exists", func():
			return [parent_dlg != null, "Found"])
		
		if parent_dlg:
			var lines = parent_dlg.get("lines", [])
			_check("parent_001 has 3+ lines", func():
				return [lines.size() >= 3, "%d lines" % lines.size()])
			
			var line0 = lines[0]
			_check("T1 line has quest_id", func():
				return [line0.get("quest_id", "") == "q_admission_001", "quest_id=%s" % line0.get("quest_id", "")])
			var choices0 = line0.get("choices", [])
			_check("T1 has 2+ choices", func():
				return [choices0.size() >= 2, "%d choices" % choices0.size()])
		
		var ai_dlg = null
		for d in dlg_list:
			if d.get("npc_id") == "ai_assistant_001":
				ai_dlg = d
				break
		_check("ai_assistant_001 dialogue exists", func():
			return [ai_dlg != null, "Found"])
		
		if ai_dlg:
			var lines = ai_dlg.get("lines", [])
			_check("ai_assistant has 2+ lines", func():
				return [lines.size() >= 2, "%d lines" % lines.size()])
			var line0 = lines[0]
			_check("T7 line has quest_id (fix 5)", func():
				return [line0.get("quest_id", "") == "q_dashboard_001", "quest_id=%s" % line0.get("quest_id", "")])
			var line1 = lines[1]
			_check("T8 line has quest_id", func():
				return [line1.get("quest_id", "") == "q_canary_release_001", "quest_id=%s" % line1.get("quest_id", "")])

	# ── DialogueManager method check ──
	_check("DialogueManager has quest-aware skipping", func():
		var dm_script = load("res://scripts/dialogue_manager.gd")
		return [dm_script != null and dm_script.has_method("_find_first_available_line"), "Method exists"])

	_print_summary()
	_done = true


func _check(name: String, test: Callable) -> void:
	var result = test.call()
	var passed = result[0] if result.size() > 0 else false
	var detail = result[1] if result.size() > 1 else ""
	var icon = "✓" if passed else "✗"
	print("  %s %s: %s" % [icon, name, detail])
	results.append({"name": name, "passed": passed})
	if passed:
		pass_count += 1
	else:
		fail_count += 1


func _print_summary() -> void:
	print()
	print("══════════════════════════════════════════════════")
	print("  RESULTS: %d passed, %d failed, %d total" % [pass_count, fail_count, results.size()])
	print("══════════════════════════════════════════════════")
	for r in results:
		var icon = "✓" if r.passed else "✗"
		print("  %s %s" % [icon, r.name])


func _process(_delta: float) -> bool:
	if _done:
		print()
		print("[EXIT] Tests complete, quitting...")
		if _st:
			_st.quit()
		return false
	return false


func _idle(_delta: float) -> bool:
	return false
