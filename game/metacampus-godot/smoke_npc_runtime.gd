extends MainLoop

## NPC Runtime Smoke Test
## 运行方式: godot --headless --path . --script smoke_npc_runtime.gd
## extends MainLoop 满足 --script 约束，同时 project autoload 可用

var results := []
var total_pass := 0
var total_fail := 0

func _initialize() -> void:
	print("══════════════════════════════════════════════════")
	print("  NPC Runtime Smoke Test — Godot %s" % Engine.get_version_info()["version"])
	print("══════════════════════════════════════════════════")
	print()

	_run_tests()

	print()
	print("══════════════════════════════════════════════════")
	print("  SUMMARY: %d passed, %d failed, %d total" % [total_pass, total_fail, results.size()])
	print("══════════════════════════════════════════════════")


func _process(_delta: float) -> bool:
	# 一帧后退出（测试已完成）
	print()
	print("[EXIT] Smoke test complete, quitting...")
	get_tree().quit()
	return true  # process returns bool in MainLoop context


func _idle(_delta: float) -> bool:
	return false  # 不阻止退出


func _run_tests() -> void:
	print("[1/4] NpcRegistry 加载...")
	var npc_count := _test_npc_registry()
	print()

	print("[2/4] 资产路径验证...")
	_test_asset_paths()
	print()

	print("[3/4] NpcSpriteLoader manifest 解析...")
	_test_sprite_loader()
	print()

	print("[4/4] NpcFactory 构建 AnimatedSprite2D...")
	_test_npc_factory()
	print()


func _test_npc_registry() -> int:
	var npc_reg = get_node_or_null("/root/NpcRegistry")
	if npc_reg == null:
		_add_result("NpcRegistry", false, "Autoload 未注册")
		print("  ✗ NpcRegistry 未注册于 /root")
		return 0

	if not npc_reg.has_method("get_all_npcs"):
		_add_result("NpcRegistry", false, "get_all_npcs 方法缺失")
		print("  ✗ get_all_npcs 方法不存在")
		return 0

	var all_npcs = npc_reg.get_all_npcs()
	var count := all_npcs.size()

	if count == 0:
		_add_result("NpcRegistry", false, "无 NPC 数据")
		print("  ✗ 加载 0 个 NPC")
		return 0

	if count >= 8:
		_add_result("NpcRegistry", true, "加载 %d 个 NPC OK" % count)
		print("  ✓ 加载 %d 个 NPC profile" % count)
		for npc in all_npcs:
			print("    - %s (%s)" % [npc.get("npc_id", "?"), npc.get("role", "?")])
	else:
		_add_result("NpcRegistry", false, "NPC 数量不足: 期望 8, 实际 %d" % count)
		print("  ✗ 仅加载 %d 个 NPC（期望 8）" % count)

	# 逐个验证
	var expected := [
		"principal", "admissions_director", "homeroom_teacher",
		"it_operator", "logistics_manager", "compliance_officer",
		"parent_representative", "student_representative"
	]
	var loaded_ids := all_npcs.map(func(n): return n.get("npc_id", ""))
	var missing := expected.filter(func(e): return not loaded_ids.has(e))
	if not missing.is_empty():
		print("  ✗ 缺少: %s" % ", ".join(missing))

	return count


func _test_asset_paths() -> void:
	var npc_reg = get_node("/root/NpcRegistry")
	var all_npcs = npc_reg.get_all_npcs()
	var ok_count := 0
	var fail_count := 0

	for npc in all_npcs:
		var npc_id: String = npc.get("npc_id", "")
		var asset_root: String = npc.get("asset_root", "")
		if asset_root.is_empty():
			asset_root = "res://assets/npcs/" + npc_id

		var idle_candidates := [
			asset_root + "/sprite_idle.png",
			asset_root + "/baseline/sprite_idle.png",
		]
		var idle_found := ""
		for c in idle_candidates:
			if ResourceLoader.exists(c):
				idle_found = c
				break

		var has_spec := ResourceLoader.exists(asset_root + "/animation_spec.json")

		var status: String
		if idle_found != "" and has_spec:
			status = "OK (idle+spec)"
			ok_count += 1
		elif idle_found != "":
			status = "WARN (idle only)"
			ok_count += 1
		else:
			status = "FAIL (no sprite)"
			fail_count += 1

		var icon := "✓" if status.begins_with("OK") else ("~" if status.begins_with("WARN") else "✗")
		print("  %s %s: %s" % [icon, npc_id, status])
		_add_result("asset:" + npc_id, status.begins_with("OK"), status)

	print("  资产路径: %d OK, %d FAIL" % [ok_count, fail_count])


