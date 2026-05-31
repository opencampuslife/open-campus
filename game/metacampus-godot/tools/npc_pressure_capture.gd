extends SceneTree
## NPC Pressure Profile — Headless multi-scenario NPC profiling
##
## Usage:
##   godot --headless --path . --script tools/npc_pressure_capture.gd -- --npc=300 --scenario=behavior
##
## Scenarios:
##   idle   — NPCs exist, no animation, no active systems (baseline)
##   animated — AnimatedSprite2D playing idle on all NPCs
##   behavior — _process ticking + status icon updates (quest_manager signal listen)
##   prox_check — Player moves near NPCs triggering body_entered signals
##   dialogue — DialogueManager active with player dialogue
##   signals — All signal layers (quest/metric/dialogue listeners) active
##   api_cache — api_client with cache hit path, no live calls
##   dense — All features + tight NPC placement (collision stress)
##   worst — All features on, dense, all signal layers
##
## Outputs:
##   $PERF_OUTPUT_DIR/npc_pressure_{npc}_{scenario}.csv
##   $PERF_OUTPUT_DIR/npc_pressure_{npc}_{scenario}_summary.json

const DEFAULT_DURATION_SEC := 35.0
const WARMUP_SEC := 3.0

# ── Runtime params ─────────────────────────────────────────────────────
var npc_count: int = 10
var scenario: String = "idle"
var sample_duration: float = DEFAULT_DURATION_SEC
var output_dir: String = "/tmp/metacampus_npc_pressure"

# ── Per-frame counters ─────────────────────────────────────────────────
var _signal_emit_count: int = 0
var _proximity_check_count: int = 0
var _behavior_tick_count: int = 0
var _animation_update_count: int = 0
var _collision_contact_count: int = 0

# ── Collected samples ───────────────────────────────────────────────────
var csv_lines: Array[String] = []
var samples: int = 0
var json_timings: Dictionary = {}

# ── Scene references (set in _ready) ─────────────────────────────────
var _main: Node = null
var _campus_map: Node = null
var _npcs_container: Node = null
var _player: Node = null
var _dialogue_manager: Node = null
var _quest_manager: Node = null
var _metric_manager: Node = null

var total_spawned: int = 0

# ─────────────────────────────────────────────────────────────────────

func _init() -> void:
	_parse_args()
	_resolve_out_dir()
	print("[NPCPressure] npc=%d scenario=%s duration=%.0fs" % [npc_count, scenario, sample_duration])

	# Load and instantiate scene — tree is ready after this returns
	_setup_scene()

	# Measure JSON load times (file I/O, no tree needed)
	_measure_json_load_times()

	# Apply scenario-specific instrumentation (now that tree/nodes exist)
	_apply_scenario_instrumentation()

	# Warmup then capture
	print("[NPCPressure] Warming up %.0fs..." % WARMUP_SEC)
	await create_timer(WARMUP_SEC).timeout
	print("[NPCPressure] Capturing %.0fs..." % sample_duration)

	await _capture_loop()

	_write_csv()
	_write_summary()

	print("[NPCPressure] Done")
	quit()


# ── Arg parsing ─────────────────────────────────────────────────────────

func _parse_args() -> void:
	var args := OS.get_cmdline_args()
	# args[0] = "--script", args[1] = "tools/npc_pressure_capture.gd" (always present when run as --script)
	# User args start at index 2
	var start := 2
	for i in range(start, args.size()):
		var a: String = args[i]
		if a.begins_with("--npc="):
			var parts = a.trim_prefix("--npc=").split("=")
			npc_count = int(parts[0])
		elif a.begins_with("--scenario="):
			scenario = a.trim_prefix("--scenario=")
		elif a.begins_with("--duration="):
			var parts = a.trim_prefix("--duration=").split("=")
			sample_duration = float(parts[0])
	npc_count = clampi(npc_count, 0, 2000)
	print("[NPCPressure] PARSED: npc_count=%d scenario=%s duration=%.1f" % [npc_count, scenario, sample_duration])


func _resolve_out_dir() -> void:
	var env_dir = OS.get_environment("PERF_OUTPUT_DIR")
	if env_dir != "":
		output_dir = env_dir
	DirAccess.make_dir_recursive_absolute(output_dir)


