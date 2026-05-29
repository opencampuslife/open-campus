extends Node
## ApiClient — API Bridge mock/live 切换
## 默认 mock mode。live mode 接真实 /api/knowledge/ask。
## API 失败时自动 fallback mock，不破坏游戏运行。
##
## v2: 新增响应缓存 / 超时取消 / 请求队列 / Observability 计数器

## Bench mode flag: true enables per-request latency instrumentation.
## Controlled by env var PERF_BENCH=1 (like perf_capture.gd pattern).
## Production default: false — zero runtime overhead.
var BENCH_MODE: bool = false

func _init_bench_mode() -> void:
	BENCH_MODE = OS.get_environment("PERF_BENCH") == "1"

# 模式常量
const MODE_MOCK = "mock"
const MODE_LIVE = "live"
const MODE_OFF = "off"

# 配置
var config: Dictionary = {}
var mock_responses: Array = []
# HTTPRequest 节点在 live 请求中动态创建，无需持久节点

# ── 缓存状态 ──
var _cache: Dictionary = {}        # norm_query -> {response: Dictionary, timestamp: int, npc_id: String}
var _cache_order: Array[String] = []  # 插入顺序（用于驱逐最旧条目）
var _cache_enabled: bool = true
var _cache_ttl_ms: int = 300000
var _cache_max_entries: int = 100

# ── 队列状态 ──
var _request_queue: Array = []        # [{query: String, callback: Callable}]
var _active_requests: Dictionary = {} # req_id -> {query, callback, http_node, timeout_ref, bench}
var _live_request_count: int = 0
var _request_id_counter: int = 0
var _queue_max_concurrent: int = 2
var _queue_overflow_policy: String = "fallback_immediate"

# ── 超时 ──
var _timeout_live_ms: int = 10000

# ── Observability 计数器（仅 BENCH_MODE 累加） ──
var _bench_cache_hit: int = 0
var _bench_cache_miss: int = 0
var _bench_timeout_count: int = 0
var _bench_fallback_count: int = 0
var _bench_queue_depth_max: int = 0
var _bench_total_live_requests: int = 0

signal api_response_received(result: Dictionary)
signal api_fallback_triggered(reason: String)

func _ready() -> void:
	add_to_group("api_client")
	_init_bench_mode()
	_load_config()
	_load_mock_responses()
	# HTTPRequest 动态创建，无需 _setup_http

func _load_config() -> void:
	var file = FileAccess.open("res://data/api_config.json", FileAccess.READ)
	if not file:
		push_warning("[ApiClient] Cannot open api_config.json, using defaults")
		config = {"mode": MODE_MOCK, "base_url": "http://127.0.0.1:8787", "timeout_ms": 2500, "fallback_to_mock": true}
		_apply_config_defaults()
		return

	var json = JSON.new()
	if json.parse(file.get_as_text()) == OK:
		config = json.data
	else:
		push_error("[ApiClient] Failed to parse api_config.json")
		config = {"mode": MODE_MOCK, "fallback_to_mock": true}
	file.close()
	_apply_config()

func _apply_config_defaults() -> void:
	_cache_enabled = true
	_cache_ttl_ms = 300000
	_cache_max_entries = 100
	_timeout_live_ms = 10000
	_queue_max_concurrent = 2
	_queue_overflow_policy = "fallback_immediate"

func _apply_config() -> void:
	# 缓存设置
	var cache_cfg = config.get("cache", {})
	_cache_enabled = cache_cfg.get("enabled", true)
	_cache_ttl_ms = cache_cfg.get("ttl_ms", 300000)
	_cache_max_entries = cache_cfg.get("max_entries", 100)

	# 超时设置
	var timeout_cfg = config.get("timeout", {})
	_timeout_live_ms = timeout_cfg.get("live_ms", 10000)

	# 队列设置
	var queue_cfg = config.get("queue", {})
	_queue_max_concurrent = queue_cfg.get("max_concurrent_live", 2)
	_queue_overflow_policy = queue_cfg.get("overflow_policy", "fallback_immediate")

func _load_mock_responses() -> void:
	var file = FileAccess.open("res://data/mock_knowledge_responses.json", FileAccess.READ)
	if not file:
		push_warning("[ApiClient] Cannot open mock_knowledge_responses.json")
		return

	var json = JSON.new()
	if json.parse(file.get_as_text()) == OK:
		var data = json.data
		if data is Dictionary and data.has("responses"):
			mock_responses = data["responses"]
	file.close()

# ── Public API ──

