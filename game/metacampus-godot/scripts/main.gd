extends Node2D

func _ready():
	print("=== Main.tscn loaded ===")
	print("  Children: %d" % get_child_count())
	for c in get_children():
		print("    - %s" % c.name)

	# Load NpcScene.tscn to verify SubResource parsing
	var npc_scene = load("res://scenes/NPCs/NpcScene.tscn")
	if npc_scene:
		var instance = npc_scene.instantiate()
		if instance:
			print("[PASS] NpcScene.tscn instantiated OK")
			instance.queue_free()
		else:
			print("[FAIL] NpcScene.tscn instantiate returned null")
	else:
		print("[FAIL] NpcScene.tscn failed to load")

	# Load CampusMap to verify PackedScene
	var map_scene = load("res://scenes/CampusMap.tscn")
	if map_scene:
		var map_inst = map_scene.instantiate()
		if map_inst:
			print("[PASS] CampusMap.tscn instantiated OK")
			map_inst.queue_free()
		else:
			print("[WARN] CampusMap.tscn returned null (may be OK)")
	else:
		print("[FAIL] CampusMap.tscn failed to load")

	print("=== Main.tscn smoke done ===")
	_start_exit_timer()

func _start_exit_timer():
	var timer = Timer.new()
	timer.wait_time = 1.0
	timer.one_shot = true
	timer.timeout.connect(_on_timer)
	add_child(timer)
	timer.start()

func _on_timer():
	get_tree().quit()