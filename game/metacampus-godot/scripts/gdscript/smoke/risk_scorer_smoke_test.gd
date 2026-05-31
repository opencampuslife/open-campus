extends Node2D

## RiskScorer GDExtension Smoke Test
## 测试非 Mono Godot headless 下的 GDExtension 加载和 evaluate_text 调用

var tests_passed := 0
var tests_total := 5

func _ready():
	print("=== RiskScorer GDExtension Smoke Test ===")
	print()

	# Test 1: RiskScorer class exists
	print("[1/5] Testing if RiskScorer class exists...")
	var has_class: bool = ClassDB.class_exists("RiskScorer")
	if has_class:
		print("[PASS] RiskScorer class exists in ClassDB")
		tests_passed += 1
	else:
		print("[FAIL] RiskScorer class does not exist")
		_finish_test(false)
		return
	print()

	# Test 2: Can instantiate RiskScorer
	print("[2/5] Testing RiskScorer instantiation...")
	var scorer = ClassDB.instantiate("RiskScorer")
	if scorer != null:
		print("[PASS] RiskScorer instantiated")
		tests_passed += 1
	else:
		print("[FAIL] ClassDB.instantiate returned null")
		_finish_test(false)
		return
	print()

	# Test 3: evaluate_text method exists and returns structure
	print("[3/5] Testing evaluate_text() method...")
	if scorer.has_method("evaluate_text"):
		var ctx = {"scenario": "general", "citation_count": 1}
		var result = scorer.evaluate_text("hello", "world", ctx)
		
		var has_keys: bool = result.has("risk_score") and result.has("risk_level") and result.has("recommended_action")
		if has_keys:
			print("[PASS] evaluate_text returned correct structure")
			print("  risk_score: %s" % str(result.get("risk_score", "N/A")))
			print("  risk_level: %s" % str(result.get("risk_level", "N/A")))
			print("  action: %s" % str(result.get("recommended_action", "N/A")))
			tests_passed += 1
		else:
			print("[FAIL] evaluate_text missing required keys")
			_finish_test(false)
			return
	else:
		print("[FAIL] evaluate_text method not found on RiskScorer")
		_finish_test(false)
		return
	print()

	# Test 4: "保证录取" triggers high/block
	print("[4/5] Testing rule: '保证录取' -> high/block...")
	var result2 = scorer.evaluate_text("能保证吗？", "我们可以保证录取！", {})
	var score2: int = int(result2.get("risk_score", 0))
	var level2: String = str(result2.get("risk_level", ""))
	var action2: String = str(result2.get("recommended_action", ""))
	var rules2 = result2.get("triggered_rules", [])
	
	print("  Raw result: score=%d, level=%s, action=%s" % [score2, level2, action2])
	print("  Triggered rules: %s" % str(rules2))
	
	if score2 >= 70 and (level2 == "high" or level2 == "critical") and action2 == "block":
		print("[PASS] Rule triggered correctly")
		tests_passed += 1
	else:
		print("[FAIL] Rule not triggered as expected")
	print()

	# Test 5: "走关系" triggers critical/block
	print("[5/5] Testing rule: '走关系' -> critical/block...")
	var result3 = scorer.evaluate_text("有关系吗？", "可以走关系找人疏通！", {})
	var score3: int = int(result3.get("risk_score", 0))
	var level3: String = str(result3.get("risk_level", ""))
	var action3: String = str(result3.get("recommended_action", ""))
	var rules3 = result3.get("triggered_rules", [])
	
	print("  Raw result: score=%d, level=%s, action=%s" % [score3, level3, action3])
	print("  Triggered rules: %s" % str(rules3))
	
	if score3 >= 90 and level3 == "critical" and action3 == "block":
		print("[PASS] '走关系' rule triggered correctly")
		tests_passed += 1
	else:
		print("[FAIL] '走关系' rule not triggered as expected")
	print()

	_finish_test(true)

func _finish_test(all_passed: bool):
	print()
	print("=== SUMMARY ===")
	print("  Tests passed: %d/%d" % [tests_passed, tests_total])
	
	if tests_passed >= 4:
		print("  [PASS] RiskScorer GDExtension smoke test PASSED")
	else:
		print("  [FAIL] RiskScorer GDExtension smoke test FAILED")
	
	# Cleanup
	var timer := Timer.new()
	timer.wait_time = 0.5
	timer.one_shot = true
	timer.timeout.connect(_on_timer)
	add_child(timer)
	timer.start()

func _on_timer():
	get_tree().quit()