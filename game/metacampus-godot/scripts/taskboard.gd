extends CanvasLayer
class_name TaskBoard

## 任务板 UI
## 显示 8 个任务列表，标注状态（待办/进行中/完成/失败）
## Tab 键打开/关闭，ESC 关闭

signal quest_selected(quest_id: String)
signal quest_deselected

# UI 节点（引用场景中的节点）
@onready var panel: PanelContainer = $Panel
@onready var quest_list: VBoxContainer = $Panel/MarginContainer/VBoxContainer/ScrollContainer/QuestList
@onready var tab_buttons_container: HBoxContainer = $Panel/MarginContainer/VBoxContainer/TabButtons
@onready var title_label: Label = $Panel/MarginContainer/VBoxContainer/TitleLabel
@onready var close_hint: Label = $Panel/MarginContainer/VBoxContainer/CloseHint

# 状态
var is_visible: bool = false
var current_tab: int = 0  # 0: 进行中, 1: 已完成, 2: 全部

# 颜色定义
const COLOR_NORMAL = Color("#64748b")
const COLOR_ACTIVE = Color("#2563eb")
const COLOR_COMPLETED = Color("#10b981")
const COLOR_FAILED = Color("#ef4444")
const COLOR_AVAILABLE = Color("#f59e0b")

# Quest Manager
var quest_manager: Node = null

func _ready() -> void:
	add_to_group("taskboard")
	process_mode = Node.PROCESS_MODE_ALWAYS

	# 获取 Quest Manager
	quest_manager = get_tree().get_first_node_in_group("quest_manager")

	# 连接 Tab 按钮
	var tabs = tab_buttons_container.get_children()
	if tabs.size() >= 3:
		tabs[0].pressed.connect(_on_tab_changed.bind(0))
		tabs[1].pressed.connect(_on_tab_changed.bind(1))
		tabs[2].pressed.connect(_on_tab_changed.bind(2))

	_hide_board()

func _process(_delta: float) -> void:
	# Tab 键切换显示
	if Input.is_action_just_pressed("toggle_taskboard"):
		toggle_board()
	# ESC 关闭
	elif Input.is_action_just_pressed("ui_cancel") and is_visible:
		_hide_board()

func _on_tab_changed(tab_index: int) -> void:
	current_tab = tab_index
	_refresh_quest_list()

func _refresh_quest_list() -> void:
	# 清除旧任务项
	for child in quest_list.get_children():
		child.queue_free()

	if quest_manager == null:
		var placeholder = Label.new()
		placeholder.text = "加载中..."
		placeholder.add_theme_color_override("font_color", COLOR_NORMAL)
		quest_list.add_child(placeholder)
		return

	# 根据 Tab 获取任务
	var quests = []
	match current_tab:
		0:
			quests = quest_manager.get_active_quests()
		1:
			quests = quest_manager.get_completed_quests()
		2:
			quests = quest_manager.get_all_quests()

	# 创建任务项
	if quests.is_empty():
		var empty_label = Label.new()
		match current_tab:
			0:
				empty_label.text = "暂无进行中的任务"
			1:
				empty_label.text = "暂无已完成的任务"
			2:
				empty_label.text = "暂无任务"
		empty_label.add_theme_color_override("font_color", COLOR_NORMAL)
		quest_list.add_child(empty_label)
		return

	for quest in quests:
		var quest_id = quest.get("quest_id", "")
		var status = quest_manager.get_quest_status(quest_id)
		var item = _create_quest_item(quest, status)
		quest_list.add_child(item)

func _create_quest_item(quest: Dictionary, status: String) -> Control:
	# 创建任务项面板
	var item = PanelContainer.new()
	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.1, 0.12, 0.18, 0.8)
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	item.add_theme_stylebox_override("panel", style)

	var hbox = HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 8)
	item.add_child(hbox)

	# 状态图标
	var status_icon = Label.new()
	match status:
		"available":
			status_icon.text = "📌"
			status_icon.add_theme_color_override("font_color", COLOR_AVAILABLE)
		"active":
			status_icon.text = "⏳"
			status_icon.add_theme_color_override("font_color", COLOR_ACTIVE)
		"completed":
			status_icon.text = "✅"
			status_icon.add_theme_color_override("font_color", COLOR_COMPLETED)
		"failed":
			status_icon.text = "❌"
			status_icon.add_theme_color_override("font_color", COLOR_FAILED)
		_:
			status_icon.text = "❓"
	status_icon.add_theme_font_size_override("font_size", 16)
	hbox.add_child(status_icon)

	# 任务信息
	var vbox = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 4)
	hbox.add_child(vbox)

	# 标题 + 状态标签行
	var title_hbox = HBoxContainer.new()
	title_hbox.add_theme_constant_override("separation", 8)
	vbox.add_child(title_hbox)

	var title = Label.new()
	title.text = quest.get("title", "未知任务")
	title.add_theme_font_size_override("font_size", 16)
	title_hbox.add_child(title)

	# 状态标签
	var status_label = Label.new()
	match status:
		"available":
			status_label.text = "待领取"
			status_label.add_theme_color_override("font_color", COLOR_AVAILABLE)
		"active":
			status_label.text = "进行中"
			status_label.add_theme_color_override("font_color", COLOR_ACTIVE)
		"completed":
			status_label.text = "已完成"
			status_label.add_theme_color_override("font_color", COLOR_COMPLETED)
		"failed":
			status_label.text = "已失败"
			status_label.add_theme_color_override("font_color", COLOR_FAILED)
		_:
			status_label.text = "未知"
	status_label.add_theme_font_size_override("font_size", 11)
	title_hbox.add_child(status_label)

	# 描述
	var desc = Label.new()
	desc.text = quest.get("description", "")
	desc.add_theme_color_override("font_color", COLOR_NORMAL)
	desc.add_theme_font_size_override("font_size", 12)
	desc.autowrap_mode = TextServer.AUTOWRAP_WORD
	vbox.add_child(desc)

	# 进度
	if quest_manager.has_method("get_quest_progress_text"):
		var progress_text = quest_manager.get_quest_progress_text(quest.get("quest_id", ""))
		if progress_text != "":
			var progress = Label.new()
			progress.text = "进度: " + progress_text
			progress.add_theme_color_override("font_color", COLOR_NORMAL)
			progress.add_theme_font_size_override("font_size", 11)
			vbox.add_child(progress)

	return item

func toggle_board() -> void:
	if is_visible:
		_hide_board()
	else:
		AudioManager.play_ui_click()
		_show_board()

func show_board() -> void:
	_show_board()

func _show_board() -> void:
	is_visible = true
	panel.visible = true

	# 刷新任务列表
	_refresh_quest_list()

	# 禁用玩家控制
	var player = get_tree().get_first_node_in_group("player")
	if player and player.has_method("set_enabled"):
		player.set_enabled(false)

func _hide_board() -> void:
	is_visible = false
	panel.visible = false

	# 恢复玩家控制
	var player = get_tree().get_first_node_in_group("player")
	if player and player.has_method("set_enabled"):
		player.set_enabled(true)

func _on_quest_clicked(quest_id: String) -> void:
	quest_selected.emit(quest_id)
