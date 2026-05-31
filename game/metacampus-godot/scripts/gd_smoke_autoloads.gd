extends Node2D

var tick := 0

func _ready():
	print("=== GDScript Smoke with Autoloads ===")

	# Test NpcRegistry autoload
	var nr = get_node_or_null("/root/NpcRegistry")
	if nr == null:
		print("[FAIL] NpcRegistry not found at /root")
		_start_exit_timer()
		return

	var all = nr.get_all_npcs()
	print("NPC_COUNT=%d" % all.size())
	for n in all:
		print("  %s | %s | %s" % [n.get("npc_id", "?"), n.get("display_name", "?"), n.get("role", "?")])

	# Test DialogueManager autoload
	var dm = get_node_or_null("/root/DialogueManager")
	if dm == null:
		print("[FAIL] DialogueManager not found")
	else:
		print("[PASS] DialogueManager autoload OK")

	# Test MetricManager autoload
	var mm = get_node_or_null("/root/MetricManager")
	if mm == null:
		print("[FAIL] MetricManager not found")
	else:
		print("[PASS] MetricManager autoload OK")

	# Test QuestManager autoload
	var qm = get_node_or_null("/root/QuestManager")
	if qm == null:
		print("[FAIL] QuestManager not found")
	else:
		print("[PASS] QuestManager autoload OK")

	print("=== Smoke Done ===")
	_start_exit_timer()

func _start_exit_timer():
	var timer = Timer.new()
	timer.wait_time = 0.5
	timer.one_shot = true
	timer.timeout.connect(_on_timer)
	add_child(timer)
	timer.start()

func _on_timer():
	get_tree().quit()