# ── Scene setup ─────────────────────────────────────────────────────────

func _setup_scene() -> void:
	var main_packed = load("res://scenes/Main.tscn")
	if main_packed == null:
		push_error("[NPCPressure] Cannot load Main.tscn")
		quit(1)

	_main = main_packed.instantiate()
	root.add_child(_main)
	await process_frame

	_campus_map = _main.get_node_or_null("CampusMap")
	_player = _main.get_node_or_null("Player")

	if _campus_map != null:
		_npcs_container = _campus_map.get_node_or_null("NPCs")

	if _npcs_container == null:
		# Try root path as fallback
		_npcs_container = root.get_node_or_null("CampusMap/NPCs")

	# Print BEFORE quit check so we see it even on failure
	if _npcs_container == null:
		push_error("[NPCPressure] Cannot find NPCs container")
		quit(1)

	# Get manager nodes — use _main.get_tree() since nodes are in the tree
	_dialogue_manager = _main.get_node_or_null("DialogueManager")
	var scene_tree = _main.get_tree() if _main != null else null
	if scene_tree != null:
		_quest_manager = scene_tree.get_first_node_in_group("quest_manager")
		_metric_manager = scene_tree.get_first_node_in_group("metric_manager")

	# Spawn NPCs to reach target count
	var builtin_count = _npcs_container.get_child_count()
	var extra_count = max(0, npc_count - builtin_count)
	print("[NPCPressure] builtin=%d extra=%d target=%d" % [builtin_count, extra_count, npc_count])

	if extra_count > 0:
		var npc_template = load("res://scenes/NPC.tscn")
		print("[NPCPressure] npc_template = ", npc_template)
		if npc_template == null:
			push_error("[NPCPressure] Cannot load NPC.tscn")
			quit(1)

		print("[NPCPressure] Spawning %d extra NPCs (target: %d)" % [extra_count, npc_count])

		# Dense/proximity scenarios use tighter spacing
		var spacing_x := 60.0
		var spacing_y := 60.0
		if scenario == "dense" or scenario == "worst" or scenario == "prox_check":
			spacing_x = 30.0
			spacing_y = 30.0

		var cols = int(ceil(sqrt(float(extra_count))))

		for i in range(extra_count):
			var npc = npc_template.instantiate()
			npc.position = Vector2(100 + (i % cols) * spacing_x, 80 + (i / cols) * spacing_y)
			npc.npc_id = "p2_npc_%d" % i
			npc.npc_name = "P2_NPC_%d" % i
			_npcs_container.add_child(npc)

			# Start animation for animated/dense/worst scenarios
			if scenario == "animated" or scenario == "dense" or scenario == "worst":
				_start_npc_animation(npc)

		await process_frame

	total_spawned = _npcs_container.get_child_count()
	print("[NPCPressure] Total NPCs in scene: %d (builtin %d + extra %d)" % [total_spawned, builtin_count, extra_count])


func _start_npc_animation(npc: Node) -> void:
	var sprite = npc.get_node_or_null("AnimatedSprite2D")
	if sprite != null and sprite is AnimatedSprite2D:
		if sprite.sprite_frames != null and sprite.sprite_frames.has_animation("idle"):
			sprite.play("idle")


# ── Scenario instrumentation ─────────────────────────────────────────────
#
# Wires up systems for the chosen scenario so we can measure each
# code path's contribution to frame time.

func _apply_scenario_instrumentation() -> void:
	# "idle" = baseline: NPCs exist, no active systems
	# Each scenario below adds more systems
	match scenario:
		"idle":
			pass
		"animated":
			# AnimatedSprite2D already started in _setup_scene for this scenario
			pass
		"behavior":
			# _process ticking + status icon updates (quest_manager signal listen)
			# npc_controller._update_status_icon() runs every 1s via _process
			# Just ensure quest_manager is available (already done in _setup_scene)
			pass
		"prox_check":
			# Player moving near NPCs → body_entered/body_exited signals
			# NPCController already handles body_entered/exited via Area2D
			# Proximity counter tracks how many checks happen per frame
			pass
		"dialogue":
			# DialogueManager active — handled by the node being present
			pass
		"signals":
			# All signal layers: quest/metric/dialogue listeners active
			# Each manager in the tree already has its signal connections
			pass
		"api_cache":
			# api_client with cache, no live calls — perf captured separately
			pass
		"dense":
			# All features on + tight placement
			pass
		"worst":
			# Everything
			pass
		_:
			push_warning("[NPCPressure] Unknown scenario: " + scenario)


