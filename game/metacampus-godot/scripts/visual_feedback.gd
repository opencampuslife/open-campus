extends CanvasLayer
## G4 Visual Feedback — 指标变化 toast、高风险 warning、Demo 信息
## 录制友好：所有文字大号、颜色鲜明

const TOAST_DURATION: float = 2.5
const WARNING_DURATION: float = 3.0

var _metric_manager: Node = null
var _toasts: Array = []

# Preload for speed
var _metrics_prev: Dictionary = {}

func _ready() -> void:
	add_to_group("visual_feedback")
	layer = 10  # 最上层
	process_mode = Node.PROCESS_MODE_ALWAYS

func _process(delta: float) -> void:
	_check_metric_changes()
	_update_toasts(delta)

# ── Metric change detection ──

func _check_metric_changes() -> void:
	if not _metric_manager:
		_metric_manager = get_tree().get_first_node_in_group("metric_manager")
		if not _metric_manager:
			return
	
	var current = _metric_manager.get_all()
	
	if _metrics_prev.is_empty():
		_metrics_prev = current.duplicate()
		return
	
	for metric_id in current:
		var prev_val = _metrics_prev.get(metric_id, 0)
		var cur_val = current.get(metric_id, 0)
		var delta = cur_val - prev_val
		if delta != 0:
			_show_metric_toast(metric_id, delta, cur_val)
	
	_metrics_prev = current.duplicate()

func _show_metric_toast(metric_id: String, delta: int, new_val: int) -> void:
	var name = _metric_name(metric_id)
	var sign = "+" if delta > 0 else ""
	var color = Color("#10b981") if delta > 0 else Color("#ef4444")
	var icon = "▲" if delta > 0 else "▼"
	
	var label = Label.new()
	label.text = "%s %s%s%d → %d" % [icon, name, sign, delta, new_val]
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	label.add_theme_font_size_override("font_size", 18)
	label.add_theme_color_override("font_color", color)
	label.anchor_right = 1.0
	label.offset_right = -20
	label.add_child(_make_outline(Color.BLACK))
	add_child(label)
	
	_toasts.append({
		"label": label,
		"remaining": TOAST_DURATION,
		"y": 60.0 + _toasts.size() * 32.0
	})
	
	# 高风险负向变化 → 红色警告
	if delta <= -10:
		_show_red_warning(metric_id, delta, name)

func _show_red_warning(metric_id: String, delta: int, name: String) -> void:
	var warning = Label.new()
	warning.text = "⚠ 警告: %s %d" % [name, delta]
	warning.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	warning.anchor_left = 0.5
	warning.anchor_right = 0.5
	warning.offset_top = 200
	warning.offset_left = -200
	warning.offset_right = 200
	warning.add_theme_font_size_override("font_size", 28)
	warning.add_theme_color_override("font_color", Color("#ef4444"))
	warning.add_child(_make_outline(Color(0.5, 0, 0, 0.8)))
	add_child(warning)
	
	# 自动消失
	get_tree().create_timer(WARNING_DURATION).timeout.connect(func():
		if is_instance_valid(warning):
			warning.queue_free()
	)

func _make_outline(color: Color) -> Label:
	var outline = Label.new()
	outline.text = ""  # outlines via duplicate labels are complex; use modulate for simplicity
	return outline

func _update_toasts(delta: float) -> void:
	var i = 0
	while i < _toasts.size():
		_toasts[i]["remaining"] -= delta
		var label: Label = _toasts[i]["label"]
		
		if _toasts[i]["remaining"] <= 0:
			label.queue_free()
			_toasts.remove_at(i)
			continue
		
		# 淡出
		if _toasts[i]["remaining"] < 0.5:
			label.modulate.a = _toasts[i]["remaining"] * 2.0
		
		# Stack position
		label.offset_top = 20 + i * 30
		i += 1

func _metric_name(id: String) -> String:
	match id:
		"school_efficiency": return "学校效率"
		"parent_trust": return "家长信任"
		"compliance_safety": return "合规安全"
		"system_stability": return "系统稳定"
		_: return id

# ── Demo info display ──

func show_demo_info(text: String) -> void:
	var label = Label.new()
	label.text = text
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.anchor_left = 0.5
	label.anchor_right = 0.5
	label.offset_top = 80
	label.offset_left = -300
	label.offset_right = 300
	label.add_theme_font_size_override("font_size", 20)
	label.add_theme_color_override("font_color", Color("#ffffff"))
	add_child(label)
	get_tree().create_timer(3.0).timeout.connect(func():
		if is_instance_valid(label):
			label.queue_free()
	)