func _test_sprite_loader() -> void:
	var npc_reg = get_node("/root/NpcRegistry")
	var all_npcs = npc_reg.get_all_npcs()
	var ok_count := 0

	# 动态调用 NpcSpriteLoader（class_name，通过 call 绕过编译期引用）
	var loader_path := "res://scripts/npc_sprite_loader.gd"
	if not ResourceLoader.exists(loader_path):
		print("  ✗ npc_sprite_loader.gd 不存在")
		return

	for npc in all_npcs:
		var npc_id: String = npc.get("npc_id", "")
		var asset_root: String = npc.get("asset_root", "")
		if asset_root.is_empty():
			asset_root = "res://assets/npcs/" + npc_id

		var spec_dir := asset_root
		if spec_dir.ends_with("/baseline"):
			spec_dir = spec_dir.substr(0, spec_dir.length() - len("/baseline"))

		var spec_path := spec_dir + "/animation_spec.json"

		if not ResourceLoader.exists(spec_path):
			_add_result("sprite_loader:" + npc_id, false, "spec 缺失")
			print("  ✗ %s: animation_spec.json 缺失" % npc_id)
			continue

		var idle_path := asset_root + "/baseline/sprite_idle.png"
		if not ResourceLoader.exists(idle_path):
			idle_path = asset_root + "/sprite_idle.png"
		if not ResourceLoader.exists(idle_path):
			idle_path = spec_dir + "/baseline/sprite_idle.png"

		# 调用静态方法
		var frames: SpriteFrames = _call_sprite_loader(spec_dir, spec_path, idle_path)
		var anim_names: Array = frames.get_animation_names()
		var anim_count := anim_names.size()

		if anim_count > 0:
			var idle_frames: int = frames.get_frame_count("idle")
			print("  ✓ %s: %d 动画 (%d idle帧)" % [npc_id, anim_count, idle_frames])
			_add_result("sprite_loader:" + npc_id, true, "%d 动画解析 OK" % anim_count)
			ok_count += 1
		else:
			print("  ✗ %s: SpriteFrames 解析失败" % npc_id)
			_add_result("sprite_loader:" + npc_id, false, "无动画")

	print("  NpcSpriteLoader: %d/%d 解析成功" % [ok_count, all_npcs.size()])


func _call_sprite_loader(spec_dir: String, spec_path: String, idle_path: String) -> SpriteFrames:
	var script: GDScript = load("res://scripts/npc_sprite_loader.gd") as GDScript
	if script == null:
		return SpriteFrames.new()

	var inst = script.new() as RefCounted
	if inst != null and inst.has_method("build_from_spec_with_idle"):
		var result = inst.call("build_from_spec_with_idle", spec_dir, spec_path, idle_path)
		inst.unreference()
		return result as SpriteFrames
	if inst != null:
		inst.unreference()
	return SpriteFrames.new()


func _test_npc_factory() -> void:
	var factory_path := "res://scripts/npc_factory.gd"
	if not ResourceLoader.exists(factory_path):
		print("  ✗ npc_factory.gd 不存在")
		return

	var factory_script: GDScript = load(factory_path) as GDScript
	if factory_script == null:
		print("  ✗ 无法加载 NpcFactory 脚本")
		return

	var factory_node: Node = factory_script.new() as Node
	if factory_node == null:
		print("  ✗ NpcFactory.new() 返回 null")
		return

	var npc_reg = get_node("/root/NpcRegistry")
	var all_npcs = npc_reg.get_all_npcs()
	var ok_count := 0

	for npc in all_npcs:
		var npc_id: String = npc.get("npc_id", "")

		var npc_node: Node = factory_node.call("create_npc", npc_id) as Node

		if npc_node == null:
			print("  ✗ %s: create_npc() 返回 null" % npc_id)
			_add_result("npc_factory:" + npc_id, false, "create_npc 返回 null")
			continue

		var node_type: String = npc_node.get_class()
		var has_sprite: bool = npc_node.has_node("AnimatedSprite2D")
		var has_bodyrect: bool = npc_node.has_node("BodyRect")

		var status: String
		if has_sprite:
			status = "OK (AnimatedSprite2D)"
			ok_count += 1
		elif has_bodyrect:
			status = "WARN (ColorRect fallback)"
			ok_count += 1
		else:
			status = "FAIL (no sprite layer)"

		var icon := "✓" if status.begins_with("OK") else ("~" if status.begins_with("WARN") else "✗")
		print("  %s %s: %s [%s]" % [icon, npc_id, status, node_type])
		_add_result("npc_factory:" + npc_id, status.begins_with("OK") or status.begins_with("WARN"), status)

		npc_node.queue_free()

	factory_node.queue_free()

	print("  NpcFactory: %d/%d 构建成功" % [ok_count, all_npcs.size()])


func _add_result(name: String, passed: bool, detail: String) -> void:
	results.append({"name": name, "passed": passed, "detail": detail})
	if passed:
		total_pass += 1
	else:
		total_fail += 1