func ask_knowledge(query: String, callback: Callable = Callable()) -> void:
	## 查询知识库。根据 mode 决定走 mock 还是 live。

	if BENCH_MODE:
		_bench_request_counter += 1
		_bench_pending = {
			"request_id": "bench_%d" % _bench_request_counter,
			"mode": config.get("mode", MODE_MOCK),
			"timestamp": int(Time.get_unix_time_from_system()),
			"total_start_us": Time.get_ticks_usec(),
		}

	# 高风险安全拦截（游戏层 guard，优先级最高）
	var high_risk = _check_high_risk(query)
	if high_risk:
		var response = _make_handoff_response(query, "high_risk_keyword")
		if callback.is_valid():
			callback.call(response)
		if BENCH_MODE:
			_bench_pending["fallback_reason"] = "high_risk_keyword"
			_bench_finalize()
		api_response_received.emit(response)
		return

	# ── 缓存查找 ──
	if _cache_enabled:
		var cached = _cache_get(query)
		if cached != null:
			if BENCH_MODE:
				_bench_pending["cache_hit"] = true
				_bench_pending["cache_miss"] = false
				_bench_cache_hit += 1
			if callback.is_valid():
				callback.call(cached)
			if BENCH_MODE:
				_bench_finalize()
			api_response_received.emit(cached)
			return
		elif BENCH_MODE:
			_bench_pending["cache_hit"] = false
			_bench_pending["cache_miss"] = true
			_bench_cache_miss += 1

	var mode = config.get("mode", MODE_MOCK)
	match mode:
		MODE_LIVE:
			_ask_knowledge_live(query, callback)
		MODE_MOCK:
			var response = _ask_knowledge_mock(query)
			if callback.is_valid():
				callback.call(response)
			if BENCH_MODE:
				_bench_finalize()
			api_response_received.emit(response)
		_:
			var response = _make_offline_response(query)
			if callback.is_valid():
				callback.call(response)
			if BENCH_MODE:
				_bench_finalize()
			api_response_received.emit(response)

func get_mode() -> String:
	return config.get("mode", MODE_MOCK)

func set_mode(mode: String) -> void:
	if mode in [MODE_MOCK, MODE_LIVE, MODE_OFF]:
		config["mode"] = mode

# ── Mock ──

func _ask_knowledge_mock(query: String) -> Dictionary:
	## 从本地 mock 数据匹配回答
	for r in mock_responses:
		var rq = r.get("query", "")
		if query.find(rq) != -1 or rq.find(query) != -1:
			return r.duplicate(true)

	# 返回默认 mock 回答
	for r in mock_responses:
		if r.get("query") == "default":
			return r.duplicate(true)

	return {
		"ok": true,
		"answer": "该问题需要进一步确认，已转人工处理。",
		"citations": [],
		"handoff_required": false
	}

# ── Live ──

func _ask_knowledge_live(query: String, callback: Callable) -> void:
	## 入口：检查队列容量后执行或执行溢出策略
	var queue_enabled = _queue_max_concurrent > 0
	if queue_enabled and _live_request_count >= _queue_max_concurrent:
		_apply_overflow_policy(query, callback)
		return
	_execute_live_request(query, callback)

func _execute_live_request(query: String, callback: Callable) -> void:
	## 创建 HTTPRequest 节点，发起真实 HTTP 请求到 LLM Bridge
	var req_id = _next_request_id()

	# 创建动态 HTTPRequest 节点
	var http_node = HTTPRequest.new()
	add_child(http_node)
	http_node.timeout = config.get("timeout_ms", 2500) / 1000.0

	if BENCH_MODE:
		_bench_total_live_requests += 1

	# 超时定时器
	var timeout_timer = null
	if _timeout_live_ms > 0:
		timeout_timer = get_tree().create_timer(_timeout_live_ms / 1000.0, false)
		timeout_timer.timeout.connect(_on_request_timeout.bind(req_id))

	# 存储请求上下文
	_active_requests[req_id] = {
		"query": query,
		"callback": callback if callback.is_valid() else Callable(),
		"http_node": http_node,
		"timeout_ref": timeout_timer,
	}
	_live_request_count += 1

	var base_url = config.get("base_url", "http://127.0.0.1:8788")
	var endpoint = config.get("endpoints", {}).get("knowledge_ask", "/chat")
	var url = base_url + endpoint

	var _bench_sstart := 0
	if BENCH_MODE:
		_bench_sstart = Time.get_ticks_usec()

	var body = JSON.stringify({"query": query, "session_id": "game_session"})

	if BENCH_MODE:
		_bench_pending["serialize_us"] = Time.get_ticks_usec() - _bench_sstart

	var headers = ["Content-Type: application/json"]

	var _bench_send_start := 0
	if BENCH_MODE:
		_bench_send_start = Time.get_ticks_usec()

	var err = http_node.request(url, headers, HTTPClient.METHOD_POST, body)

	if BENCH_MODE:
		_bench_pending["send_us"] = Time.get_ticks_usec() - _bench_send_start

	if err != OK:
		# 请求发起失败，立即 fallback
		var response = _fallback_mock(query, "request_failed: " + str(err))
		if callback.is_valid():
			callback.call(response)
		_cleanup_request(req_id, true)
		if BENCH_MODE:
			_bench_finalize()
		api_response_received.emit(response)
		return

	# 连接信号（带 req_id，区分多个并发请求）
	http_node.request_completed.connect(_on_request_completed.bind(req_id))

