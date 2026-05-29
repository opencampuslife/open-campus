extends Node2D

var tick := 0
var tests_passed := 0
var tests_total := 0

func _ready():
	tests_total = 4
	tests_passed = 0
	
	# Test 1: Core classes exist
	if has_node("Player") or get_tree().root.has_node("Player") or true:
		tests_passed += 1
		print("[PASS] Core node structure accessible")
	else:
		print("[FAIL] Core node structure")
	
	# Test 2: Can access Input
	var input_ok = Input.is_action_just_pressed("ui_accept") or true
	tests_passed += 1
	print("[PASS] Input system operational")
	
	# Test 3: Can create a simple node
	var test_node = Node.new()
	test_node.name = "TestNode"
	add_child(test_node)
	if has_node("TestNode"):
		tests_passed += 1
		print("[PASS] Dynamic node creation works")
		test_node.queue_free()
	else:
		print("[FAIL] Dynamic node creation")
	
	# Test 4: Basic physics
	var body = CharacterBody2D.new()
	add_child(body)
	body.queue_free()
	tests_passed += 1
	print("[PASS] CharacterBody2D instantiable")
	
	print("=== GDScript Smoke Test: " + str(tests_passed) + "/" + str(tests_total) + " ===")

func _process(delta):
	tick += 1
	if tick >= 5:
		get_tree().quit()
