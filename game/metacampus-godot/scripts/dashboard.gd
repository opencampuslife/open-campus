extends CanvasLayer
class_name Dashboard

## 指标仪表盘
## 显示四个核心指标的当前数值，支持快捷键打开/关闭

const WARNING_COLOR = Color("#ef4444")   # 红色警告
const NORMAL_COLOR = Color("#22c55e")    # 绿色正常
const WARNING_THRESHOLD = 30

const COLOR_NORMAL = Color("#1458ea")     # 蓝
const COLOR_PARENT_TRUST = Color("#10b981")
const COLOR_COMPLIANCE = Color("#7c3aed")
const COLOR_STABILITY = Color("#06b6d4")

var is_visible: bool = false
var metric_manager: Node = null

# 指标显示节点的引用
var _metric_nodes: Dictionary = {
	"school_efficiency": null,
	"parent_trust": null,
	"compliance_safety": null,
	"system_stability": null
}

# 指标的默认颜色（各自的视觉主题色，warning 时统一变红）
var _metric_colors: Dictionary = {
	"school_efficiency": COLOR_NORMAL,
	"parent_trust": COLOR_PARENT_TRUST,
	"compliance_safety": COLOR_COMPLIANCE,
	"system_stability": COLOR_STABILITY
}

func _ready() -> void:
	add_to_group("dashboard")
	_hide()

	# 获取 MetricManager 引用
	metric_manager = get_tree().get_first_node_in_group("metric_manager")

	# 监听指标变化信号（metric_manager 在 dialogue_manager 应用效果后发出）
	if metric_manager and metric_manager.has_signal("all_metrics_updated"):
		metric_manager.all_metrics_updated.connect(_on_metrics_updated)
	if metric_manager and metric_manager.has_signal("metric_warning"):
		metric_manager.metric_warning.connect(_on_metric_warning)

	# 监听 dialogue_manager 的 choice_made 信号（对话选择后立即更新指标）
	var dialogue_manager = get_tree().get_first_node_in_group("dialogue_manager")
	if dialogue_manager and dialogue_manager.has_signal("choice_made"):
		dialogue_manager.choice_made.connect(_on_choice_made)

	# 初始化显示
	_update_all_metrics()

func _process(_delta: float) -> void:
	# 专用快捷键切换 Dashboard
	if Input.is_action_just_pressed("toggle_dashboard"):
		_toggle()
	# ESC 关闭（仅当可见时）
	elif Input.is_action_just_pressed("ui_cancel") and is_visible:
		_hide()

func _toggle() -> void:
	if is_visible:
		_hide()
	else:
		_show()

func _show() -> void:
	visible = true
	is_visible = true
	_update_all_metrics()

	# 禁用玩家控制
	var player = get_tree().get_first_node_in_group("player")
	if player and player.has_method("set_enabled"):
		player.set_enabled(false)

func _hide() -> void:
	visible = false
	is_visible = false

	# 恢复玩家控制
	var player = get_tree().get_first_node_in_group("player")
	if player and player.has_method("set_enabled"):
		player.set_enabled(true)

func _update_all_metrics() -> void:
	"""更新所有指标的显示"""
	if not metric_manager:
		return

	var metrics = metric_manager.get_all_with_metadata()
	for metric_id in _metric_nodes:
		_update_metric_display(metric_id, metrics.get(metric_id, {}))

func _update_metric_display(metric_id: String, metric_data: Dictionary) -> void:
	var container = _get_metric_container(metric_id)
	if not container:
		return

	var value_label = container.get_node_or_null("ValueLabel")
	var progress_bar = container.get_node_or_null("ProgressBar")

	if not value_label or not progress_bar:
		return

	var value = metric_data.get("value", 0)

	# 更新数值显示
	value_label.text = str(value)

	# 更新进度条
	progress_bar.value = value

	# 颜色逻辑：低于警告阈值 → 红色，否则用该指标的默认主题色
	var warning_threshold = metric_data.get("warning_threshold", WARNING_THRESHOLD)
	var is_warning_state = value < warning_threshold

	var font_color = WARNING_COLOR if is_warning_state else _metric_colors.get(metric_id, NORMAL_COLOR)
	value_label.add_theme_color_override("font_color", font_color)

	# 设置进度条填充颜色
	var fill_style = StyleBoxFlat.new()
	fill_style.bg_color = font_color
	fill_style.corner_radius_top_left = 4
	fill_style.corner_radius_top_right = 4
	fill_style.corner_radius_bottom_left = 4
	fill_style.corner_radius_bottom_right = 4
	progress_bar.add_theme_stylebox_override("fill", fill_style)

func _get_metric_container(metric_id: String) -> Control:
	if not _metric_nodes[metric_id]:
		# 懒加载：从场景树查找对应的容器节点
		var panel = get_node_or_null("Panel/MetricsContainer")
		if not panel:
			return null

		var node_name = _get_node_name_for_metric(metric_id)
		_metric_nodes[metric_id] = panel.get_node_or_null(node_name)

	return _metric_nodes[metric_id]

func _get_node_name_for_metric(metric_id: String) -> String:
	match metric_id:
		"school_efficiency":
			return "SchoolEfficiency"
		"parent_trust":
			return "ParentTrust"
		"compliance_safety":
			return "ComplianceSafety"
		"system_stability":
			return "SystemStability"
		_:
			return ""

func _on_choice_made(_choice_data: Dictionary) -> void:
	"""对话选择触发后立即刷新指标显示"""
	_update_all_metrics()

func _on_metrics_updated(metrics: Dictionary) -> void:
	"""MetricManager 发出 all_metrics_updated 时更新显示"""
	if is_visible:
		_update_all_metrics()
	# 即使不可见也更新内部状态，确保打开时显示最新值
	var metric_manager_ref = metric_manager
	if metric_manager_ref:
		var all_metrics = metric_manager_ref.get_all_with_metadata()
		for metric_id in _metric_nodes:
			_update_metric_display(metric_id, all_metrics.get(metric_id, {}))

func _on_metric_warning(metric_id: String, value: int) -> void:
	var metric_name = ""
	var container = _get_metric_container(metric_id)
	if container:
		var name_label = container.get_node_or_null("NameLabel")
		if name_label:
			metric_name = name_label.text

	print("[Dashboard] 警告: %s 指标过低 (当前值: %d)" % [metric_name, value])