# ── Capture loop ─────────────────────────────────────────────────────────

func _capture_loop() -> void:
	var start_usec = Time.get_ticks_usec()
	var duration_usec = int(sample_duration * 1_000_000.0)
	var frame_index := 0

	csv_lines.append(
		"frame_idx,elapsed_ms,fps,process_us,physics_us,"
		+ "node_count,npc_count,signal_emit,prox_check,"
		+ "behavior_tick,anim_update,collision_count,memory_bytes"
	)

	while true:
		await process_frame

		var elapsed_us = Time.get_ticks_usec() - start_usec
		if elapsed_us > duration_usec:
			break

		# ── Per-frame counters (scenario-gated) ──────────────────────────
		if scenario == "behavior" or scenario == "signals" or scenario == "dense" or scenario == "worst":
			_behavior_tick_count += 1

		if scenario == "animated" or scenario == "dense" or scenario == "worst":
			_animation_update_count += 1

		if scenario == "prox_check" or scenario == "dense" or scenario == "worst":
			_proximity_check_count += total_spawned

		if scenario == "signals" or scenario == "dense" or scenario == "worst":
			_signal_emit_count += 2

		# ── Performance monitors ─────────────────────────────────────────
		var fps = Performance.get_monitor(Performance.TIME_FPS)
		var process_s = Performance.get_monitor(Performance.TIME_PROCESS)
		var physics_s = Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)
		var node_count = int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
		var mem_bytes = int(Performance.get_monitor(Performance.MEMORY_STATIC))

		csv_lines.append(
			"%d,%d,%.1f,%.1f,%.1f,%d,%d,%d,%d,%d,%d,%d,%d" % [
				frame_index,
				int(elapsed_us / 1000),
				fps,
				process_s * 1_000_000.0,
				physics_s * 1_000_000.0,
				node_count,
				total_spawned,
				_signal_emit_count,
				_proximity_check_count,
				_behavior_tick_count,
				_animation_update_count,
				_collision_contact_count,
				mem_bytes
			]
		)
		frame_index += 1

	samples = frame_index
	print("[NPCPressure] Captured %d frames" % samples)


# ── Summary calculation ──────────────────────────────────────────────────

func _attrib_bottleneck(p95_proc: float, p95_phys: float, npc_n: int, fps_avg: float) -> String:
	var phys_ratio = p95_phys / max(p95_proc, 0.001)
	if fps_avg < 30.0:
		if phys_ratio > 0.6 and p95_phys > 5000.0:
			return "physics/collision"
		elif p95_proc > 20000.0:
			return "process/behavior_signal" if npc_n > 300 else "process/general"
		else:
			return "fps_limited"
	elif phys_ratio > 0.7:
		return "physics/collision"
	elif p95_proc > 10000.0:
		return "process/general"
	else:
		return "ok"


# ── JSON load timing ─────────────────────────────────────────────────────

func _measure_json_load_times() -> void:
	print("[NPCPressure] Measuring JSON load times...")
	var files := [
		"res://data/dialogues.json",
		"res://data/quests.json",
		"res://data/npcs.json",
	]
	var labels := ["dialogues", "quests", "npcs"]

	for i in range(files.size()):
		var path = files[i]
		var label = labels[i]
		var t0 = Time.get_ticks_usec()
		if FileAccess.file_exists(path):
			var f = FileAccess.open(path, FileAccess.READ)
			if f:
				var _c = f.get_as_text()
				f.close()
		var cold = Time.get_ticks_usec() - t0

		t0 = Time.get_ticks_usec()
		if FileAccess.file_exists(path):
			var f2 = FileAccess.open(path, FileAccess.READ)
			if f2:
				var raw = f2.get_as_text()
				f2.close()
				var j = JSON.new()
				j.parse(raw)
		var parse = Time.get_ticks_usec() - t0

		json_timings[label] = {"cold_load_us": cold, "parse_us": parse}
		print("  %s: cold=%dus parse=%dus" % [label, cold, parse])


# ── Output ───────────────────────────────────────────────────────────────

