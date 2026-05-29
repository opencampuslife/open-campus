extends SceneTree
## P1B Resilience Headless Test Suite
##
## Tests 6 resilience mechanisms of api_client.gd (cache hit, cache TTL,
## cache disabled, timeout fallback, queue overflow, high-risk no-cache)
## through the full ask_knowledge() path.
##
## NOTE: In Godot 4.6, lambda captures of local Dictionary variables are
## BUGGED (captured = r does not update the outer variable). Use Array
## wrappers to work around this — Array is a reference type and mutations
## (like holder[0] = r) ARE visible outside the lambda.
##
## Outputs JSON-structured results to stdout between markers.
##
## Usage:
##   godot --headless --path <project> --script tools/test_resilience_capture.gd

const API_CLIENT_PATH := "res://scripts/api_client.gd"

var _ac: Node = null
var _results: Array[Dictionary] = []

func _init() -> void:
	var cls = load(API_CLIENT_PATH)
	_ac = cls.new()
	root.add_child(_ac)
	await process_frame

	_ac.BENCH_MODE = true

	print("[P1B] Starting 6 resilience tests...")

	await _test_cache_hit()
	await _test_cache_ttl()
	await _test_cache_disabled()
	await _test_timeout_fallback()
	await _test_queue_overflow()
	await _test_high_risk_not_cached()

	print("\n[=== RESULTS ===")
	print(JSON.stringify(_results))
	print("=== END ===]")
	quit()


# ── Helpers ──

func _reset() -> void:
	## Reset ApiClient for a fresh test. Uses .clear() and direct
	## property access for internal state; falls back to .set() where
	## the base Node type blocks direct assignment.
	var empty_cache: Dictionary = {}
	_ac.set("_cache", empty_cache)
	var empty_order: Array = []
	_ac.set("_cache_order", empty_order)
	var br: Array = []
	_ac.set("_bench_results", br)
	_ac.set("_bench_request_counter", 0)
	_ac.set("_bench_pending", {})
	_ac.set("_bench_cache_hit", 0)
	_ac.set("_bench_cache_miss", 0)
	_ac.set("_bench_timeout_count", 0)
	_ac.set("_bench_fallback_count", 0)
	_ac.set("_live_request_count", 0)
	_ac.set("_active_requests", {})
	_ac.set("_request_queue", [])


func _append(name: String, ok: bool, details: Dictionary) -> void:
	_results.append({"test": name, "passed": ok, "details": details})


# ── Test 1: Cache hit ──
func _test_cache_hit() -> void:
	_reset()
	_ac.set_mode("mock")
	_ac.set("_cache_enabled", true)
	_ac._cache_ttl_ms = 300000

	var cached_resp := {"ok": true, "answer": "cached_answer", "citations": [], "handoff_required": false}
	var key = _ac._cache_key("报名需要哪些材料")
	var now := Time.get_unix_time_from_system() * 1000
	_ac._cache[key] = {"response": cached_resp.duplicate(true), "timestamp": now}
	_ac._cache_order.append(key)

	# Use Array wrapper to work around Godot 4.6 lambda capture bug
	var holder: Array = [{}]
	_ac.ask_knowledge("报名需要哪些材料", func(r): holder[0] = r)
	await process_frame

	var lt: Dictionary = _ac._bench_results[-1] if _ac._bench_results.size() > 0 else {}
	var hit: bool = lt.get("cache_hit", false)
	var answer_ok: bool = holder[0].get("answer", "") == "cached_answer"

	_append("cache_hit", hit and answer_ok, {
		"cache_hit": hit,
		"captured_answer": holder[0].get("answer", ""),
		"expected_answer": "cached_answer",
		"cache_size": _ac._cache.size(),
		"trace": lt,
	})


# ── Test 2: Cache TTL expiry ──
func _test_cache_ttl() -> void:
	_reset()
	_ac.set_mode("mock")
	_ac.set("_cache_enabled", true)
	_ac._cache_ttl_ms = 1000

	var cached_resp := {"ok": true, "answer": "stale_answer", "citations": [], "handoff_required": false}
	var key = _ac._cache_key("报名需要哪些材料")
	var stale_ts := (Time.get_unix_time_from_system() * 1000) - 5000
	_ac._cache[key] = {"response": cached_resp.duplicate(true), "timestamp": stale_ts}
	_ac._cache_order.append(key)

	var holder: Array = [{}]
	_ac.ask_knowledge("报名需要哪些材料", func(r): holder[0] = r)
	await process_frame

	var lt: Dictionary = _ac._bench_results[-1] if _ac._bench_results.size() > 0 else {}
	var miss: bool = lt.get("cache_miss", false)
	var sz: int = _ac._cache.size()

	_append("cache_ttl", miss and sz == 0, {
		"cache_miss": miss,
		"cache_size": sz,
		"trace": lt,
	})


