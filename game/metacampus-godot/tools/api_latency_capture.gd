extends SceneTree
## API Latency Capture — Headless latency benchmark via ApiClient trace points
##
## Drives api_client.gd in --headless mode, reads _bench_results after each
## request, and outputs CSV.
##
## Usage:
##   godot --headless --path <project> --script tools/api_latency_capture.gd -- --mode=mock --samples=30 --interval_ms=100
##
## Args:
##   --mode=mock|live|off    API mode (default: mock)
##   --samples=N             Number of requests (default: 30)
##   --interval_ms=N         Delay between requests in ms (default: 100)
##
## Output: stdout (CSV) + tools/perf_output/perf_api_{mode}_{samples}.csv

const API_CLIENT_PATH := "res://scripts/api_client.gd"
const OUT_DIR := "tools/perf_output"

var _mode := "mock"
var _samples := 30
var _interval_ms := 100
var _response_count := 0
var _api_client: Node = null
var _out_dir := OUT_DIR


func _init() -> void:
	_parse_args()
	_resolve_out_dir()

	print("[APILatency] Mode=%s Samples=%d Interval=%dms" % [_mode, _samples, _interval_ms])

	# Instantiate ApiClient and add to scene tree
	var ApiClientClass = load(API_CLIENT_PATH)
	_api_client = ApiClientClass.new()
	root.add_child(_api_client)
	await process_frame  # let _ready() run (loads config, mock data, HTTP setup)

	# Track response count so we know if ask_knowledge was sync or async
	_api_client.api_response_received.connect(_on_api_response)

	# Set request mode
	_api_client.set_mode(_mode)

	# Collect traces
	var traces := await _collect_traces()

	# Write CSV
	_write_csv(traces)

	print("[APILatency] Done — %d requests, %d traces" % [_samples, traces.size()])
	quit()


func _parse_args() -> void:
	var args := OS.get_cmdline_args()
	for i in range(args.size()):
		var a := args[i]
		if a.begins_with("--mode="):
			_mode = a.trim_prefix("--mode=")
		elif a.begins_with("--samples="):
			_samples = int(a.trim_prefix("--samples="))
		elif a.begins_with("--interval_ms="):
			_interval_ms = int(a.trim_prefix("--interval_ms="))
	_samples = clampi(_samples, 1, 10_000)
	_interval_ms = max(0, _interval_ms)


func _resolve_out_dir() -> void:
	var env_dir := OS.get_environment("PERF_OUTPUT_DIR")
	if env_dir != "":
		_out_dir = env_dir
	DirAccess.make_dir_recursive_absolute(_out_dir)


func _on_api_response(_result: Dictionary) -> void:
	_response_count += 1


func _collect_traces() -> Array[Dictionary]:
	var queries: Array[String] = [
		"报名需要哪些材料",
		"学校有什么特色课程",
		"招生政策是什么",
		"能不能保证录取",
		"学校地址在哪里",
		"学费是多少",
		"今天天气怎么样",
		"如何申请奖学金",
	]

	var traces: Array[Dictionary] = []

	for i in range(_samples):
		var query: String = queries[i % queries.size()]
		var prev_count := _response_count

		_api_client.ask_knowledge(query)

		# For async (live) mode, wait for the response signal
		if _response_count == prev_count:
			await _api_client.api_response_received

		# Read latest trace from bench_results
		var trace: Dictionary = {}
		if _api_client._bench_results.size() > 0:
			trace = _api_client._bench_results[-1].duplicate()

		traces.append(trace)

		if i > 0 and i % 10 == 0:
			print("[APILatency] %d/%d requests completed" % [i, _samples])

		# Inter-request delay
		if i < _samples - 1 and _interval_ms > 0:
			await create_timer(_interval_ms / 1000.0).timeout

	return traces


func _write_csv(traces: Array[Dictionary]) -> void:
	var header := "request_id,mode,timestamp,total_us,serialize_us,send_us,parse_us,callback_us,fallback_reason"
	var lines: Array[String] = [header]

	for trace in traces:
		var row := "%s,%s,%d,%d,%d,%d,%d,%d,%s" % [
			trace.get("request_id", ""),
			trace.get("mode", _mode),
			trace.get("timestamp", 0),
			trace.get("total_us", 0),
			trace.get("serialize_us", 0),
			trace.get("send_us", 0),
			trace.get("parse_us", 0),
			trace.get("callback_us", 0),
			trace.get("fallback_reason", ""),
		]
		lines.append(row)

	# Write to stdout
	print("\n=== API Latency CSV ===")
	for line in lines:
		print(line)
	print("=== END CSV ===\n")

	# Write to file
	var filename := "perf_api_%s_%d.csv" % [_mode, _samples]
	var filepath := _out_dir.path_join(filename)
	var file := FileAccess.open(filepath, FileAccess.WRITE)
	if file:
		for line in lines:
			file.store_line(line)
		file.close()
		print("[APILatency] Wrote %s" % filepath)
	else:
		push_error("[APILatency] Cannot write %s" % filepath)

	# Also compute and print a quick summary
	_compute_summary(traces)


func _compute_summary(traces: Array[Dictionary]) -> void:
	var total_values: Array[int] = []
	var success_count := 0
	var fallback_count := 0

	for t in traces:
		var total: int = int(t.get("total_us", 0))
		if total > 0:
			total_values.append(total)
		var fb: String = str(t.get("fallback_reason", ""))
		if fb != "" and fb != "null":
			fallback_count += 1
		else:
			success_count += 1

	if total_values.is_empty():
		return

	total_values.sort()
	var n := total_values.size()
	var min_us := total_values[0]
	var max_us := total_values[n - 1]
	var sum_us := 0
	for v in total_values:
		sum_us += v
	var avg_us := sum_us / n
	var p50 := total_values[int(n * 0.5)]
	var p95 := total_values[int(n * 0.95)]
	var p99 := total_values[int(n * 0.99)]

	print("[APILatency] Summary: %d traces (%d success, %d fallback)" % [n, success_count, fallback_count])
	print("[APILatency]   total_us: min=%d  p50=%d  p95=%d  p99=%d  max=%d  avg=%d" % [min_us, p50, p95, p99, max_us, avg_us])
	print("[APILatency]   %s %.2fms  p50=%.2fms  p95=%.2fms" % [_mode, avg_us / 1000.0, p50 / 1000.0, p95 / 1000.0])