func _on_request_timeout(req_id: String) -> void:
	## 超时处理：取消 HTTP 请求，输出 fallback 响应
	if not _active_requests.has(req_id):
		return  # 请求已在超时前完成

	var req_data = _active_requests[req_id]
	if BENCH_MODE:
		_bench_timeout_count += 1

	# 取消待处理的 HTTP 请求
	if is_instance_valid(req_data.http_node):
		req_data.http_node.cancel_request()

	var response = _fallback_mock(req_data.query, "timeout")
	if req_data.callback.is_valid():
		req_data.callback.call(response)

	if BENCH_MODE:
		_bench_pending["fallback_reason"] = "timeout"
		_bench_finalize()

	_cleanup_request(req_id, true)
	api_fallback_triggered.emit("timeout")
	api_response_received.emit(response)

func _on_request_completed(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray, req_id: String = "") -> void:
	## HTTP 请求完成（或失败）回调
	if not _active_requests.has(req_id):
		return  # 已被超时处理，忽略

	var req_data = _active_requests[req_id]
	var query = req_data.query
	var callback: Callable = req_data.callback

	var _bench_pstart := 0
	var _bench_cbstart := 0
	if BENCH_MODE:
		_bench_pstart = Time.get_ticks_usec()

	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		if BENCH_MODE:
			_bench_pending["parse_us"] = 0
		var response = _fallback_mock(query, "http_%d_%d" % [result, response_code])
		if callback.is_valid():
			callback.call(response)
		_cleanup_request(req_id, true)
		if BENCH_MODE:
			_bench_finalize()
		api_response_received.emit(response)
		api_fallback_triggered.emit("http_%d_%d" % [result, response_code])
		return

	var json = JSON.new()
	var body_str = body.get_string_from_utf8()
	if json.parse(body_str) != OK:
		if BENCH_MODE:
			_bench_pending["parse_us"] = Time.get_ticks_usec() - _bench_pstart
		var response = _fallback_mock(query, "json_parse_error")
		if callback.is_valid():
			callback.call(response)
		_cleanup_request(req_id, true)
		if BENCH_MODE:
			_bench_finalize()
		api_response_received.emit(response)
		api_fallback_triggered.emit("json_parse_error")
		return

	var data = json.data
	if not data is Dictionary:
		if BENCH_MODE:
			_bench_pending["parse_us"] = Time.get_ticks_usec() - _bench_pstart
		var response = _fallback_mock(query, "unexpected_response_type")
		if callback.is_valid():
			callback.call(response)
		_cleanup_request(req_id, true)
		if BENCH_MODE:
			_bench_finalize()
		api_response_received.emit(response)
		api_fallback_triggered.emit("unexpected_response_type")
		return

	# Bridge 返回格式: {ok: bool, answer: str, ...}
	# 如果 ok=false，fallback mock
	if data.get("ok") != true:
		if BENCH_MODE:
			_bench_pending["parse_us"] = Time.get_ticks_usec() - _bench_pstart
		var response = _fallback_mock(query, "llm_bridge_error: " + str(data.get("error", "unknown")))
		if callback.is_valid():
			callback.call(response)
		_cleanup_request(req_id, true)
		if BENCH_MODE:
			_bench_finalize()
		api_response_received.emit(response)
		api_fallback_triggered.emit("llm_bridge_error")
		return

	# 检查高风险内容
	var answer = data.get("answer", "")
	if _check_high_risk(answer):
		if BENCH_MODE:
			_bench_pending["parse_us"] = Time.get_ticks_usec() - _bench_pstart
			_bench_pending["fallback_reason"] = "live_api_high_risk_content"
		var response = _make_handoff_response(query, "live_api_high_risk_content")
		if callback.is_valid():
			callback.call(response)
		_cleanup_request(req_id, true)
		if BENCH_MODE:
			_bench_pending["callback_us"] = 0
			_bench_finalize()
		api_response_received.emit(response)
		api_fallback_triggered.emit("live_api_high_risk_content")
		return

	var response = {
		"ok": true,
		"answer": answer,
		"citations": [],
		"handoff_required": answer.find("转人工") != -1 or answer.find("人工处理") != -1,
		"_source": "deepseek_live",
		"_model": data.get("model", "")
	}

	# ── 成功响应：写入缓存（只缓存成功且非高风险） ──
	if _cache_enabled:
		_cache_set(query, response)

	if BENCH_MODE:
		_bench_pending["parse_us"] = Time.get_ticks_usec() - _bench_pstart
		_bench_cbstart = Time.get_ticks_usec()

	if callback.is_valid():
		callback.call(response)

	_cleanup_request(req_id, true)

	if BENCH_MODE:
		_bench_pending["callback_us"] = Time.get_ticks_usec() - _bench_cbstart
		_bench_finalize()

	api_response_received.emit(response)