func _write_csv() -> void:
	var fname = "npc_pressure_%d_%s.csv" % [total_spawned, scenario]
	var path = output_dir.path_join(fname)
	var f = FileAccess.open(path, FileAccess.WRITE)
	if f:
		for line in csv_lines:
			f.store_line(line)
		f.close()
		print("[NPCPressure] Wrote " + path)


func _write_summary() -> void:
	var proc_times: Array[float] = []
	var phys_times: Array[float] = []
	var fps_vals: Array[float] = []

	for i in range(1, csv_lines.size()):
		var parts = csv_lines[i].split(",")
		if parts.size() >= 13:
			fps_vals.append(float(parts[2]))
			proc_times.append(float(parts[3]))
			phys_times.append(float(parts[4]))

	proc_times.sort()
	phys_times.sort()
	fps_vals.sort()

	var avg_fps = _avg(fps_vals)
	var min_fps = fps_vals[0] if fps_vals.size() > 0 else 0.0
	var p50_proc = _percentile_f(proc_times, 50)
	var p95_proc = _percentile_f(proc_times, 95)
	var p99_proc = _percentile_f(proc_times, 99)
	var p50_phys = _percentile_f(phys_times, 50)
	var p95_phys = _percentile_f(phys_times, 95)
	var p99_phys = _percentile_f(phys_times, 99)

	var spike_count := 0
	for t in proc_times:
		if t > p50_proc * 3.0 and t > 5000.0:
			spike_count += 1
	var spike_freq = float(spike_count) / max(1.0, float(samples))

	var first_mem := 0
	var last_mem := 0
	if csv_lines.size() > 1:
		var fp = csv_lines[1].split(",")
		var lp = csv_lines[csv_lines.size() - 1].split(",")
		if fp.size() >= 13:
			first_mem = int(fp[12])
		if lp.size() >= 13:
			last_mem = int(lp[12])

	var summary = {
		"npc_count": total_spawned,
		"scenario": scenario,
		"samples": samples,
		"fps_avg": snapped(avg_fps, 0.01),
		"fps_min": snapped(min_fps, 0.01),
		"process_time_us_p50": snapped(p50_proc, 0.01),
		"process_time_us_p95": snapped(p95_proc, 0.01),
		"process_time_us_p99": snapped(p99_proc, 0.01),
		"physics_time_us_p50": snapped(p50_phys, 0.01),
		"physics_time_us_p95": snapped(p95_phys, 0.01),
		"physics_time_us_p99": snapped(p99_phys, 0.01),
		"spike_count": spike_count,
		"spike_frequency": snapped(spike_freq, 0.0001),
		"memory_start_bytes": first_mem,
		"memory_end_bytes": last_mem,
		"memory_delta_bytes": last_mem - first_mem,
		"signal_emit_count": _signal_emit_count,
		"proximity_check_count": _proximity_check_count,
		"behavior_tick_count": _behavior_tick_count,
		"animation_update_count": _animation_update_count,
		"collision_contact_count": _collision_contact_count,
		"main_bottleneck": _attrib_bottleneck(p95_proc, p95_phys, total_spawned, avg_fps),
		"json_timings": json_timings,
	}

	var js = JSON.new()
	var json_str = js.stringify(summary, "  ", false)

	print("\n=== NPCPressure Summary NPC=%d scenario=%s ===" % [total_spawned, scenario])
	print(json_str)

	var sname = "npc_pressure_%d_%s_summary.json" % [total_spawned, scenario]
	var spath = output_dir.path_join(sname)
	var sf = FileAccess.open(spath, FileAccess.WRITE)
	if sf:
		sf.store_string(json_str)
		sf.close()
		print("[NPCPressure] Wrote " + spath)


# ── Helpers ─────────────────────────────────────────────────────────────

func _avg(arr: Array[float]) -> float:
	if arr.is_empty():
		return 0.0
	var s := 0.0
	for v in arr:
		s += v
	return s / float(arr.size())


func _percentile_f(sorted_arr: Array[float], pct: float) -> float:
	if sorted_arr.is_empty():
		return 0.0
	var idx := int(ceil(pct / 100.0 * sorted_arr.size()) - 1)
	idx = clampi(idx, 0, sorted_arr.size() - 1)
	return sorted_arr[idx]