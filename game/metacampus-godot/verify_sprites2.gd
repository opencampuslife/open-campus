extends SceneTree

## Sprite load verification that works with autoloads
## Run: godot --headless --path . --script verify_sprites2.gd

var _done := false

func _init():
	print("=== Sprite Load Verification ===")

	var main_scene = load("res://scenes/Main.tscn")
	if main_scene == null:
		print("ERROR: Main.tscn not found")
		_done = true
		return

	print("Main.tscn script loaded OK")

	# Instantiate the scene
	var inst = main_scene.instantiate()
	if inst == null:
		print("ERROR: instantiate() returned null")
		_done = true
		return

	root.add_child(inst)
	print("Main.tscn instantiated OK")

	# Wait one frame for _ready to run
	await process_frame
	await process_frame

	# Check NPCContainer
	var npc_container = inst.get_node_or_null("NPCContainer")
	if npc_container == null:
		print("ERROR: NPCContainer not found")
		inst.queue_free()
		_done = true
		return

	var npc_names = [
		"Npc_Principal", "Npc_AdmissionsDirector", "Npc_HomeroomTeacher",
		"Npc_ItOperator", "Npc_LogisticsManager", "Npc_ComplianceOfficer",
		"Npc_ParentRepresentative", "Npc_StudentRepresentative"
	]

	var sprites_ok = 0
	for name in npc_names:
		var npc = npc_container.get_node_or_null(name)
		if npc == null:
			print("ERROR: NPC node missing: " + name)
			continue

		# Check npc_id export
		var id = npc.get("npc_id")
		print("  " + name + " npc_id=" + str(id))

		# Check Sprite2D
		var sprite = npc.get_node_or_null("Sprite2D")
		if sprite == null:
			print("  ERROR: Sprite2D missing on " + name)
			continue

		var tex = sprite.get("texture")
		if tex == null:
			print("  WARN: no texture on " + name)
		else:
			print("  OK: " + name + " has texture: " + str(tex))
			sprites_ok += 1

	print()
	print("Sprites with texture: " + str(sprites_ok) + "/8")

	# Check QuestBoard
	var qb = inst.get_node_or_null("QuestBoard")
	if qb:
		var qb_sprite = qb.get_node_or_null("Sprite2D")
		if qb_sprite:
			var tex2 = qb_sprite.get("texture")
			if tex2:
				print("OK: QuestBoard has texture")
			else:
				print("WARN: QuestBoard no texture")
		else:
			print("WARN: QuestBoard no Sprite2D")
	else:
		print("ERROR: QuestBoard not found")

	inst.queue_free()
	_done = true

func _process(_delta: float) -> bool:
	if _done:
		quit()
		return false
	return false