# ── Test 3: Cache disabled ──
func _test_cache_disabled() -> void:
	_reset()
	_ac.set_mode("mock")
	_ac.set("_cache_enabled", false)
	_ac._cache_ttl_ms = 300000

	var cached_resp := {"ok": true, "answer": "should_not_be_returned", "citations": [], "handoff_required": false}
	var key = _ac._cache_key("报名需要哪些材料")
	var now := Time.get_unix_time_from_system() * 1000
	_ac._cache[key] = {"response": cached_resp.duplicate(true), "timestamp": now}
	_ac._cache_order.append(key)

	var holder: Array = [{}]
	_ac.ask_knowledge("报名需要哪些材料", func(r): holder[0] = r)
	await process_frame

	var from_mock: bool = holder[0].get("answer", "").find("报名通常需要") != -1

	_append("cache_disabled", from_mock, {
		"captured_answer": holder[0].get("answer", ""),
		"expected_prefix": "报名通常需要",
		"cache_size": _ac._cache.size(),
	})


# ── Test 4: Timeout fallback ──
# Set timeout_live_ms=1 so the SceneTreeTimer fires on the next frame.
# With a TCP listener on :8788 that accepts but doesn't respond, the
# HTTP request connects and waits → timeout path fires.
# Without a listener, connection refused happens first → request_failed.
func _test_timeout_fallback() -> void:
	_reset()
	_ac.set_mode("live")
	_ac.set("_cache_enabled", false)
	_ac.set("_queue_max_concurrent", 10)
	_ac.set("_timeout_live_ms", 1)
	_ac.set("_queue_overflow_policy", "fallback_immediate")
	_ac.config["timeout_ms"] = 60000

	var holder: Array = [{}]
	_ac.ask_knowledge("报名需要哪些材料", func(r): holder[0] = r)

	# Live mode async — wait for callback
	var deadline := Time.get_ticks_msec() + 5000
	while holder[0].is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame

	var is_fb: bool = holder[0].get("_fallback", false) == true
	var reason: String = holder[0].get("_fallback_reason", "")
	var is_to: bool = reason == "timeout"

	_append("timeout_fallback", is_fb and is_to, {
		"is_fallback": is_fb,
		"fallback_reason": reason,
		"expected_reason": "timeout",
		"captured_empty": holder[0].is_empty(),
	})


# ── Test 5: Queue overflow ──
func _test_queue_overflow() -> void:
	_reset()
	_ac.set_mode("live")
	_ac.set("_cache_enabled", false)
	_ac.set("_queue_max_concurrent", 1)
	_ac.set("_queue_overflow_policy", "fallback_immediate")
	_ac.set("_timeout_live_ms", 500)
	_ac.config["timeout_ms"] = 60000

	# Use Array[Dictionary] wrapper for each response
	# NOTE: Avoid int-scoped counters — Godot 4.6 lambda capture bug
	# prevents int updates from propagating out of the lambda.
	# Instead, check Array contents directly.
	var responses: Array = [{}, {}]

	_ac.ask_knowledge("query_first", func(r):
		responses[0] = r
	)
	_ac.ask_knowledge("query_second", func(r):
		responses[1] = r
	)

	var deadline := Time.get_ticks_msec() + 10000
	while (responses[0].is_empty() or responses[1].is_empty()) and Time.get_ticks_msec() < deadline:
		await process_frame

	var q2_fb: bool = responses[1].get("_fallback", false) == true
	var q2_reason: String = responses[1].get("_fallback_reason", "")
	var q2_overflow: bool = q2_reason.find("queue") != -1

	_append("queue_overflow", not responses[1].is_empty() and q2_fb and q2_overflow, {
		"second": {
			"_fallback": q2_fb,
			"_fallback_reason": q2_reason,
			"answer": responses[1].get("answer", ""),
		},
		"first": {
			"_fallback": responses[0].get("_fallback", false),
			"_fallback_reason": responses[0].get("_fallback_reason", ""),
		},
	})


# ── Test 6: High-risk not cached ──
func _test_high_risk_not_cached() -> void:
	_reset()
	_ac.set_mode("mock")
	_ac.set("_cache_enabled", true)
	_ac._cache_ttl_ms = 300000

	var holder: Array = [{}]
	_ac.ask_knowledge("保证录取", func(r): holder[0] = r)
	await process_frame

	var handoff: bool = holder[0].get("handoff_required") == true
	var cache_empty: bool = _ac._cache.size() == 0

	_append("high_risk_not_cached", handoff and cache_empty, {
		"handoff_required": handoff,
		"handoff_reason": holder[0].get("handoff_reason", ""),
		"cache_size": _ac._cache.size(),
	})