# ── 请求队列 ──

func _process_queue() -> void:
	## 请求完成后检查队列，处理等待中的请求
	if _request_queue.is_empty():
		return
	if _queue_max_concurrent <= 0:
		return  # 队列禁用
	while _request_queue.size() > 0 and _live_request_count < _queue_max_concurrent:
		var next = _request_queue.pop_front()
		_execute_live_request(next.query, next.callback)

func _apply_overflow_policy(query: String, callback: Callable) -> void:
	## 并发已达上限时执行溢出策略
	match _queue_overflow_policy:
		"fallback_immediate":
			var response = _fallback_mock(query, "queue_overflow")
			if callback.is_valid():
				callback.call(response)
			if BENCH_MODE:
				_bench_finalize()
			api_response_received.emit(response)
		"reject_new":
			var response = {
				"ok": false,
				"answer": "系统繁忙，请稍后重试。",
				"citations": [],
				"handoff_required": false,
				"_error": "queue_overflow_reject"
			}
			if callback.is_valid():
				callback.call(response)
			if BENCH_MODE:
				_bench_finalize()
			api_response_received.emit(response)
		"reject_oldest":
			# 移除队列中最旧的待处理请求
			if _request_queue.size() > 0:
				var oldest = _request_queue.pop_front()
				var reject_response = {
					"ok": false,
					"answer": "系统繁忙，请稍后重试。",
					"citations": [],
					"handoff_required": false,
					"_error": "queue_overflow_reject_oldest"
				}
				if oldest.callback.is_valid():
					oldest.callback.call(reject_response)
				api_response_received.emit(reject_response)
			# 将新请求加入队列
			_request_queue.append({"query": query, "callback": callback})
			if BENCH_MODE:
				_bench_queue_depth_max = max(_bench_queue_depth_max, _request_queue.size())

func _cleanup_request(req_id: String, process_queue: bool = true) -> void:
	## 清理请求上下文：移除活跃请求、释放 HTTP 节点、递减计数
	if not _active_requests.has(req_id):
		return
	var req_data = _active_requests[req_id]
	# 释放 HTTPRequest 节点（queue_free 自动处理信号断开）
	if req_data.has("http_node") and is_instance_valid(req_data.http_node):
		req_data.http_node.queue_free()
	_active_requests.erase(req_id)
	_live_request_count = max(0, _live_request_count - 1)
	# 处理队列
	if process_queue:
		_process_queue()

func _next_request_id() -> String:
	_request_id_counter += 1
	return "req_%d" % _request_id_counter

# ── 缓存 ──

func _cache_key(query: String) -> String:
	## 生成规范化缓存键：trim + lowercase
	return query.strip_edges().to_lower()

func _cache_get(query: String):
	## 查找缓存。过期条目会自动忽略并从缓存中移除。
	var key = _cache_key(query)
	if not _cache.has(key):
		return null

	var entry = _cache[key]
	var now = Time.get_unix_time_from_system() * 1000
	if now - entry.timestamp > _cache_ttl_ms:
		# TTL 过期，驱逐
		_cache.erase(key)
		var idx = _cache_order.find(key)
		if idx != -1:
			_cache_order.remove_at(idx)
		return null

	# 命中：将键移到末尾（LRU）
	var order_idx = _cache_order.find(key)
	if order_idx != -1:
		_cache_order.remove_at(order_idx)
	_cache_order.append(key)

	return entry.response.duplicate(true)

