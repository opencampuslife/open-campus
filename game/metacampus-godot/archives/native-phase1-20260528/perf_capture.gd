extends SceneTree
## Perf Capture — Headless performance data collector
## Usage: godot --headless --path <project> --script tools/perf_capture.gd -- --npc=100
## Outputs: $PERF_OUTPUT_DIR/perf_npc_{count}.csv + perf_summary_{count}.json

const SAMPLE_DURATION_SEC := 35.0
const WARMUP_SEC := 3.0

var npc_count := 5
var sample_count := 0
var csv_lines: Array[String] = []
var json_timings: Dictionary = {}
var summary: Dictionary = {}
var _out_dir := "/tmp/metacampus_perf"

func _init() -> void:
	_parse_args()
	_resolve_out_dir()
	print("[PerfCapture] Starting with NPC count: %d" % npc_count)
	
	# Measure JSON load times
	_measure_json_load_times()
	
	# Load main scene and spawn extra NPCs
	_setup_scene()
	
	# Warmup
	print("[PerfCapture] Warming up for %ds..." % WARMUP_SEC)
	await create_timer(WARMUP_SEC).timeout
	print("[PerfCapture] Capturing for %ds..." % SAMPLE_DURATION_SEC)
	
	# Capture loop
	await _capture_loop()
	
	# Write outputs
	_write_csv()
	_write_summary()
	
	print("[PerfCapture] Done")
	quit()


func _parse_args() -> void:
	var args := OS.get_cmdline_args()
	for i in range(args.size()):
		var a := args[i]
		if a.begins_with("--npc="):
			npc_count = int(a.trim_prefix("--npc="))
		elif a == "--npc" and i + 1 < args.size():
			npc_count = int(args[i + 1])
	npc_count = max(0, min(npc_count, 1000))


func _resolve_out_dir() -> void:
	var env_dir := OS.get_environment("PERF_OUTPUT_DIR")
	if env_dir != "":
		_out_dir = env_dir
	DirAccess.make_dir_recursive_absolute(_out_dir)


func _setup_scene() -> void:
	var main_packed = load("res://scenes/Main.tscn")
	if main_packed == null:
		push_error("[PerfCapture] Cannot load Main.tscn")
		quit(1)
	
	var main = main_packed.instantiate()
	root.add_child(main)
	await process_frame
	
	var campus_map = main.get_node_or_null("CampusMap")
	var npcs_container = null
	if campus_map != null:
		npcs_container = campus_map.get_node_or_null("NPCs")
	
	if npcs_container == null:
		push_error("[PerfCapture] Cannot find NPCs container")
		quit(1)
	
	# Spawn extra NPCs beyond built-in ones
	var builtin_count = npcs_container.get_child_count()
	var extra_count = max(0, npc_count - builtin_count)
	
	if extra_count > 0:
		var npc_template = load("res://scenes/NPC.tscn")
		if npc_template == null:
			push_error("[PerfCapture] Cannot load NPC.tscn")
			quit(1)
		
		print("[PerfCapture] Spawning %d extra NPCs (target: %d)" % [extra_count, npc_count])
		
		var cols = int(ceil(sqrt(float(extra_count))))
		var spacing_x := 60.0
		var spacing_y := 60.0
		
		for i in range(extra_count):
			var npc = npc_template.instantiate()
			npc.position = Vector2(100 + (i % cols) * spacing_x, 80 + (i / cols) * spacing_y)
			npc.npc_id = "perf_npc_%d" % i
			npc.npc_name = "NPC_%d" % i
			npcs_container.add_child(npc)
		
		await process_frame
	
	print("[PerfCapture] Total NPCs: %d" % npcs_container.get_child_count())


func _capture_loop() -> void:
	var start_usec = Time.get_ticks_usec()
	var duration_usec = int(SAMPLE_DURATION_SEC * 1_000_000)
	var frame_index := 0
	
	csv_lines.append("frame_idx,time_elapsed_ms,fps,process_time_us,physics_time_us,node_count,npc_count,memory_bytes")
	
	while true:
		await process_frame
		
		var elapsed = Time.get_ticks_usec() - start_usec
		if elapsed > duration_usec:
			break
		
		var fps = Performance.get_monitor(Performance.TIME_FPS)
		var process_ms = Performance.get_monitor(Performance.TIME_PROCESS)
		var physics_ms = Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)
		var node_count = int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
		var memory_bytes = int(Performance.get_monitor(Performance.MEMORY_STATIC))
		
		csv_lines.append("%d,%d,%.1f,%.1f,%.1f,%d,%d,%d" % [
			frame_index,
			int(elapsed / 1000),
			fps,
			process_ms * 1000.0,
			physics_ms * 1000.0,
			node_count,
			npc_count,
			memory_bytes
		])
		frame_index += 1
	
	sample_count = frame_index
	print("[PerfCapture] Captured %d frames" % sample_count)
	_calculate_summary()


