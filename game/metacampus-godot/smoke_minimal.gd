extends MainLoop

## Minimal smoke: load NpcRegistry, print 8 NPC IDs via MainLoop API.
func _initialize() -> void:
	print("=== SMOKE START ===")

	var ml = Engine.get_main_loop()
	if ml == null:
		print("ERROR: no main loop")
		ml.quit()
		return

	var nr = ml.get_node_or_null("/root/NpcRegistry")
	if nr == null:
		print("ERROR: NpcRegistry not registered")
		ml.quit()
		return

	var all = nr.get_all_npcs()
	print("NPC_COUNT=%d" % all.size())
	for n in all:
		print("  %s | %s | %s" % [n.get("npc_id", "?"), n.get("display_name", "?"), n.get("role", "?")])

	print("=== SMOKE DONE ===")
	ml.quit()

func _process(_delta: float) -> bool:
	return false  # return true to keep running

func _idle(_delta: float) -> bool:
	return false