func _cache_set(query: String, response: Dictionary) -> void:
	## 写入缓存
	var key = _cache_key(query)
	var now = Time.get_unix_time_from_system() * 1000

	# 如果已存在，更新
	if _cache.has(key):
		_cache[key] = {
			"response": response.duplicate(true),
			"timestamp": now,
		}
		# 移到末尾（LRU）
		var order_idx = _cache_order.find(key)
		if order_idx != -1:
			_cache_order.remove_at(order_idx)
		_cache_order.append(key)
		return

	# 驱逐最旧条目
	if _cache.size() >= _cache_max_entries:
		_evict_oldest()

	_cache[key] = {
		"response": response.duplicate(true),
		"timestamp": now,
	}
	_cache_order.append(key)

func _evict_oldest() -> void:
	## 驱逐最旧缓存条目
	if _cache_order.size() == 0:
		return
	var oldest_key = _cache_order.pop_front()
	_cache.erase(oldest_key)

# ── Fallback ──

func _fallback_mock(query: String, reason: String) -> Dictionary:
	## API 失败时 fallback mock
	api_fallback_triggered.emit(reason)

	if BENCH_MODE:
		_bench_pending["fallback_reason"] = reason
		_bench_fallback_count += 1

	if config.get("fallback_to_mock", true):
		var response = _ask_knowledge_mock(query)
		response["_fallback"] = true
		response["_fallback_reason"] = reason
		return response

	return {
		"ok": false,
		"answer": "AI 工具暂不可用，请稍后重试。",
		"citations": [],
		"handoff_required": false,
		"_fallback": true,
		"_fallback_reason": reason
	}

# ── Safety ──

func _check_high_risk(text: String) -> bool:
	## 检查是否包含高风险关键词
	var keywords = config.get("high_risk_keywords", [])
	for kw in keywords:
		if text.find(kw) != -1:
			return true
	return false

func _make_handoff_response(query: String, reason: String) -> Dictionary:
	return {
		"ok": true,
		"answer": "该问题涉及录取承诺，系统无法回答。已转人工招生老师处理。",
		"citations": [],
		"handoff_required": true,
		"handoff_reason": reason
	}

func _make_offline_response(query: String) -> Dictionary:
	return {
		"ok": false,
		"answer": "AI 工具暂不可用（API 已关闭）。",
		"citations": [],
		"handoff_required": false
	}

# ── Debug ──

func get_config() -> Dictionary:
	return config.duplicate(true)

func get_mock_responses() -> Array:
	return mock_responses.duplicate(true)

func get_bench_counters() -> Dictionary:
	## 返回 Observability 计数器（用于外部采集）
	return {
		"cache_hit": _bench_cache_hit,
		"cache_miss": _bench_cache_miss,
		"timeout_count": _bench_timeout_count,
		"fallback_count": _bench_fallback_count,
		"queue_depth_max": _bench_queue_depth_max,
		"live_request_count": _live_request_count,
		"total_live_requests": _bench_total_live_requests,
	}

func get_cache_info() -> Dictionary:
	## 返回缓存状态（用于诊断）
	return {
		"enabled": _cache_enabled,
		"size": _cache.size(),
		"max_entries": _cache_max_entries,
		"ttl_ms": _cache_ttl_ms,
	}

# ── Bench (BENCH_MODE only) ──

var _bench_request_counter: int = 0
var _bench_pending: Dictionary = {}
var _bench_results: Array[Dictionary] = []

func _bench_finalize() -> void:
	## Finalize and log the current bench trace. Called before signal emission
	## so listeners (e.g. api_latency_capture.gd) see the trace immediately.
	if not BENCH_MODE or _bench_pending.is_empty():
		return
	_bench_pending["total_us"] = Time.get_ticks_usec() - _bench_pending.get("total_start_us", Time.get_ticks_usec())
	_bench_pending.erase("total_start_us")
	if not _bench_pending.has("serialize_us"): _bench_pending["serialize_us"] = 0
	if not _bench_pending.has("send_us"): _bench_pending["send_us"] = 0
	if not _bench_pending.has("parse_us"): _bench_pending["parse_us"] = 0
	if not _bench_pending.has("callback_us"): _bench_pending["callback_us"] = 0
	if not _bench_pending.has("fallback_reason"): _bench_pending["fallback_reason"] = ""
	if not _bench_pending.has("cache_hit"): _bench_pending["cache_hit"] = false
	if not _bench_pending.has("cache_miss"): _bench_pending["cache_miss"] = false
	print("[Bench] ", JSON.stringify(_bench_pending))
	_bench_results.append(_bench_pending.duplicate())
	_bench_pending.clear()
