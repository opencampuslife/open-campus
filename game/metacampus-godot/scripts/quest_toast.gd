extends CanvasLayer
class_name QuestToast

## 任务完成 Toast 提示
## 任务完成后弹出 toast 提示（2 秒后自动消失，从顶部滑入）

# Toast 显示时长
const DISPLAY_DURATION: float = 2.0

# UI 节点（引用场景节点，不自建）
@onready var toast_panel: PanelContainer = $ToastPanel
@onready var title_icon: Label = $ToastPanel/MarginContainer/VBoxContainer/Title/Icon
@onready var title_label: Label = $ToastPanel/MarginContainer/VBoxContainer/Title/Label
@onready var quest_name_label: Label = $ToastPanel/MarginContainer/VBoxContainer/QuestName
@onready var rewards_label: Label = $ToastPanel/MarginContainer/VBoxContainer/Rewards

# 状态
var is_showing: bool = false
var display_timer: float = 0.0

# 动画 - 记录最终位置
var _target_offset_top: float = 0.0

# Quest Manager
var quest_manager: Node = null

func _ready() -> void:
	add_to_group("quest_toast")
	process_mode = Node.PROCESS_MODE_ALWAYS

	# 记录动画目标位置
	_target_offset_top = toast_panel.offset_top

	# 初始隐藏
	_hide_toast()

	# 应用面板样式（场景中无 StyleBoxFlat，这里用代码设置）
	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.1, 0.15, 0.2, 0.95)
	panel_style.border_width_left = 2
	panel_style.border_width_right = 2
	panel_style.border_width_top = 2
	panel_style.border_width_bottom = 2
	panel_style.border_color = Color("#10b981")
	panel_style.corner_radius_top_left = 8
	panel_style.corner_radius_top_right = 8
	panel_style.corner_radius_bottom_left = 8
	panel_style.corner_radius_bottom_right = 8
	panel_style.content_margin_left = 20
	panel_style.content_margin_right = 20
	panel_style.content_margin_top = 16
	panel_style.content_margin_bottom = 16
	toast_panel.add_theme_stylebox_override("panel", panel_style)

	# 设置标题样式
	title_label.add_theme_color_override("font_color", Color("#10b981"))
	title_label.add_theme_font_size_override("font_size", 18)
	title_icon.add_theme_font_size_override("font_size", 20)

	# 设置任务名称样式
	quest_name_label.add_theme_font_size_override("font_size", 14)

	# 设置奖励说明样式
	rewards_label.add_theme_color_override("font_color", Color("#64748b"))
	rewards_label.add_theme_font_size_override("font_size", 12)

	# 获取 Quest Manager
	quest_manager = get_tree().get_first_node_in_group("quest_manager")

	# 连接信号
	if quest_manager:
		quest_manager.quest_started.connect(_on_quest_started)
		quest_manager.quest_completed.connect(_on_quest_completed)
		quest_manager.quest_failed.connect(_on_quest_failed)

func _on_quest_started(quest_data: Dictionary) -> void:
	AudioManager.play_quest_start()

func _process(delta: float) -> void:
	if is_showing:
		display_timer -= delta
		if display_timer <= 0:
			_hide_toast()

func _on_quest_completed(quest_data: Dictionary) -> void:
	AudioManager.play_quest_complete()
	show_quest_complete(quest_data)

func _on_quest_failed(quest_data: Dictionary) -> void:
	AudioManager.play_quest_fail()
	show_quest_failed(quest_data)

func show_quest_complete(quest_data: Dictionary) -> void:
	# 重置为成功样式
	var panel_style = toast_panel.get_theme_stylebox("panel") as StyleBoxFlat
	if panel_style:
		panel_style.border_color = Color("#10b981")
	title_icon.text = "🎉"
	title_label.text = "任务完成！"
	title_label.add_theme_color_override("font_color", Color("#10b981"))

	# 更新 Toast 内容
	quest_name_label.text = quest_data.get("title", "未知任务")

	# 构建奖励文本
	var reward = quest_data.get("reward", {})
	var reward_texts = []
	for metric_id in reward.keys():
		var value = reward[metric_id]
		var metric_name = _get_metric_name(metric_id)
		var sign = "+" if value > 0 else ""
		reward_texts.append("%s%s%d" % [metric_name, sign, value])

	if not reward_texts.is_empty():
		rewards_label.text = "奖励: " + ", ".join(reward_texts)
	else:
		rewards_label.text = ""

	# 显示 Toast
	_show_toast()

func _show_toast() -> void:
	is_showing = true
	display_timer = DISPLAY_DURATION

	# 设置初始位置（从屏幕顶部外滑入）
	toast_panel.offset_top = _target_offset_top - 80
	toast_panel.visible = true
	toast_panel.modulate.a = 1.0

	# 停止之前的动画
	if toast_panel and toast_panel.get_tree():
		for t in get_tree().get_processed_tweens():
			if t.is_valid() and t.is_running():
				t.kill()

	# 使用单一 Tween 做滑入动画
	var tween = create_tween()
	tween.set_parallel(false)
	tween.tween_property(toast_panel, "offset_top", _target_offset_top, 0.35).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)

func _hide_toast() -> void:
	is_showing = false
	toast_panel.visible = false

func _get_metric_name(metric_id: String) -> String:
	match metric_id:
		"school_efficiency":
			return "学校效率"
		"parent_trust":
			return "家长信任"
		"compliance_safety":
			return "合规安全"
		"system_stability":
			return "系统稳定性"
		_:
			return metric_id

## 显示任务失败 Toast
func show_quest_failed(quest_data: Dictionary) -> void:
	# 改为失败样式
	var panel_style = toast_panel.get_theme_stylebox("panel") as StyleBoxFlat
	if panel_style:
		panel_style.border_color = Color("#ef4444")

	title_icon.text = "❌"
	title_label.text = "任务失败！"
	title_label.add_theme_color_override("font_color", Color("#ef4444"))
	quest_name_label.text = quest_data.get("title", "未知任务")

	# 构建惩罚文本
	var fail_condition = quest_data.get("fail_condition", {})
	var penalty = fail_condition.get("penalty", {})
	var penalty_texts = []
	for metric_id in penalty.keys():
		var value = penalty[metric_id]
		var metric_name = _get_metric_name(metric_id)
		var sign = "+" if value > 0 else ""
		penalty_texts.append("%s%s%d" % [metric_name, sign, value])

	if not penalty_texts.is_empty():
		rewards_label.text = "惩罚: " + ", ".join(penalty_texts)
	else:
		rewards_label.text = ""

	# 显示 Toast
	_show_toast()

	# 2 秒后恢复成功样式
	await get_tree().create_timer(2.5).timeout
	if is_instance_valid(toast_panel):
		panel_style = toast_panel.get_theme_stylebox("panel") as StyleBoxFlat
		if panel_style:
			panel_style.border_color = Color("#10b981")
		title_icon.text = "🎉"
		title_label.text = "任务完成！"
		title_label.add_theme_color_override("font_color", Color("#10b981"))