func _calculate_summary() -> void:
	var process_times: Array[float] = []
	var physics_times: Array[float] = []
	var fps_values: Array[float] = []
	
	for i in range(1, csv_lines.size()):
		var parts = csv_lines[i].split(",")
		if parts.size() >= 8:
			fps_values.append(float(parts[2]))
			process_times.append(float(parts[3]))
			physics_times.append(float(parts[4]))
	
	process_times.sort()
	physics_times.sort()
	fps_values.sort()
	
	var avg_fps = _avg(fps_values)
	var min_fps = fps_values[0] if fps_values.size() > 0 else 0.0
	var p50_process = _percentile(process_times, 50)
	var p95_process = _percentile(process_times, 95)
	var p99_process = _percentile(process_times, 99)
	var p50_physics = _percentile(physics_times, 50)
	var p95_physics = _percentile(physics_times, 95)
	var p99_physics = _percentile(physics_times, 99)
	
	var median_process = p50_process
	var spike_count := 0
	for t in process_times:
		if t > median_process * 3.0 and t > 5000.0:
			spike_count += 1
	var spike_freq = float(spike_count) / float(max(1, sample_count))
	
	var first_mem := 0
	var last_mem := 0
	if csv_lines.size() > 1:
		var first_parts = csv_lines[1].split(",")
		var last_parts = csv_lines[csv_lines.size() - 1].split(",")
		if first_parts.size() >= 8:
			first_mem = int(first_parts[7])
		if last_parts.size() >= 8:
			last_mem = int(last_parts[7])
	
	summary = {
		"npc_count": npc_count,
		"samples": sample_count,
		"fps_avg": snapped(avg_fps, 0.01),
		"fps_min": snapped(min_fps, 0.01),
		"process_time_us_p50": snapped(p50_process, 0.01),
		"process_time_us_p95": snapped(p95_process, 0.01),
		"process_time_us_p99": snapped(p99_process, 0.01),
		"physics_time_us_p50": snapped(p50_physics, 0.01),
		"physics_time_us_p95": snapped(p95_physics, 0.01),
		"physics_time_us_p99": snapped(p99_physics, 0.01),
		"spike_count": spike_count,
		"spike_frequency": snapped(spike_freq, 0.0001),
		"memory_start_bytes": first_mem,
		"memory_end_bytes": last_mem,
		"memory_delta_bytes": last_mem - first_mem,
		"json_timings": json_timings
	}


func _measure_json_load_times() -> void:
	print("[PerfCapture] Measuring JSON load times...")
	
	var files := ["res://data/dialogues.json", "res://data/quests.json", "res://data/npcs.json", "res://data/locations.json", "res://data/api_config.json"]
	var labels := ["dialogues", "quests", "npcs", "locations", "api_config"]
	
	for i in range(files.size()):
		var path = files[i]
		var label = labels[i]
		
		# Cold load
		var t0 = Time.get_ticks_usec()
		var file = FileAccess.open(path, FileAccess.READ)
		if file:
			var _content = file.get_as_text()
			file.close()
		var cold_usec = Time.get_ticks_usec() - t0
		
		# Parse JSON
		t0 = Time.get_ticks_usec()
		if FileAccess.file_exists(path):
			var f2 = FileAccess.open(path, FileAccess.READ)
			if f2:
				var raw = f2.get_as_text()
				f2.close()
				var json = JSON.new()
				json.parse(raw)
		var parse_usec = Time.get_ticks_usec() - t0
		
		# Hot load (OS cached)
		t0 = Time.get_ticks_usec()
		var file3 = FileAccess.open(path, FileAccess.READ)
		if file3:
			var _c2 = file3.get_as_text()
			file3.close()
		var hot_usec = Time.get_ticks_usec() - t0
		
		json_timings[label] = {
			"cold_load_us": cold_usec,
			"parse_us": parse_usec,
			"hot_load_us": hot_usec
		}
		print("  %s: cold=%dus parse=%dus hot=%dus" % [label, cold_usec, parse_usec, hot_usec])


func _write_csv() -> void:
	var path = _out_dir.path_join("perf_npc_%d.csv" % npc_count)
	var file = FileAccess.open(path, FileAccess.WRITE)
	if file:
		for line in csv_lines:
			file.store_line(line)
		file.close()
		print("[PerfCapture] Wrote %s" % path)
	
	# Also write JSON load timings
	var json_path = _out_dir.path_join("perf_json_load_%d.csv" % npc_count)
	var jf = FileAccess.open(json_path, FileAccess.WRITE)
	if jf:
		jf.store_line("file,stage,time_us")
		for label in json_timings:
			var t = json_timings[label]
			if t is Dictionary:
				jf.store_line("%s,cold,%d" % [label, t.get("cold_load_us", 0)])
				jf.store_line("%s,parse,%d" % [label, t.get("parse_us", 0)])
				jf.store_line("%s,hot,%d" % [label, t.get("hot_load_us", 0)])
		jf.close()


func _write_summary() -> void:
	var json_out = JSON.new()
	var json_str = json_out.stringify(summary, "  ", false)
	
	var path = _out_dir.path_join("perf_summary_%d.json" % npc_count)
	var file = FileAccess.open(path, FileAccess.WRITE)
	if file:
		file.store_string(json_str)
		file.close()
		print("[PerfCapture] Wrote %s" % path)
	
	print("\n=== Perf Summary for %d NPCs ===" % npc_count)
	print(json_str)


func _avg(arr: Array[float]) -> float:
	if arr.is_empty():
		return 0.0
	var s := 0.0
	for v in arr:
		s += v
	return s / float(arr.size())


func _percentile(sorted_arr: Array[float], pct: float) -> float:
	if sorted_arr.is_empty():
		return 0.0
	var idx := int(ceil(pct / 100.0 * sorted_arr.size()) - 1)
	idx = clampi(idx, 0, sorted_arr.size() - 1)
	return sorted_arr[idx]
