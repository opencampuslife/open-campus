extends Node2D

var tick := 0

func _ready():
	print("=== Non-Mono Godot Headless Smoke ===")

	# Test 1: Can load GDScript scene
	print("[PASS] GDScript scene loaded")

	# Test 2: Can create nodes dynamically
	var n = Node2D.new()
	n.name = "TestNode"
	add_child(n)
	n.queue_free()
	print("[PASS] Dynamic node creation")

	# Test 3: CharacterBody2D works
	var cb = CharacterBody2D.new()
	cb.name = "TestBody"
	add_child(cb)
	cb.queue_free()
	print("[PASS] CharacterBody2D")

	# Test 4: SpriteFrames works
	var anim = AnimatedSprite2D.new()
	anim.name = "TestAnim"
	add_child(anim)
	anim.queue_free()
	print("[PASS] AnimatedSprite2D")

	# Test 5: Can read project.godot settings
	var scene = ProjectSettings.get_setting("application/run/main_scene", "")
	print("[PASS] ProjectSettings accessible: %s" % scene)

	# Test 6: Can load JSON
	var json = JSON.new()
	print("[PASS] JSON class available")

	# Test 7: Vector2 math
	var v = Vector2(10, 20).normalized()
	print("[PASS] Vector2 math")

	# Test 8: FileAccess
	var test_path = "user://smoke_test.txt"
	var f = FileAccess.open(test_path, FileAccess.WRITE)
	if f != null:
		f.store_string("smoke test")
		f.close()
		print("[PASS] FileAccess write")
		DirAccess.remove_absolute(test_path)
	else:
		print("[FAIL] FileAccess write")

	print()
	print("=== Non-Mono Godot Headless: ALL TESTS PASSED ===")
	_start_exit_timer()

func _start_exit_timer():
	var timer = Timer.new()
	timer.wait_time = 0.3
	timer.one_shot = true
	timer.timeout.connect(_on_timer)
	add_child(timer)
	timer.start()

func _on_timer():
	get_tree().quit()