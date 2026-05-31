extends SceneTree

## Quick NPC sprite load verification
## Run: godot --headless --path . --script verify_sprites.gd

var _done := false

func _init():
	print("=== Sprite Load Verification ===")

	var root_node = root
	if root_node == null:
		print("ERROR: no root")
		_done = true
		return

	# Load Main.tscn
	var main_scene = load("res://scenes/Main.tscn")
	if main_scene == null:
		print("ERROR: Main.tscn not found")
		_done = true
		return

	print("Main.tscn loaded OK")

	var inst = main_scene.instantiate()
	if inst == null:
		print("ERROR: Main.tscn instantiate failed")
		_done = true
		return

	root_node.add_child(inst)
	print("Main.tscn instantiated OK")

	# Check NPC container
	var npc_container = inst.get_node_or_null("NPCContainer")
	if npc_container == null:
		print("ERROR: NPCContainer not found")
	else:
		print("NPCContainer found")
		var npc_names = ["Npc_Principal","Npc_AdmissionsDirector","Npc_HomeroomTeacher","Npc_ItOperator","Npc_LogisticsManager","Npc_ComplianceOfficer","Npc_ParentRepresentative","Npc_StudentRepresentative"]
		for name in npc_names:
			var npc = npc_container.get_node_or_null(name)
			if npc == null:
				print("ERROR: NPC not found: " + name)
			else:
				var sprite = npc.get_node_or_null("Sprite2D")
				if sprite == null:
					print("ERROR: Sprite2D missing on: " + name)
				else:
					var tex = sprite.texture
					if tex == null:
						print("WARN: Sprite2D has no texture: " + name)
					else:
						print("OK: " + name + " has texture")

	inst.queue_free()
	_done = true

func _process(_delta: float) -> bool:
	if _done:
		quit()
		return false
	return false